data "aws_iam_policy_document" "ec2_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "node" {
  name               = "${local.name}-node"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

# Session Manager shell access, so the estate needs no SSH ingress and no key pair.
resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy_attachment" "cloudwatch_agent" {
  role       = aws_iam_role.node.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

data "aws_iam_policy_document" "node" {
  statement {
    sid    = "ReadWriteBuckets"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:GetObjectVersion",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:AbortMultipartUpload",
      "s3:ListBucket",
      "s3:ListBucketMultipartUploads",
      "s3:GetBucketLocation",
    ]
    resources = concat(
      [for b in aws_s3_bucket.this : b.arn],
      [for b in aws_s3_bucket.this : "${b.arn}/*"],
    )
  }

  statement {
    sid    = "ReadRuntimeParameters"
    effect = "Allow"
    actions = [
      "ssm:GetParameter",
      "ssm:GetParameters",
      "ssm:GetParametersByPath",
    ]
    resources = [
      "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${local.prefix}",
      "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${local.prefix}/*",
    ]
  }

  statement {
    sid       = "DecryptParameters"
    effect    = "Allow"
    actions   = ["kms:Decrypt"]
    resources = ["arn:aws:kms:${var.aws_region}:${data.aws_caller_identity.current.account_id}:alias/aws/ssm"]
  }

  statement {
    sid    = "PullImages"
    effect = "Allow"
    actions = [
      "ecr:GetAuthorizationToken",
      "ecr:BatchCheckLayerAvailability",
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage",
      "ecr:DescribeImages",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "SendTransactionalMail"
    effect = "Allow"
    actions = [
      "ses:SendEmail",
      "ses:SendRawEmail",
    ]
    resources = ["*"]
  }

  # The deploy and ingest scripts report their own outcome to the operator topic.
  statement {
    sid       = "PublishAlerts"
    effect    = "Allow"
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.alerts.arn]
  }
}

resource "aws_iam_role_policy" "node" {
  name   = "${local.name}-node"
  role   = aws_iam_role.node.id
  policy = data.aws_iam_policy_document.node.json
}

resource "aws_iam_instance_profile" "node" {
  name = "${local.name}-node"
  role = aws_iam_role.node.name
}

# ---------------------------------------------------------------------------
# CI deployer
#
# Assumed by GitHub Actions through OIDC, so no long-lived keys exist. It can
# push images and start a deployment; it cannot read application data.
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "deployer_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }
  }
}

resource "aws_iam_role" "deployer" {
  name               = "${local.name}-deployer"
  assume_role_policy = data.aws_iam_policy_document.deployer_assume.json

  description = "Build and release role. Attach a GitHub OIDC trust statement before wiring CI; see infra/terraform/README.md."
}

data "aws_iam_policy_document" "deployer" {
  statement {
    sid       = "AuthenticateToRegistry"
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid    = "PushImages"
    effect = "Allow"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:CompleteLayerUpload",
      "ecr:InitiateLayerUpload",
      "ecr:PutImage",
      "ecr:UploadLayerPart",
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
      "ecr:DescribeImages",
    ]
    resources = [for r in aws_ecr_repository.this : r.arn]
  }

  statement {
    sid    = "TriggerDeployment"
    effect = "Allow"
    actions = [
      "ssm:SendCommand",
      "ssm:GetCommandInvocation",
      "ssm:ListCommandInvocations",
    ]
    resources = [
      aws_instance.app.arn,
      "arn:aws:ssm:${var.aws_region}::document/AWS-RunShellScript",
    ]
  }
}

resource "aws_iam_role_policy" "deployer" {
  name   = "${local.name}-deployer"
  role   = aws_iam_role.deployer.id
  policy = data.aws_iam_policy_document.deployer.json
}
