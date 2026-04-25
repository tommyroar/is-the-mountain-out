# Cloudflare Worker + Container that owns the */15 mountain inference cadence.
#
# The Worker (worker/src/index.ts) is bound to a Container running the
# inference Dockerfile (inference/Dockerfile). On each cron tick the Worker
# invokes the container's /predict endpoint and pushes the result back to
# the GitHub repo via the Contents API.
#
# The Cloudflare Terraform provider's first-class container resource is still
# stabilizing across 5.x minor versions; rather than pin a specific resource
# name that may rename, we drive `wrangler deploy` from a null_resource. This
# also keeps the Worker's TypeScript source as the single source of truth for
# routes, bindings, and migrations (declared in worker/wrangler.toml).

locals {
  worker_dir         = "${path.module}/../worker"
  inference_image    = "ghcr.io/${var.github_owner}/${var.github_repo}/inference:${var.inference_image_tag}"
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
      npx wrangler deploy \
        --var GITHUB_OWNER:${var.github_owner} \
        --var GITHUB_REPO:${var.github_repo} \
        --var GITHUB_BRANCH:${var.github_branch} \
        --var STATE_PATH:web/public/state.json \
        --var HISTORY_PATH:web/public/history.jsonl
    EOT
  }
}

# The GitHub PAT is set once via wrangler secret put. Re-running terraform
# apply with a changed value re-pushes the secret. We do NOT echo the value
# anywhere — it's piped into wrangler via stdin.
resource "null_resource" "worker_secret_github_token" {
  triggers = {
    pat_hash = sha256(var.github_pat)
  }

  provisioner "local-exec" {
    working_dir = local.worker_dir
    environment = {
      CLOUDFLARE_API_TOKEN  = var.cloudflare_api_token
      CLOUDFLARE_ACCOUNT_ID = var.cloudflare_account_id
      GITHUB_PAT_VALUE      = var.github_pat
    }
    command = <<-EOT
      set -euo pipefail
      printf '%s' "$GITHUB_PAT_VALUE" | npx wrangler secret put GITHUB_TOKEN --name mountain-inference
    EOT
  }

  depends_on = [null_resource.worker_deploy]
}
