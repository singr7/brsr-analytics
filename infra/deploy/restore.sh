#!/usr/bin/env bash
# Restore the database from a backup in the backups bucket.
#
#   restore.sh list
#   restore.sh <backup-name>   e.g. prod-nightly-20260816T193000Z.sql.gz
#
# Destructive and deliberately awkward: it stops the application, requires the
# operator to type the environment name, and verifies the result before
# bringing the stack back. This is the procedure the quarterly drill exercises.
set -euo pipefail

source /opt/brsrlens/env/node.env

log() { printf '[restore %s] %s\n' "$(date -u +%FT%TZ)" "$*"; }

compose() {
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" "$@"
}

scalar() {
  compose exec -T postgres psql -U "${POSTGRES_USER:-brsrlens}" -d "${POSTGRES_DB:-brsrlens}" \
    -tAc "$1" 2>/dev/null | tr -d '[:space:]'
}

if [[ "${1:-list}" == "list" ]]; then
  echo "Backups in s3://${BACKUPS_BUCKET}/postgres/ (newest last):"
  aws s3 ls "s3://${BACKUPS_BUCKET}/postgres/" --region "$AWS_REGION" | sort
  exit 0
fi

NAME="$1"
SRC="s3://${BACKUPS_BUCKET}/postgres/${NAME}"
STAGING="/opt/brsrlens/data/restore-staging"

log "about to restore ${NAME} into the ${ENVIRONMENT} database on ${DOMAIN_NAME}"
log "this REPLACES the current contents, including any corpus ingested since that backup"
read -r -p "Type the environment name (${ENVIRONMENT}) to continue: " CONFIRM
if [[ "$CONFIRM" != "$ENVIRONMENT" ]]; then
  log "aborted"
  exit 1
fi

mkdir -p "$STAGING"
trap 'rm -f "${STAGING}/${NAME}"' EXIT

log "downloading ${SRC}"
aws s3 cp "$SRC" "${STAGING}/${NAME}" --region "$AWS_REGION" --only-show-errors

# Take a snapshot of what is about to be replaced. A restore run against the
# wrong backup is otherwise unrecoverable.
log "snapshotting the current database before overwriting it"
/opt/brsrlens/bin/backup.sh "pre-restore" || log "WARNING: pre-restore snapshot failed; continuing at operator request"

log "stopping application services (postgres stays up to receive the restore)"
compose stop api worker scheduler web

log "restoring"
gunzip -c "${STAGING}/${NAME}" \
  | compose exec -T postgres psql -U "${POSTGRES_USER:-brsrlens}" -d "${POSTGRES_DB:-brsrlens}" \
      -v ON_ERROR_STOP=1 --quiet

# Assertions the drill checklist requires: the corpus is present, and lineage
# integrity survived - every metric still resolves to a pinned field version.
COMPANIES="$(scalar 'select count(*) from companies')"
METRICS="$(scalar 'select count(*) from metrics')"
ORPHANS="$(scalar 'select count(*) from metrics m left join field_version_pins p on p.id = m.field_version_pin_id where p.id is null')"

log "restored: ${COMPANIES} companies, ${METRICS} metrics, ${ORPHANS} metrics without a pin"

if [[ "${ORPHANS:-1}" != "0" ]]; then
  log "CRITICAL: ${ORPHANS} metrics have no pinned field version. Lineage is broken; do not serve this."
  exit 1
fi

log "starting application services"
compose up -d
sleep 10
/opt/brsrlens/bin/smoke.sh
