locals {
  # api runs the FastAPI app, the Celery worker and the Beat scheduler from one
  # image. web is nginx with the prerendered frontend bundle baked in.
  ecr_repositories = ["api", "web"]
}

resource "aws_ecr_repository" "this" {
  for_each = toset(local.ecr_repositories)

  name                 = "${var.project}/${each.value}"
  image_tag_mutability = "MUTABLE" # the deploy flow retags 'current' and 'prev'

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = { Name = "${var.project}/${each.value}" }
}

resource "aws_ecr_lifecycle_policy" "this" {
  for_each   = aws_ecr_repository.this
  repository = each.value.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep the rollback target and recent releases"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["sha-"]
          countType     = "imageCountMoreThan"
          countNumber   = var.ecr_image_retention_count
        }
        action = { type = "expire" }
      },
      {
        rulePriority = 2
        description  = "Expire untagged layers left by interrupted pushes"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 7
        }
        action = { type = "expire" }
      },
    ]
  })
}
