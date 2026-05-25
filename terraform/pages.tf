# Cloudflare Pages project that builds and serves the SPA in web/.
#
# Reclaims what would otherwise be a dashboard click on every fresh
# environment. The project itself doesn't exist yet on the Cloudflare
# account — this resource creates it from scratch, so no import is
# needed (unlike the R2 buckets in r2.tf).
#
# Prerequisite: the Cloudflare GitHub App must be authorized on the
# repo BEFORE `terraform apply` (Cloudflare can't bind a Git source
# without an existing OAuth grant). One-time human action; not
# terraformable because it IS the security boundary. See README in
# this directory.
#
# The env var here matches web/.env.production. Vite picks up the
# .env.production file at build time too — declaring it in both
# places is belt-and-suspenders, but means changing the R2 URL is a
# one-file edit either way.

resource "cloudflare_pages_project" "spa" {
  account_id        = var.cloudflare_account_id
  name              = "is-the-mountain-out"
  production_branch = "main"

  source = {
    type = "github"
    config = {
      owner                          = var.github_owner
      owner_id                       = "4916474"
      repo_name                      = var.github_repo
      repo_id                        = "1162388160"
      production_branch              = "main"
      production_deployments_enabled = true
      preview_deployment_setting     = "all"
      pr_comments_enabled            = true
    }
  }

  build_config = {
    build_command   = "npm install && npm run build"
    destination_dir = "web/dist"
    root_dir        = "web"
  }

  deployment_configs = {
    production = {
      env_vars = {
        VITE_STATE_URL = {
          value = "https://pub-66d3d1f139004e29b2afcb5fba49bdb3.r2.dev/state.json"
          type  = "plain_text"
        }
      }
    }
    preview = {
      env_vars = {
        VITE_STATE_URL = {
          value = "https://pub-66d3d1f139004e29b2afcb5fba49bdb3.r2.dev/state.json"
          type  = "plain_text"
        }
      }
    }
  }
}
