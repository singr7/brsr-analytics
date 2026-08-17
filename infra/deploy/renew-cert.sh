#!/usr/bin/env bash
# Obtain or renew the TLS certificate.
#
#   renew-cert.sh          renew if due (weekly cron; a no-op most weeks)
#   renew-cert.sh issue    first issuance, replacing the self-signed placeholder
#   renew-cert.sh staging  rehearse against Let's Encrypt staging, no rate limit
#
# Uses the webroot challenge against the running nginx rather than standalone
# mode, so the site never goes down to renew.
set -euo pipefail

source /opt/brsrlens/env/node.env

MODE="${1:-renew}"
EMAIL="$(aws ssm get-parameter --name "${SSM_PREFIX}/env/BILLING_OPS_EMAIL" \
  --region "$AWS_REGION" --query Parameter.Value --output text 2>/dev/null || echo "")"

log() { printf '[cert %s] %s\n' "$(date -u +%FT%TZ)" "$*"; }

certbot() {
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" \
    --profile certbot run --rm certbot "$@"
}

case "$MODE" in
  issue|staging)
    if [[ -z "$EMAIL" || "$EMAIL" == "CHANGE_ME" ]]; then
      log "set ${SSM_PREFIX}/env/BILLING_OPS_EMAIL first: Let's Encrypt requires a contact address for expiry warnings"
      exit 1
    fi

    STAGING_FLAG=()
    [[ "$MODE" == "staging" ]] && STAGING_FLAG=(--staging)

    log "requesting a certificate for ${DOMAIN_NAME} (${MODE})"
    # DNS must already resolve to this node: Let's Encrypt fetches the challenge
    # over the public internet, not from localhost.
    certbot certonly --webroot -w /var/www/certbot \
      -d "${DOMAIN_NAME}" \
      --email "${EMAIL}" \
      --agree-tos --no-eff-email --non-interactive \
      --keep-until-expiring \
      "${STAGING_FLAG[@]}"

    log "reloading nginx to pick up the new certificate"
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T web nginx -s reload
    log "done. Verify from outside: curl -sI https://${DOMAIN_NAME} | head -1"
    ;;

  renew)
    # certbot exits 0 when nothing is due, so this is safe to run weekly.
    if certbot renew --webroot -w /var/www/certbot --quiet; then
      docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T web nginx -s reload || true
      log "renewal check complete"
    else
      log "FAILED: renewal returned non-zero"
      aws sns publish --region "$AWS_REGION" --topic-arn "$ALERTS_TOPIC_ARN" \
        --subject "BRSR Lens ${ENVIRONMENT} certificate renewal failed" \
        --message "certbot renew failed for ${DOMAIN_NAME}. The certificate will expire if this is not fixed." >/dev/null 2>&1 || true
      exit 1
    fi
    ;;

  *)
    log "usage: renew-cert.sh {issue|renew|staging}"
    exit 2
    ;;
esac
