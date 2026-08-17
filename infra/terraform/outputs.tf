output "app_instance_id" {
  description = "Target for every ops command. Export as BRSRLENS_INSTANCE_ID for ops/bin/brsrlens-prod."
  value       = aws_instance.app.id
}

output "batch_instance_id" {
  description = "Batch node id, or null while enable_batch_node is false."
  value       = try(aws_instance.batch[0].id, null)
}

output "elastic_ip" {
  description = "Stable public address. Point the DNS A record here when create_dns_record is false."
  value       = aws_eip.app.public_ip
}

output "site_url" {
  description = "Public URL once DNS resolves and certbot has issued the certificate."
  value       = "https://${var.domain_name}"
}

output "ecr_repositories" {
  description = "Image repositories to build and push into."
  value       = { for k, r in aws_ecr_repository.this : k => r.repository_url }
}

output "buckets" {
  description = "Raw filings, generated artifacts and database backups."
  value       = { for k, b in aws_s3_bucket.this : k => b.id }
}

output "ssm_env_path" {
  description = "Parameter Store path the node renders its .env from."
  value       = local.env_path
}

output "unset_parameters_command" {
  description = "Lists operator parameters still holding the CHANGE_ME placeholder. Run before the first deploy."
  value       = "aws ssm get-parameters-by-path --path ${local.env_path} --with-decryption --region ${var.aws_region} --query \"Parameters[?Value=='CHANGE_ME'].Name\" --output text"
}

output "alerts_topic_arn" {
  description = "SNS topic for alarms. Confirm the email subscription after the first apply."
  value       = aws_sns_topic.alerts.arn
}

output "deployer_role_arn" {
  description = "Role CI assumes to push images and start a deployment."
  value       = aws_iam_role.deployer.arn
}

output "next_steps" {
  description = "Ordered follow-up after a successful apply."
  value = join("\n", [
    "1. Confirm the SNS subscription email sent to ${var.alert_email}.",
    "2. Set every operator parameter still reading CHANGE_ME (see unset_parameters_command).",
    "3. Point ${var.domain_name} at ${aws_eip.app.public_ip}${var.create_dns_record ? " (this apply created the record)" : " (DNS is managed outside Terraform)"}.",
    "4. Build and push images, then run: ops/bin/brsrlens-prod deploy <tag>",
    "5. Follow docs/operations/PRODUCTION_DEPLOYMENT.md from step 6 for TLS, the admin account and the corpus run.",
  ])
}
