#!/usr/bin/env bash
# Database snapshot to the backups bucket.
#
#   backup.sh [label]
#
# Runs nightly from cron and before every ingest. A successful upload publishes
# BackupSucceeded=1, which the dead-man CloudWatch alarm watches: a backup that
# silently stops running raises an alarm rather than being discovered during a
# restore attempt.
#
# This is a logical dump, which is the right tool at this corpus size and is
# restorable by restore.sh with no coordination. The PITR story in
# DEPLOYMENT.md section 4 (pgBackRest WAL archiving) is the upgrade when RPO
# needs to be minutes rather than a day.
set -euo pipefail

source /opt/brsrlens/env/node.env

LABEL="${1:-nightly}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
NAME="${ENVIRONMENT}-${LABEL}-${STAMP}.sql.gz"
STAGING="/opt/brsrlens/data/backup-staging"
DEST="s3://${BACKUPS_BUCKET}/postgres/${NAME}"

mkdir -p "$STAGING"
trap 'rm -f "${STAGING}/${NAME}"' EXIT

log() { printf '[backup %s] %s\n' "$(date -u +%FT%TZ)" "$*"; }

compose() {
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" "$@"
}

log "dumping ${POSTGRES_DB:-brsrlens} to ${NAME}"

# --clean --if-exists makes the dump self-contained: restoring over an existing
# database does not need a manual drop first.
if ! compose exec -T postgres pg_dump \
      -U "${POSTGRES_USER:-brsrlens}" \
      -d "${POSTGRES_DB:-brsrlens}" \
      --clean --if-exists --no-owner --no-privileges \
    | gzip -9 > "${STAGING}/${NAME}"; then
  log "FAILED: pg_dump did not complete"
  aws sns publish --region "$AWS_REGION" --topic-arn "$ALERTS_TOPIC_ARN" \
    --subject "BRSR Lens ${ENVIRONMENT} backup FAILED" \
    --message "pg_dump failed on ${DOMAIN_NAME} for label '${LABEL}'." >/dev/null 2>&1 || true
  exit 1
fi

SIZE_BYTES="$(stat -c %s "${STAGING}/${NAME}")"

# A dump far smaller than expected means an empty or partial database. Uploading
# it would rotate a good backup out of retention and leave nothing to restore.
if (( SIZE_BYTES < 1048576 )); then
  log "FAILED: dump is only ${SIZE_BYTES} bytes, which is too small to be the real corpus"
  aws sns publish --region "$AWS_REGION" --topic-arn "$ALERTS_TOPIC_ARN" \
    --subject "BRSR Lens ${ENVIRONMENT} backup REJECTED" \
    --message "The dump on ${DOMAIN_NAME} was ${SIZE_BYTES} bytes. It was not uploaded. Check that the database is populated." >/dev/null 2>&1 || true
  exit 1
fi

aws s3 cp "${STAGING}/${NAME}" "$DEST" \
  --region "$AWS_REGION" \
  --sse AES256 \
  --only-show-errors

log "uploaded ${DEST} ($(numfmt --to=iec "$SIZE_BYTES" 2>/dev/null || echo "${SIZE_BYTES}B"))"

aws cloudwatch put-metric-data \
  --region "$AWS_REGION" \
  --namespace "BRSRLens/Ops" \
  --metric-name BackupSucceeded \
  --value 1 \
  --dimensions "Environment=${ENVIRONMENT}" >/dev/null

aws cloudwatch put-metric-data \
  --region "$AWS_REGION" \
  --namespace "BRSRLens/Ops" \
  --metric-name BackupSizeBytes \
  --value "$SIZE_BYTES" \
  --unit Bytes \
  --dimensions "Environment=${ENVIRONMENT}" >/dev/null

log "done"
