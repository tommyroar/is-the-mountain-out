terraform {
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 5.0"
    }
  }
}

provider "cloudflare" {
  api_token = var.cloudflare_api_token
}

# ---------- R2 Bucket ----------

resource "cloudflare_r2_bucket" "captures" {
  account_id = var.cloudflare_account_id
  name       = "is-the-mountain-out-captures"
  location   = "WNAM" # Western North America — closest to Seattle
}

# ---------- Permission groups data source ----------

data "cloudflare_api_token_permission_groups" "all" {}

# ---------- Scoped API token for R2 read/write ----------

resource "cloudflare_api_token" "r2_rw" {
  name = "mountain-r2-readwrite"

  policy {
    permission_groups = [
      data.cloudflare_api_token_permission_groups.all.account["Workers R2 Storage Read"],
      data.cloudflare_api_token_permission_groups.all.account["Workers R2 Storage Write"],
    ]
    resources = {
      "com.cloudflare.api.account.${var.cloudflare_account_id}" = "*"
    }
  }
}

# ---------- S3-compatible credentials via Cloudflare API ----------
# The Terraform provider lacks a native resource for R2 S3 API tokens,
# so we create one via local-exec and write it to a .env file.

resource "null_resource" "r2_s3_credentials" {
  depends_on = [cloudflare_r2_bucket.captures]

  provisioner "local-exec" {
    command = <<-EOT
      curl -sf -X POST \
        "https://api.cloudflare.com/client/v4/accounts/${var.cloudflare_account_id}/r2/tokens" \
        -H "Authorization: Bearer ${var.cloudflare_api_token}" \
        -H "Content-Type: application/json" \
        -d '${jsonencode({
    name        = "mountain-s3-access"
    permissions = ["object-read-write"]
    buckets     = [cloudflare_r2_bucket.captures.name]
})}' \
        | jq -r '.result | "R2_ACCESS_KEY_ID=\(.id)\nR2_SECRET_ACCESS_KEY=\(.value)"' \
        > "${path.module}/r2_credentials.env"
    EOT
}

triggers = {
  bucket = cloudflare_r2_bucket.captures.name
}
}
