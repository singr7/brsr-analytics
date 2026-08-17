resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = "${local.name}-vpc" }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${local.name}-igw" }
}

data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_subnet" "public" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.public_subnet_cidr
  availability_zone = data.aws_availability_zones.available.names[0]

  # Single public subnet with no NAT gateway, per DEPLOYMENT.md section 1. The
  # app node's public address is the Elastic IP; the batch node relies on this
  # auto-assignment for its egress-only access to ECR and the LLM provider.
  map_public_ip_on_launch = true

  tags = { Name = "${local.name}-public" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = { Name = "${local.name}-public" }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

# S3 traffic (image layers, backups, raw filings) stays on the AWS network and
# off the NAT-free public path, which also keeps it out of the data transfer bill.
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.public.id]

  tags = { Name = "${local.name}-s3-endpoint" }
}

# ---------------------------------------------------------------------------
# Security groups
# ---------------------------------------------------------------------------

resource "aws_security_group" "app" {
  name        = "${local.name}-app"
  description = "App node: public HTTP and HTTPS in, everything out. No SSH in normal operation."
  vpc_id      = aws_vpc.main.id

  tags = { Name = "${local.name}-app" }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_vpc_security_group_ingress_rule" "app_http" {
  security_group_id = aws_security_group.app.id
  description       = "HTTP, redirected to HTTPS by nginx and used for ACME challenges"
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "app_https" {
  security_group_id = aws_security_group.app.id
  description       = "HTTPS"
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
}

# Present only when break_glass_ssh_cidrs is non-empty. Normal access is SSM
# Session Manager, which requires no inbound rule at all.
resource "aws_vpc_security_group_ingress_rule" "app_break_glass_ssh" {
  for_each = toset(var.break_glass_ssh_cidrs)

  security_group_id = aws_security_group.app.id
  description       = "Break-glass SSH"
  cidr_ipv4         = each.value
  from_port         = 22
  to_port           = 22
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "app_all" {
  security_group_id = aws_security_group.app.id
  description       = "Outbound to NSE sources, ECR, S3, SES and the LLM provider"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

resource "aws_security_group" "batch" {
  name        = "${local.name}-batch"
  description = "Batch node: no inbound, egress only. Reaches Postgres and Redis on the app node via a security-group rule."
  vpc_id      = aws_vpc.main.id

  tags = { Name = "${local.name}-batch" }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_vpc_security_group_egress_rule" "batch_all" {
  security_group_id = aws_security_group.batch.id
  description       = "Outbound only"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

resource "aws_vpc_security_group_ingress_rule" "app_from_batch_postgres" {
  security_group_id            = aws_security_group.app.id
  description                  = "Postgres from the batch node"
  referenced_security_group_id = aws_security_group.batch.id
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "app_from_batch_redis" {
  security_group_id            = aws_security_group.app.id
  description                  = "Redis from the batch node"
  referenced_security_group_id = aws_security_group.batch.id
  from_port                    = 6379
  to_port                      = 6379
  ip_protocol                  = "tcp"
}
