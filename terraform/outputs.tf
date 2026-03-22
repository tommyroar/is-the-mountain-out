output "r2_bucket_name" {
  description = "Name of the R2 bucket"
  value       = cloudflare_r2_bucket.captures.name
}

output "r2_endpoint" {
  description = "S3-compatible endpoint for boto3"
  value       = "https://${var.cloudflare_account_id}.r2.cloudflarestorage.com"
}
