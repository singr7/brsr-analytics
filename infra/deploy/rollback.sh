#!/usr/bin/env bash
# Return the stack to a previously deployed tag.
#
#   rollback.sh [tag] [reason]
#
# With no tag, rolls back to the recorded previous release. Called automatically
# by deploy.sh when a health check or smoke test fails, and available to an
# operator during an incident.
#
# Rolls back CODE ONLY. Migrations are expand-only by policy, so the previous
# release runs against the newer schema; there is no automatic down-migration
# and there should never be one during an incident.
set -euo pipefail

source /opt/brsrlens/env/node.env

LOG=/opt/brsrlens/log/deploy.log
mkdir -p "$(dirname "$LOG")"
log() { printf '[rollback %s] %s\n' "$(date -u +%FT%TZ)" "$*" | tee -a "$LOG"; }

TARGET="${1:-}"
REASON="${2:-operator requested}"

if [[ -z "$TARGET" ]]; then
  TARGET="$(aws ssm get-parameter --name "${SSM_PREFIX}/release/prev" \
    --region "$AWS_REGION" --query Parameter.Value --output text)"
fi

if [[ -z "$TARGET" || "$TARGET" == "bootstrap" || "$TARGET" == "None" ]]; then
  log "no rollback target recorded. Deploy a known-good tag explicitly."
  exit 1
fi

log "rolling back to ${TARGET} (${REASON})"

aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$REGISTRY" >/dev/null

for repo in api web; do
  docker pull --quiet "${REGISTRY}/brsrlens/${repo}:${TARGET}" >/dev/null
done

export RELEASE_TAG="$TARGET"
/opt/brsrlens/bin/render-env.sh
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --remove-orphans

DEADLINE=$((SECONDS + 180))
until docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T api \
        curl -fsS --max-time 5 http://localhost:8000/healthz >/dev/null 2>&1; do
  if (( SECONDS > DEADLINE )); then
    log "CRITICAL: rollback to ${TARGET} did not become healthy. Manual intervention required."
    aws sns publish --region "$AWS_REGION" --topic-arn "$ALERTS_TOPIC_ARN" \
      --subject "BRSR Lens ${ENVIRONMENT} ROLLBACK FAILED" \
      --message "Rollback to ${TARGET} did not become healthy after ${REASON}. The site is down. Open a Session Manager shell on the node." >/dev/null 2>&1 || true
    exit 1
  fi
  sleep 3
done

aws ssm put-parameter --name "${SSM_PREFIX}/release/current" --type String \
  --overwrite --value "$TARGET" --region "$AWS_REGION" >/dev/null

log "rolled back to ${TARGET} and healthy"
aws sns publish --region "$AWS_REGION" --topic-arn "$ALERTS_TOPIC_ARN" \
  --subject "BRSR Lens ${ENVIRONMENT} rolled back" \
  --message "Rolled back to ${TARGET}. Reason: ${REASON}. The site is healthy. The failed release was not promoted." >/dev/null 2>&1 || true
