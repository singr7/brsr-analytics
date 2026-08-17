variable "project" {
  description = "Resource name prefix."
  type        = string
  default     = "brsrlens"
}

variable "environment" {
  description = "Environment name. Use a separate AWS account or a distinct value for the sandbox rehearsal estate."
  type        = string
  default     = "prod"

  validation {
    condition     = can(regex("^[a-z0-9-]{2,16}$", var.environment))
    error_message = "environment must be lowercase alphanumeric with hyphens, 2-16 characters."
  }
}

variable "aws_region" {
  description = "AWS region. Mumbai keeps Indian regulatory filings in-country."
  type        = string
  default     = "ap-south-1"
}

variable "vpc_cidr" {
  description = "CIDR for the estate VPC."
  type        = string
  default     = "10.20.0.0/16"
}

variable "public_subnet_cidr" {
  description = "CIDR for the single public subnet holding the app node."
  type        = string
  default     = "10.20.1.0/24"
}

# ---------------------------------------------------------------------------
# Compute
# ---------------------------------------------------------------------------

variable "app_instance_type" {
  description = "App node size. t3.large for beta; bump to t3.xlarge at launch per DEPLOYMENT.md section 1."
  type        = string
  default     = "t3.large"
}

variable "app_root_volume_gb" {
  description = "Root gp3 volume size in GB. Holds Postgres data, object store and raw filings."
  type        = number
  default     = 100
}

variable "enable_batch_node" {
  description = "Start the optional batch worker node for corpus runs and reprocessing. Off by default; it exists to be turned on for a run and off again."
  type        = bool
  default     = false
}

variable "batch_instance_type" {
  description = "Batch node size, used only when enable_batch_node is true."
  type        = string
  default     = "c6i.xlarge"
}

variable "break_glass_ssh_cidrs" {
  description = "Emergency SSH allowlist. Leave empty in normal operation: access is via SSM Session Manager, which needs no inbound rule."
  type        = list(string)
  default     = []
}

# ---------------------------------------------------------------------------
# DNS and TLS
# ---------------------------------------------------------------------------

variable "domain_name" {
  description = "Public hostname the portal is served on, for example brsrlens.example.com. Certbot issues the certificate for this name on the node."
  type        = string
}

variable "create_dns_record" {
  description = "Create the A record in Route 53. Set false when DNS is managed elsewhere; the elastic_ip output is then pointed at the name manually."
  type        = bool
  default     = true
}

variable "route53_zone_id" {
  description = "Hosted zone id for domain_name. Required when create_dns_record is true."
  type        = string
  default     = ""

  validation {
    condition     = var.route53_zone_id == "" || can(regex("^Z[A-Z0-9]+$", var.route53_zone_id))
    error_message = "route53_zone_id must be a Route 53 hosted zone id such as Z1234567890ABC."
  }
}

# ---------------------------------------------------------------------------
# Alerting and cost
# ---------------------------------------------------------------------------

variable "alert_email" {
  description = "Address that receives CloudWatch alarms, budget alerts and the dead-man backup alarm. Confirm the SNS subscription email after the first apply."
  type        = string
}

variable "monthly_budget_usd" {
  description = "Monthly spend alarm threshold in USD, per DEPLOYMENT.md section 6."
  type        = number
  default     = 300
}

# ---------------------------------------------------------------------------
# Retention
# ---------------------------------------------------------------------------

variable "backup_retention_days" {
  description = "Days to retain database backups in the backups bucket."
  type        = number
  default     = 30
}

variable "filings_ia_transition_days" {
  description = "Days before raw filings move to Infrequent Access storage."
  type        = number
  default     = 90
}

variable "ecr_image_retention_count" {
  description = "Number of tagged images to keep per ECR repository."
  type        = number
  default     = 10
}
