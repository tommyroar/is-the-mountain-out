output "r2_endpoint" {
  description = "S3-compatible endpoint for boto3"
  value       = "https://${var.cloudflare_account_id}.r2.cloudflarestorage.com"
}

output "r2_public_bucket_url" {
  description = "Managed r2.dev URL for the public state/history bucket"
  value       = "https://${cloudflare_r2_managed_domain.public.domain}"
}

output "pages_subdomain" {
  description = "Cloudflare-assigned *.pages.dev subdomain for the SPA"
  value       = "https://${cloudflare_pages_project.spa.subdomain}"
}

output "inference_worker_name" {
  description = "Cloudflare Worker that runs the */15 mountain-inference cron"
  value       = "mountain-inference"
}

output "inference_image" {
  description = "Container image the Worker pulls for inference"
  value       = local.inference_image
}
