# Runtime configuration lives in Parameter Store, never in the AMI, the image or
# the repository. render-env.sh on the node reads everything under
# ${local.prefix}/env/ and writes it to /opt/brsrlens/env/.env before each start.
#
# Two kinds of parameter:
#   * derived  - Terraform owns the value because the estate determines it.
#   * operator - Terraform creates the parameter once with a placeholder and then
#                ignores its value. Real secrets are written with `aws ssm
#                put-parameter --overwrite` and never appear in state or a plan.

locals {
  env_path = "${local.prefix}/env"

  derived_env = {
    APP_ENV      = "production"
    LOG_LEVEL    = "INFO"
    FRONTEND_URL = "https://${var.domain_name}"

    AWS_REGION           = var.aws_region
    OBJECT_STORE_BACKEND = "s3"
    FILINGS_BUCKET       = aws_s3_bucket.this["filings"].id
    ARTIFACTS_BUCKET     = aws_s3_bucket.this["artifacts"].id
    BACKUPS_BUCKET       = aws_s3_bucket.this["backups"].id

    # Postgres and Redis run in the compose stack on this node.
    REDIS_URL = "redis://redis:6379/0"

    # The verification-token escape hatch and the fixture LLM are both rejected
    # by Settings validation when APP_ENV=production. Pinned here so a stray
    # value cannot re-enable them.
    AUTH_EXPOSE_VERIFICATION_TOKEN = "false"

    # Legal gate. Acquisition stays fail-closed until docs/gates/legal.md is
    # signed; flipping this parameter is the signature's technical expression.
    SOURCE_NSE_BRSR_ENABLED = "false"

    # Scheduled refresh stays off until the first supervised manual cohort run
    # has been reviewed.
    NSE_BRSR_SCHEDULE_ENABLED   = "false"
    NSE_BRSR_REFRESH_HOURS      = "168"
    NSE_BRSR_DEFAULT_FY         = "2025"
    NSE_BRSR_DEFAULT_BATCH_SIZE = "10"

    ACQUISITION_RATE_PER_SECOND  = "0.5"
    PUBLIC_RATE_LIMIT_PER_MINUTE = "120"
    ORG_RATE_LIMIT_PER_MINUTE    = "600"

    SMTP_HOST = "email-smtp.${var.aws_region}.amazonaws.com"
    SMTP_PORT = "587"

    VITE_API_URL = "https://${var.domain_name}"
  }

  # Placeholders only. Set real values out of band before the first deploy;
  # deploy.sh refuses to start the stack while any of them is still CHANGE_ME.
  operator_env = [
    "JWT_SECRET",
    # DATABASE_URL is deliberately absent: render-env.sh builds it on the node
    # from POSTGRES_USER/POSTGRES_PASSWORD/POSTGRES_DB, so the connection string
    # and the database's own password cannot drift apart.
    "POSTGRES_PASSWORD",
    "EMAIL_FROM",
    "SMTP_USER",
    "SMTP_PASSWORD",
    "LLM_PROVIDER",
    "LLM_API_KEY",
    "LLM_BASE_URL",
    "LLM_MODEL",
    "NSE_BRSR_CONTACT",
    "LEAD_RECIPIENT_EMAIL",
    "LEAD_WEBHOOK_URL",
    "LEAD_WEBHOOK_SECRET",
    "ANALYTICS_DIGEST_RECIPIENTS",
    "BILLING_OPS_EMAIL",
  ]
}

resource "aws_ssm_parameter" "derived" {
  for_each = local.derived_env

  name  = "${local.env_path}/${each.key}"
  type  = "String"
  value = each.value

  tags = { Name = each.key, Origin = "terraform" }
}

resource "aws_ssm_parameter" "operator" {
  for_each = toset(local.operator_env)

  name        = "${local.env_path}/${each.value}"
  type        = "SecureString"
  value       = "CHANGE_ME"
  description = "Operator-managed. Set with: aws ssm put-parameter --name ${local.env_path}/${each.value} --type SecureString --overwrite --value ..."

  lifecycle {
    # Terraform must never own, print or diff a live secret.
    ignore_changes = [value]
  }

  tags = { Name = each.value, Origin = "operator" }
}

# Release pointers. deploy.sh writes the tag it is rolling out to 'current' and
# moves the previous value to 'prev', which is what rollback.sh reads.
resource "aws_ssm_parameter" "release_current" {
  name  = "${local.prefix}/release/current"
  type  = "String"
  value = "bootstrap"

  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_ssm_parameter" "release_prev" {
  name  = "${local.prefix}/release/prev"
  type  = "String"
  value = "bootstrap"

  lifecycle {
    ignore_changes = [value]
  }
}
