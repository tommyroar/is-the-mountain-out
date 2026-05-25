# R2 buckets and the public bucket's r2.dev managed domain + CORS rule.
#
# Both buckets were originally created via the Cloudflare dashboard /
# MCP (the v5 provider's earlier resource shapes were unstable, so
# cloudflare.tf was gutted in PR #63). Reclaiming them here so the
# dashboard isn't a second source of truth.
#
# The buckets already exist — they MUST be imported before the first
# apply or terraform will try to recreate them and fail. See README in
# this directory for the import commands.
#
# cloudflare_r2_bucket_cors and cloudflare_r2_managed_domain do NOT
# support `terraform import` in v5.19.1. The Cloudflare R2 API PUTs
# both as full replacements, so a fresh `apply` will just overwrite
# whatever the dashboard set — safe, and intended.

resource "cloudflare_r2_bucket" "captures" {
  account_id = var.cloudflare_account_id
  name       = "is-the-mountain-out"
}

resource "cloudflare_r2_bucket" "public" {
  account_id = var.cloudflare_account_id
  name       = "is-the-mountain-out-public"
}

resource "cloudflare_r2_managed_domain" "public" {
  account_id  = var.cloudflare_account_id
  bucket_name = cloudflare_r2_bucket.public.name
  enabled     = true
}

resource "cloudflare_r2_bucket_cors" "public" {
  account_id  = var.cloudflare_account_id
  bucket_name = cloudflare_r2_bucket.public.name

  rules = [{
    id              = "spa-and-local-dev"
    max_age_seconds = 3600
    allowed = {
      methods = ["GET", "HEAD"]
      origins = [
        "https://is-the-mountain-out.pages.dev",
        "http://localhost:5188",
      ]
      headers = ["*"]
    }
  }]
}
