# Cloudflare provider config. The R2 buckets (is-the-mountain-out,
# is-the-mountain-out-public) and the R2 S3-API token are managed
# manually via the Cloudflare dashboard / MCP — see PR notes. This file
# only configures the provider so cloudflare_worker.tf can deploy the
# Worker.

provider "cloudflare" {
  api_token = var.cloudflare_api_token
}
