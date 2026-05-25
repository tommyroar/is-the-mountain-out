# Cloudflare provider config.
#
# R2 buckets, CORS, managed domain, and the Pages project live in
# r2.tf and pages.tf. The R2 S3-API token (used by the inference
# container) is still cut manually in the dashboard — the v5
# provider's cloudflare_api_token policy block has been unstable
# across minor versions and the value moves through the Worker as a
# secret either way.

provider "cloudflare" {
  api_token = var.cloudflare_api_token
}
