terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
  }

  # Remote state. Copy backend.tf.example to backend.tf and fill in the bucket
  # created by the bootstrap step in docs/operations/PRODUCTION_DEPLOYMENT.md.
  # Left unconfigured here so `terraform init` works before the bucket exists.
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "brsrlens"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

data "aws_caller_identity" "current" {}

locals {
  name   = "${var.project}-${var.environment}"
  prefix = "/${var.project}/${var.environment}"

  # Buckets must be globally unique. The account id keeps the estate reproducible
  # in a second (sandbox) account without renaming anything.
  bucket_suffix = "${var.environment}-${data.aws_caller_identity.current.account_id}"
}
