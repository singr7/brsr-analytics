#!/usr/bin/env bash
# Post-deploy smoke test. Exit non-zero and deploy.sh rolls back.
#
# Runs against the node's own nginx over TLS, resolved locally, so it exercises
# the real vhost, the real static bundle and the real API without depending on
# DNS propagation or a valid certificate. Assertions are chosen to fail loudly
# on the mistakes that actually happen at deploy time: an empty database after a
# restore, a broken static bundle, a missing measure catalog, tier enforcement
# disabled, or the HTTPS redirect not being applied.
set -uo pipefail

# node.env supplies DOMAIN_NAME. Absent when running the script by hand against
# another target, in which case SMOKE_BASE_URL must be set explicitly.
[[ -f /opt/brsrlens/env/node.env ]] && source /opt/brsrlens/env/node.env

DOMAIN_NAME="${DOMAIN_NAME:-localhost}"
BASE="${SMOKE_BASE_URL:-https://${DOMAIN_NAME}}"
FAILED=0

# Resolve the public hostname to this node and accept the certificate as-is:
# the checks must exercise the real TLS vhost (where the redirect, the security
# headers and the proxy rules live) without waiting on DNS propagation, and a
# first deploy legitimately still has the self-signed placeholder.
curl() {
  command curl --insecure --resolve "${DOMAIN_NAME}:443:127.0.0.1" \
               --resolve "${DOMAIN_NAME}:80:127.0.0.1" "$@"
}

pass() { printf '  ok    %s\n' "$1"; }
fail() { printf '  FAIL  %s\n     -> %s\n' "$1" "$2"; FAILED=1; }

check() {
  local name="$1" actual="$2" expected="$3"
  if [[ "$actual" == "$expected" ]]; then pass "$name"; else fail "$name" "expected '${expected}', got '${actual}'"; fi
}

echo "smoke: ${BASE}"

# --- 1. health --------------------------------------------------------------
HEALTH="$(curl -fsS --max-time 10 "${BASE}/healthz" 2>/dev/null || echo '{}')"
check "healthz reports ok" "$(jq -r '.status // "unreachable"' <<<"$HEALTH")" "ok"
check "database reachable" "$(jq -r '.database.status // "unreachable"' <<<"$HEALTH")" "ok"
check "redis reachable" "$(jq -r '.redis.status // "unreachable"' <<<"$HEALTH")" "ok"
check "llm configured" "$(jq -r '.llm_config.status // "unreachable"' <<<"$HEALTH")" "ok"

# --- 2. static bundle -------------------------------------------------------
HOME_STATUS="$(curl -fsS -o /tmp/smoke-home.html -w '%{http_code}' --max-time 10 "${BASE}/" || echo 000)"
check "home page served" "$HOME_STATUS" "200"
if grep -qi 'brsr' /tmp/smoke-home.html 2>/dev/null; then
  pass "home page contains the app shell"
else
  fail "home page contains the app shell" "no 'brsr' marker in the response body"
fi

# Prerendered public route: proves the build ran the prerender pass and that the
# nginx directory fallback works, which is what makes these pages indexable.
check "prerendered /sectors" \
  "$(curl -fsS -o /dev/null -w '%{http_code}' --max-time 10 "${BASE}/sectors" || echo 000)" "200"

# --- 3. public API ----------------------------------------------------------
check "plans endpoint" \
  "$(curl -fsS --max-time 10 "${BASE}/api/plans" 2>/dev/null | jq -r '.tiers | keys | length' || echo 0)" "4"

CATALOG_VERSION="$(curl -fsS --max-time 10 "${BASE}/api/catalog" 2>/dev/null | jq -r '.catalog_version // .version // ""')"
if [[ -n "$CATALOG_VERSION" && "$CATALOG_VERSION" != "null" ]]; then
  pass "measure catalog published (${CATALOG_VERSION})"
else
  fail "measure catalog published" "no version in /api/catalog"
fi

check "methodology endpoint" \
  "$(curl -fsS -o /dev/null -w '%{http_code}' --max-time 10 "${BASE}/api/methodology" || echo 000)" "200"

# --- 4. the corpus is actually there ---------------------------------------
# The single most valuable assertion here. A stack can be perfectly healthy and
# serving an empty database after a failed restore or a migration onto a fresh
# volume; every public surface would then render as "no data" rather than error.
QUERY='{"measures":["completeness"],"dimensions":["sector"],"filters":[{"dimension":"fy","operator":"eq","value":2025}],"shape":"distribution","limit":20}'
ROWS="$(curl -fsS --max-time 20 -X POST "${BASE}/api/query" \
  -H 'content-type: application/json' -d "$QUERY" 2>/dev/null | jq -r '.data | length' || echo 0)"

if [[ "${ROWS:-0}" -ge 1 ]]; then
  pass "governed query returns data (${ROWS} sector rows)"
else
  fail "governed query returns data" "0 rows: the corpus is empty or the query path is broken"
fi

# --- 5. tier enforcement is live -------------------------------------------
# Anonymous company-level access must be refused by policy, not by an error.
# If this ever passes silently, paid company detail is public.
GATE="$(curl -fsS --max-time 20 -X POST "${BASE}/api/query" \
  -H 'content-type: application/json' \
  -d '{"measures":["p6.e1.energy_total_gj"],"dimensions":["company"],"filters":[{"dimension":"fy","operator":"eq","value":2025}],"shape":"ranking","limit":3}' 2>/dev/null)"
GATE_ROWS="$(jq -r '.data | length' <<<"$GATE" 2>/dev/null || echo -1)"
GATE_CODE="$(jq -r '.applied_policy[0].code // ""' <<<"$GATE" 2>/dev/null || echo "")"

if [[ "$GATE_ROWS" == "0" && -n "$GATE_CODE" ]]; then
  pass "anonymous company detail is gated (${GATE_CODE})"
else
  fail "anonymous company detail is gated" "returned ${GATE_ROWS} rows with policy '${GATE_CODE}'"
fi

# --- 6. transport and security headers --------------------------------------
# Plain HTTP must redirect rather than serve. nginx merges add_header per level,
# so a location that sets its own header silently drops the inherited set --
# these checks are what catch that regression.
REDIRECT="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "http://${DOMAIN_NAME}/" || echo 000)"
check "http redirects to https" "$REDIRECT" "301"

HEADERS="$(curl -fsS -o /dev/null -D - --max-time 10 "${BASE}/" 2>/dev/null || true)"
for header in "strict-transport-security" "x-content-type-options" "x-frame-options" "content-security-policy"; do
  if grep -qi "^${header}:" <<<"$HEADERS"; then
    pass "header ${header}"
  else
    fail "header ${header}" "not present on the home page response"
  fi
done

echo
if [[ $FAILED -eq 0 ]]; then
  echo "smoke: PASS"
else
  echo "smoke: FAIL"
fi
exit $FAILED
