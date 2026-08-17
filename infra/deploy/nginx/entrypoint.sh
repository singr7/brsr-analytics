#!/bin/sh
# Runs before nginx starts, from the stock nginx image's /docker-entrypoint.d hook.
#
# nginx refuses to start when ssl_certificate points at a file that does not
# exist, and certbot cannot obtain that file until nginx is already serving the
# ACME challenge on port 80. This breaks that cycle by dropping in a self-signed
# placeholder on a first boot. Certbot overwrites it with the real certificate,
# and every later start finds the real one and leaves it alone.
set -eu

DOMAIN="${DOMAIN_NAME:?DOMAIN_NAME must be set}"
LIVE="/etc/letsencrypt/live/${DOMAIN}"

# The admin allowlist is rendered on the host by render-env.sh from the
# ADMIN_ALLOW_CIDRS parameter. nginx will not start if the include is missing,
# so guarantee a file exists even on a node that has never rendered one.
ALLOWLIST="/etc/nginx/extra/admin-allowlist.conf"
if [ ! -f "${ALLOWLIST}" ]; then
  mkdir -p /etc/nginx/extra
  echo "bootstrap-tls: no admin allowlist rendered, defaulting to role-gating only"
  printf '# No ADMIN_ALLOW_CIDRS set; /admin/* is protected by role checks alone.\nallow all;\n' > "${ALLOWLIST}"
fi

if [ -f "${LIVE}/fullchain.pem" ] && [ -f "${LIVE}/privkey.pem" ]; then
  echo "bootstrap-tls: using existing certificate for ${DOMAIN}"
  exit 0
fi

echo "bootstrap-tls: no certificate for ${DOMAIN}, generating a self-signed placeholder"
echo "bootstrap-tls: the site will show a certificate warning until certbot has run"

mkdir -p "${LIVE}"
openssl req -x509 -nodes -newkey rsa:2048 -days 30 \
  -keyout "${LIVE}/privkey.pem" \
  -out "${LIVE}/fullchain.pem" \
  -subj "/CN=${DOMAIN}" >/dev/null 2>&1

chmod 600 "${LIVE}/privkey.pem"
