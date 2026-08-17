locals {
  buckets = {
    filings   = "${var.project}-filings-raw-${local.bucket_suffix}"
    artifacts = "${var.project}-artifacts-${local.bucket_suffix}"
    backups   = "${var.project}-backups-${local.bucket_suffix}"
  }
}

resource "aws_s3_bucket" "this" {
  for_each = local.buckets
  bucket   = each.value

  tags = { Name = each.value, Role = each.key }
}

resource "aws_s3_bucket_versioning" "this" {
  for_each = aws_s3_bucket.this
  bucket   = each.value.id

  versioning_configuration {
    status = "Enabled"
  }
}

# AES256 rather than KMS: api/app/services/storage.py signs its own SigV4 PUT
# requests with x-amz-server-side-encryption: AES256. Switching to KMS here
# without changing that header makes every upload fail the bucket policy.
resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  for_each = aws_s3_bucket.this
  bucket   = each.value.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "this" {
  for_each = aws_s3_bucket.this
  bucket   = each.value.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Private analysis uploads and Studio documents live in artifacts. Refusing
# unencrypted and non-TLS writes is what makes the privacy promise enforceable
# rather than aspirational.
resource "aws_s3_bucket_policy" "deny_insecure" {
  for_each = aws_s3_bucket.this
  bucket   = each.value.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyInsecureTransport"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          each.value.arn,
          "${each.value.arn}/*",
        ]
        Condition = {
          Bool = { "aws:SecureTransport" = "false" }
        }
      },
      {
        Sid       = "DenyUnencryptedObjectUploads"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:PutObject"
        Resource  = "${each.value.arn}/*"
        Condition = {
          StringNotEquals = { "s3:x-amz-server-side-encryption" = "AES256" }
        }
      },
    ]
  })

  depends_on = [aws_s3_bucket_public_access_block.this]
}

resource "aws_s3_bucket_lifecycle_configuration" "filings" {
  bucket = aws_s3_bucket.this["filings"].id

  rule {
    id     = "raw-filings-to-ia"
    status = "Enabled"

    filter {}

    transition {
      days          = var.filings_ia_transition_days
      storage_class = "STANDARD_IA"
    }

    # Raw filings are immutable evidence: old versions are kept long enough to
    # recover from an operator error, then dropped.
    noncurrent_version_expiration {
      noncurrent_days = 90
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "backups" {
  bucket = aws_s3_bucket.this["backups"].id

  rule {
    id     = "expire-backups"
    status = "Enabled"

    filter {}

    expiration {
      days = var.backup_retention_days
    }

    noncurrent_version_expiration {
      noncurrent_days = 7
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 3
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "artifacts" {
  bucket = aws_s3_bucket.this["artifacts"].id

  rule {
    id     = "expire-old-artifact-versions"
    status = "Enabled"

    filter {}

    noncurrent_version_expiration {
      noncurrent_days = 30
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 3
    }
  }
}
