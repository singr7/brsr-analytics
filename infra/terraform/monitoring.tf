resource "aws_sns_topic" "alerts" {
  name = "${local.name}-alerts"
}

resource "aws_sns_topic_subscription" "alerts_email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email

  # AWS sends a confirmation mail. Until it is accepted the subscription stays
  # PendingConfirmation and no alarm reaches anyone -- check after first apply.
}

resource "aws_cloudwatch_metric_alarm" "app_status_check" {
  alarm_name          = "${local.name}-app-status-check"
  alarm_description   = "App node failed an EC2 or system status check."
  namespace           = "AWS/EC2"
  metric_name         = "StatusCheckFailed"
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 2
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "breaching"

  dimensions    = { InstanceId = aws_instance.app.id }
  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "app_cpu" {
  alarm_name          = "${local.name}-app-cpu-high"
  alarm_description   = "Sustained CPU pressure on the app node. Usually an extraction batch running on the wrong node."
  namespace           = "AWS/EC2"
  metric_name         = "CPUUtilization"
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 3
  threshold           = 85
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  dimensions    = { InstanceId = aws_instance.app.id }
  alarm_actions = [aws_sns_topic.alerts.arn]
}

# Published by the CloudWatch agent installed in cloud-init. Raw filings and the
# object store grow with every cohort; disk exhaustion stops Postgres first.
resource "aws_cloudwatch_metric_alarm" "app_disk" {
  alarm_name          = "${local.name}-app-disk-high"
  alarm_description   = "Data volume above 80% used on the app node."
  namespace           = "CWAgent"
  metric_name         = "disk_used_percent"
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 2
  threshold           = 80
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    InstanceId = aws_instance.app.id
    path       = "/opt/brsrlens/data"
    fstype     = "xfs"
    device     = "nvme1n1"
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "app_memory" {
  alarm_name          = "${local.name}-app-memory-high"
  alarm_description   = "Memory pressure on the app node. The compose memory split assumes headroom above this."
  namespace           = "CWAgent"
  metric_name         = "mem_used_percent"
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 3
  threshold           = 90
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  dimensions    = { InstanceId = aws_instance.app.id }
  alarm_actions = [aws_sns_topic.alerts.arn]
}

# ---------------------------------------------------------------------------
# Dead-man backup alarm
#
# backup.sh publishes BackupSucceeded=1 after every successful upload. Missing
# data is treated as breaching, so a backup that silently stops running raises
# the alarm rather than staying invisible until a restore is needed.
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "backup_deadman" {
  alarm_name          = "${local.name}-backup-missed"
  alarm_description   = "No successful database backup reported in the last 36 hours."
  namespace           = "BRSRLens/Ops"
  metric_name         = "BackupSucceeded"
  statistic           = "Sum"
  period              = 43200
  evaluation_periods  = 3
  threshold           = 1
  comparison_operator = "LessThanThreshold"
  treat_missing_data  = "breaching"

  dimensions    = { Environment = var.environment }
  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_log_group" "app" {
  name              = "/${var.project}/${var.environment}/app"
  retention_in_days = 30
}

# ---------------------------------------------------------------------------
# Cost guardrail
# ---------------------------------------------------------------------------

resource "aws_budgets_budget" "monthly" {
  name         = "${local.name}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.alert_email]
  }
}
