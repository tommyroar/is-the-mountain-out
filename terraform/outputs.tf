output "r2_bucket_name" {
  description = "Name of the R2 bucket"
  value       = cloudflare_r2_bucket.captures.name
}

output "r2_endpoint" {
  description = "S3-compatible endpoint for boto3"
  value       = "https://${var.cloudflare_account_id}.r2.cloudflarestorage.com"
}

output "inference_worker_name" {
  description = "Cloudflare Worker that runs the */15 mountain-inference cron"
  value       = "mountain-inference"
}

output "inference_image" {
  description = "Container image the Worker pulls for inference"
  value       = local.inference_image
}
