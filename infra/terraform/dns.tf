resource "aws_route53_record" "app" {
  count = var.create_dns_record ? 1 : 0

  zone_id = var.route53_zone_id
  name    = var.domain_name
  type    = "A"
  ttl     = 60 # low so the record can be moved quickly during an incident
  records = [aws_eip.app.public_ip]

  lifecycle {
    precondition {
      condition     = var.route53_zone_id != ""
      error_message = "route53_zone_id is required when create_dns_record is true. Set create_dns_record = false to manage DNS elsewhere and point the record at the elastic_ip output."
    }
  }
}
