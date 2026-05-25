# Cloudflare Worker + Container that owns the */15 mountain inference cadence.
#
# The Worker (worker/src/index.ts) is bound to a Container running the
# inference Dockerfile (inference/Dockerfile). On each cron tick the Worker
# invokes the container's /predict endpoint and writes the result to the
# public R2 bucket the SPA reads from. The container itself pulls its
# checkpoint from R2 on startup using the R2 creds passed in as env vars.
#
# The Cloudflare Terraform provider's first-class container resource is still
# stabilizing across 5.x minor versions; rather than pin a specific resource
# name that may rename, we drive `wrangler deploy` from a null_resource. This
# also keeps the Worker's TypeScript source as the single source of truth for
# routes, bindings, and migrations (declared in worker/wrangler.toml).

locals {
  worker_dir      = "${path.module}/../worker"
  inference_image = "ghcr.io/${var.github_owner}/${var.github_repo}/inference:${var.inference_image_tag}"
  worker_source_hash = sha256(join("", [
    filesha256("${local.worker_dir}/wrangler.toml"),
    filesha256("${local.worker_dir}/src/index.ts"),
    filesha256("${local.worker_dir}/package.json"),
    var.inference_image_tag,
  ]))
}

resource "null_resource" "worker_deploy" {
  triggers = {
    source_hash = local.worker_source_hash
  }

  provisioner "local-exec" {
    working_dir = local.worker_dir
    environment = {
      CLOUDFLARE_API_TOKEN  = var.cloudflare_api_token
      CLOUDFLARE_ACCOUNT_ID = var.cloudflare_account_id
      INFERENCE_IMAGE       = local.inference_image
    }
    command = <<-EOT
      set -euo pipefail
      npm install --no-audit --no-fund
      npx wrangler deploy
    EOT
  }
}

# R2 S3-API credentials passed to the container so it can pull the latest
# checkpoint from the private is-the-mountain-out bucket on startup. These
# are pushed to the Worker as secrets — the container reads them as env
# vars via the InferenceContainer class in worker/src/index.ts.
resource "null_resource" "worker_secret_r2_access_key_id" {
  triggers = {
    value_hash = sha256(var.r2_access_key_id)
  }

  provisioner "local-exec" {
    working_dir = local.worker_dir
    environment = {
      CLOUDFLARE_API_TOKEN  = var.cloudflare_api_token
      CLOUDFLARE_ACCOUNT_ID = var.cloudflare_account_id
      SECRET_VALUE          = var.r2_access_key_id
    }
    command = <<-EOT
      set -euo pipefail
      printf '%s' "$SECRET_VALUE" | npx wrangler secret put R2_ACCESS_KEY_ID --name mountain-inference
    EOT
  }

  depends_on = [null_resource.worker_deploy]
}

resource "null_resource" "worker_secret_r2_secret_access_key" {
  triggers = {
    value_hash = sha256(var.r2_secret_access_key)
  }

  provisioner "local-exec" {
    working_dir = local.worker_dir
    environment = {
      CLOUDFLARE_API_TOKEN  = var.cloudflare_api_token
      CLOUDFLARE_ACCOUNT_ID = var.cloudflare_account_id
      SECRET_VALUE          = var.r2_secret_access_key
    }
    command = <<-EOT
      set -euo pipefail
      printf '%s' "$SECRET_VALUE" | npx wrangler secret put R2_SECRET_ACCESS_KEY --name mountain-inference
    EOT
  }

  depends_on = [null_resource.worker_deploy]
}

# ntfy.sh topic the Worker publishes to on Not-Out → visible transitions.
resource "null_resource" "worker_secret_ntfy_topic" {
  triggers = {
    value_hash = sha256(var.ntfy_topic)
  }

  provisioner "local-exec" {
    working_dir = local.worker_dir
    environment = {
      CLOUDFLARE_API_TOKEN  = var.cloudflare_api_token
      CLOUDFLARE_ACCOUNT_ID = var.cloudflare_account_id
      SECRET_VALUE          = var.ntfy_topic
    }
    command = <<-EOT
      set -euo pipefail
      printf '%s' "$SECRET_VALUE" | npx wrangler secret put NTFY_TOPIC --name mountain-inference
    EOT
  }

  depends_on = [null_resource.worker_deploy]
}
