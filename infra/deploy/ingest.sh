#!/usr/bin/env bash
# Corpus acquisition on the production node.
#
#   ingest.sh initial [--limit N] [--fy YYYY] [--replace-synthetic]
#   ingest.sh next    [--limit N] [--fy YYYY]
#   ingest.sh refresh [--limit N] [--fy YYYY]
#   ingest.sh publish [--fy YYYY]
#   ingest.sh status
#
# Wraps `python -m worker.acquire.cli` inside the api container and then does the
# three things that must happen for an ingest to be visible in the product:
# publish the provisional mappings, rebuild metrics and scores, and invalidate
# the semantic cache. The CLI's --publish flag already chains all three; this
# script exists to add the operational guarantees around it:
#
#   * refuses to run while the legal gate flag is off, with the reason;
#   * takes a database snapshot first, so a bad batch is recoverable;
#   * serialises runs with a lock, because two concurrent cursors would skip
#     companies rather than collide visibly;
#   * reports the resulting corpus counts, not just the run's own tallies;
#   * writes the whole transcript to a log CloudWatch collects.
set -euo pipefail

source /opt/brsrlens/env/node.env

MODE="${1:?usage: ingest.sh {initial|next|refresh|publish|status} [options]}"
shift || true

LOG=/opt/brsrlens/log/ingest.log
LOCK=/var/lock/brsrlens-ingest.lock
mkdir -p "$(dirname "$LOG")"

log() { printf '[ingest %s] %s\n' "$(date -u +%FT%TZ)" "$*" | tee -a "$LOG"; }

compose() {
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" "$@"
}

# Runs a read-only SQL scalar against the stack's Postgres.
scalar() {
  compose exec -T postgres psql -U "${POSTGRES_USER:-brsrlens}" -d "${POSTGRES_DB:-brsrlens}" \
    -tAc "$1" 2>/dev/null | tr -d '[:space:]'
}

corpus_summary() {
  cat <<EOF
  companies        $(scalar 'select count(*) from companies')
  filings parsed   $(scalar "select count(*) from filings where status='parsed'")
  filings missing  $(scalar "select count(*) from filings where status='missing'")
  raw xbrl facts   $(scalar 'select count(*) from xbrl_facts')
  pinned fields    $(scalar 'select count(*) from field_version_pins')
  metrics          $(scalar 'select count(*) from metrics')
  scores           $(scalar 'select count(*) from scores')
EOF
}

if [[ "$MODE" == "status" ]]; then
  echo "Corpus state on ${DOMAIN_NAME}:"
  corpus_summary
  echo
  echo "Ten most recent ingestion runs:"
  compose exec -T postgres psql -U "${POSTGRES_USER:-brsrlens}" -d "${POSTGRES_DB:-brsrlens}" -c \
    "select started_at, mode, status, discovered_count, fetched_count, parsed_count, missing_count, error_count
       from ingestion_runs order by started_at desc limit 10"
  echo
  echo "Next registry offset: $(scalar 'select coalesce(max(next_offset),0) from ingestion_state')"
  exit 0
fi

case "$MODE" in
  initial|next|refresh|publish) ;;
  *) log "unknown mode '${MODE}'"; exit 2 ;;
esac

# --- legal gate -------------------------------------------------------------
# Acquisition is fail-closed by design. Publishing does not fetch anything, so
# it stays allowed while the gate is shut.
if [[ "$MODE" != "publish" ]]; then
  GATE="$(aws ssm get-parameter --name "${SSM_PREFIX}/env/SOURCE_NSE_BRSR_ENABLED" \
    --region "$AWS_REGION" --query Parameter.Value --output text 2>/dev/null || echo "false")"
  if [[ "$GATE" != "true" ]]; then
    log "REFUSED: SOURCE_NSE_BRSR_ENABLED is '${GATE}'."
    log "Automated acquisition stays closed until the legal gate in docs/gates/legal.md is signed."
    log "To open it: aws ssm put-parameter --name ${SSM_PREFIX}/env/SOURCE_NSE_BRSR_ENABLED \\"
    log "              --type String --overwrite --value true --region ${AWS_REGION}"
    log "            then: systemctl restart brsrlens"
    exit 1
  fi
fi

# --- serialise --------------------------------------------------------------
exec 9>"$LOCK"
if ! flock -n 9; then
  log "REFUSED: another ingest is already running. The registry cursor is not safe to advance twice."
  exit 1
fi

# --- snapshot before mutating ----------------------------------------------
# `next` and `refresh` advance a persisted cursor and replace pinned values; a
# bad mapping or a source revision is far cheaper to undo from a snapshot than
# to unpick row by row.
log "mode=${MODE} args=${*:-none}"
log "taking a pre-ingest snapshot"
if ! /opt/brsrlens/bin/backup.sh "pre-ingest-${MODE}" >>"$LOG" 2>&1; then
  log "ABORTED: pre-ingest snapshot failed. Not touching the corpus."
  exit 1
fi

log "corpus before:"
corpus_summary | tee -a "$LOG"

# --- run --------------------------------------------------------------------
# --publish makes the batch visible: map, pin, rebuild metrics and scores, and
# invalidate the semantic cache. Without it an ingest lands raw facts that no
# public surface can see.
ARGS=("$MODE" "$@")
if [[ "$MODE" != "publish" ]] && [[ ! " $* " =~ " --publish " ]]; then
  ARGS+=("--publish")
fi

log "running: python -m worker.acquire.cli ${ARGS[*]}"
set +e
compose exec -T api python -m worker.acquire.cli "${ARGS[@]}" 2>&1 | tee -a "$LOG"
STATUS=${PIPESTATUS[0]}
set -e

if [[ $STATUS -ne 0 ]]; then
  log "FAILED: the acquisition CLI exited ${STATUS}. The snapshot above is the restore point."
  aws sns publish --region "$AWS_REGION" --topic-arn "$ALERTS_TOPIC_ARN" \
    --subject "BRSR Lens ${ENVIRONMENT} ingest failed" \
    --message "ingest.sh ${MODE} exited ${STATUS} on ${DOMAIN_NAME}. See /opt/brsrlens/log/ingest.log." >/dev/null 2>&1 || true
  exit $STATUS
fi

# --- verify -----------------------------------------------------------------
log "corpus after:"
corpus_summary | tee -a "$LOG"

# The semantic layer caches query results in Redis. The CLI invalidates them,
# but a stale key here would show operators an unchanged site and send them
# hunting a non-existent ingest bug.
log "confirming the public query path reflects the new corpus"
if ! /opt/brsrlens/bin/smoke.sh >>"$LOG" 2>&1; then
  log "WARNING: post-ingest smoke did not pass. The corpus changed; review before announcing it."
  aws sns publish --region "$AWS_REGION" --topic-arn "$ALERTS_TOPIC_ARN" \
    --subject "BRSR Lens ${ENVIRONMENT} post-ingest smoke failed" \
    --message "ingest.sh ${MODE} completed but smoke.sh failed afterwards on ${DOMAIN_NAME}." >/dev/null 2>&1 || true
  exit 1
fi

log "SUCCESS"
cat <<'EOF'

Next, before treating these figures as publishable:
  1. Review any 'withheld' count above zero. A withheld value is an unresolved
     unit or turnover scale, not a gap in the filing. Add a reviewed registry
     entry with evidence in taxonomy/nse_concept_mappings.yaml, redeploy, then
     re-run `ingest.sh publish` -- no re-fetch is needed.
  2. Review new mappings at https://<domain>/admin/ingestion.
  3. Any 'missing' filing is a company with nothing published at the portal for
     that financial year. Confirm before reporting it as non-compliance.
EOF
