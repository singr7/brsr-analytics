#!/usr/bin/env bash
# Roll out a release tag on this node.
#
#   deploy.sh <release-tag>
#
# Invoked through SSM by ops/bin/brsrlens-prod, never by hand over SSH.
#
# Order matters and is deliberate:
#   1. resolve and pull both images BEFORE touching anything running, so a bad
#      tag fails while the current release is still serving;
#   2. run migrations expand-only, with the old code still up, so a migration
#      that fails leaves a working site rather than a half-migrated one;
#   3. restart, wait for health, smoke test;
#   4. roll back automatically to the recorded previous tag if the smoke fails.
set -euo pipefail

source /opt/brsrlens/env/node.env

RELEASE_TAG="${1:?usage: deploy.sh <release-tag>}"
LOG=/opt/brsrlens/log/deploy.log
mkdir -p "$(dirname "$LOG")"

log() { printf '[deploy %s] %s\n' "$(date -u +%FT%TZ)" "$*" | tee -a "$LOG"; }

notify() {
  aws sns publish --region "$AWS_REGION" --topic-arn "$ALERTS_TOPIC_ARN" \
    --subject "BRSR Lens ${ENVIRONMENT} deploy: $1" --message "$2" >/dev/null 2>&1 || true
}

PREV_TAG="$(aws ssm get-parameter --name "${SSM_PREFIX}/release/current" \
  --region "$AWS_REGION" --query Parameter.Value --output text)"

log "rolling out ${RELEASE_TAG} (current: ${PREV_TAG})"

# --- 1. fetch images --------------------------------------------------------
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$REGISTRY" >/dev/null
log "authenticated to ${REGISTRY}"

for repo in api web; do
  image="${REGISTRY}/brsrlens/${repo}:${RELEASE_TAG}"
  log "pulling ${image}"
  if ! docker pull --quiet "$image" >/dev/null; then
    log "FAILED: ${image} is not in the registry. Nothing was changed."
    notify "aborted" "Release ${RELEASE_TAG} was not deployed: ${image} could not be pulled. ${PREV_TAG} is still serving."
    exit 1
  fi
done

# --- 2. configuration and migrations ---------------------------------------
export RELEASE_TAG
/opt/brsrlens/bin/render-env.sh

compose() {
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" "$@"
}

# Probes the app directly inside the container rather than through nginx: port
# 80 only issues the HTTPS redirect, and at this point in the deploy the proxy
# may still be starting. The end-to-end path is covered by smoke.sh next.
compose_health() {
  compose exec -T api curl -fsS --max-time 5 http://localhost:8000/healthz >/dev/null 2>&1
}

# Postgres and Redis are stateful and are not restarted by a code deploy.
log "ensuring data services are up"
compose up -d postgres redis
compose exec -T postgres sh -c 'until pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"; do sleep 2; done'

# Expand-only: every migration in this repo adds structures that the previous
# release tolerates, so this runs while the old containers are still serving.
log "applying database migrations"
if ! compose run --rm --no-deps api python -m alembic upgrade head 2>&1 | tee -a "$LOG"; then
  log "FAILED: migration did not complete. Release ${PREV_TAG} is untouched and still serving."
  notify "migration failed" "Release ${RELEASE_TAG} aborted during alembic upgrade. ${PREV_TAG} is still serving. Node ${HOSTNAME}."
  exit 1
fi

# --- 3. restart and health-gate --------------------------------------------
log "restarting application services"
compose up -d --remove-orphans

log "waiting for the API to report healthy"
DEADLINE=$((SECONDS + 180))
until compose_health; do
  if (( SECONDS > DEADLINE )); then
    log "FAILED: API did not become healthy within 180s"
    /opt/brsrlens/bin/rollback.sh "$PREV_TAG" "health check timeout on ${RELEASE_TAG}"
    exit 1
  fi
  sleep 3
done
log "API healthy"

# --- 4. smoke -------------------------------------------------------------
if ! /opt/brsrlens/bin/smoke.sh 2>&1 | tee -a "$LOG"; then
  log "FAILED: smoke tests did not pass"
  /opt/brsrlens/bin/rollback.sh "$PREV_TAG" "smoke failure on ${RELEASE_TAG}"
  exit 1
fi

# --- 5. record --------------------------------------------------------------
aws ssm put-parameter --name "${SSM_PREFIX}/release/prev" --type String \
  --overwrite --value "$PREV_TAG" --region "$AWS_REGION" >/dev/null
aws ssm put-parameter --name "${SSM_PREFIX}/release/current" --type String \
  --overwrite --value "$RELEASE_TAG" --region "$AWS_REGION" >/dev/null

docker image prune -f --filter "until=168h" >/dev/null 2>&1 || true

log "SUCCESS: ${RELEASE_TAG} is live (rollback target: ${PREV_TAG})"
notify "success" "Release ${RELEASE_TAG} is live on ${DOMAIN_NAME}. Rollback target is ${PREV_TAG}."
