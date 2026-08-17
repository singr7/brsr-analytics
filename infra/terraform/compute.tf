data "aws_ssm_parameter" "al2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-6.1-x86_64"
}

locals {
  node_user_data = templatefile("${path.module}/../cloudinit/app-node.yaml.tftpl", {
    project        = var.project
    environment    = var.environment
    aws_region     = var.aws_region
    ssm_prefix     = local.prefix
    domain_name    = var.domain_name
    account_id     = data.aws_caller_identity.current.account_id
    alerts_topic   = aws_sns_topic.alerts.arn
    backups_bucket = aws_s3_bucket.this["backups"].id
    data_device    = "/dev/sdf"
  })
}

# ---------------------------------------------------------------------------
# App node
# ---------------------------------------------------------------------------

resource "aws_instance" "app" {
  ami                    = data.aws_ssm_parameter.al2023.value
  instance_type          = var.app_instance_type
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.app.id]
  iam_instance_profile   = aws_iam_instance_profile.node.name

  # No key pair. Shell access is SSM Session Manager only.
  user_data                   = local.node_user_data
  user_data_replace_on_change = false

  metadata_options {
    http_tokens                 = "required" # IMDSv2 only
    http_endpoint               = "enabled"
    http_put_response_hop_limit = 2 # containers reach IMDS for the instance role
    instance_metadata_tags      = "enabled"
  }

  root_block_device {
    volume_type           = "gp3"
    volume_size           = 30
    encrypted             = true
    delete_on_termination = true
    tags                  = { Name = "${local.name}-app-root" }
  }

  monitoring = true

  tags = { Name = "${local.name}-app", Role = "app" }

  lifecycle {
    # The AMI parameter resolves to a newer image every few weeks. Replacing the
    # node on that alone would destroy the running stack; OS updates are applied
    # in place by dnf-automatic and a rebuild is a deliberate operator action.
    ignore_changes = [ami]
  }
}

# The corpus, the object store and every backup staging file live here rather
# than on the root volume, so the node can be rebuilt without losing the
# database that took a supervised cohort run to produce.
resource "aws_ebs_volume" "data" {
  availability_zone = aws_subnet.public.availability_zone
  size              = var.app_root_volume_gb
  type              = "gp3"
  encrypted         = true

  tags = { Name = "${local.name}-data" }

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_volume_attachment" "data" {
  device_name = "/dev/sdf"
  volume_id   = aws_ebs_volume.data.id
  instance_id = aws_instance.app.id

  # Detaching a mounted filesystem corrupts it. Stop the stack first.
  stop_instance_before_detaching = true
}

resource "aws_eip" "app" {
  domain   = "vpc"
  instance = aws_instance.app.id

  tags = { Name = "${local.name}-app" }

  depends_on = [aws_internet_gateway.main]
}

# ---------------------------------------------------------------------------
# Optional batch node
#
# Off by default. Turned on for a corpus run or an annual reprocess, then turned
# off again: it exists so a long extraction batch never competes with the public
# site for the app node's memory.
# ---------------------------------------------------------------------------

resource "aws_instance" "batch" {
  count = var.enable_batch_node ? 1 : 0

  ami                    = data.aws_ssm_parameter.al2023.value
  instance_type          = var.batch_instance_type
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.batch.id]
  iam_instance_profile   = aws_iam_instance_profile.node.name
  user_data              = local.node_user_data

  metadata_options {
    http_tokens                 = "required"
    http_endpoint               = "enabled"
    http_put_response_hop_limit = 2
  }

  root_block_device {
    volume_type           = "gp3"
    volume_size           = 100
    encrypted             = true
    delete_on_termination = true
  }

  tags = { Name = "${local.name}-batch", Role = "batch" }

  lifecycle {
    ignore_changes = [ami]
  }
}
