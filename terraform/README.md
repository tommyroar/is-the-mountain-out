# Terraform — Cloudflare infra for is-the-mountain-out

This directory is the source of truth for the Cloudflare side of the stack:

| File | Manages |
|---|---|
| `cloudflare_worker.tf` | `mountain-inference` Worker + Container deploy (via `wrangler`), Worker secrets (`R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, and `NTFY_TOPIC` once PR #65 lands) |
| `r2.tf` | Both R2 buckets, the public bucket's `r2.dev` managed domain, and its CORS rule |
| `pages.tf` | The `is-the-mountain-out` Cloudflare Pages project (GitHub source + build config) |
| `outputs.tf` | R2 endpoint, public bucket URL, Pages subdomain, Worker name, image tag |
| `main.tf` | Provider versions + the local Nomad `mountain-training` batch job |

State is **local** (`terraform.tfstate` in this directory — no remote backend). The
state file and any `*.tfvars` contain secrets and are gitignored; never commit them.

## What is NOT terraformed (on purpose)

- **The R2 S3-API token** (`r2_access_key_id` / `r2_secret_access_key`). The v5
  provider's token-policy block has been unstable across minors; the token is cut
  by hand in the Cloudflare dashboard and flows to the container through a Worker
  secret regardless. Put the values in `cf.env` at the repo root.
- **The Cloudflare GitHub App authorization** (see prerequisites). It *is* the
  security boundary between Cloudflare and the repo, so it can't be terraformed.

## Prerequisites (one-time, before the first `apply`)

1. **Authorize the Cloudflare GitHub App on the repo.** Pages cannot bind a Git
   source without an existing OAuth grant, so `pages.tf` will fail on a fresh
   account until this is done. In the Cloudflare dashboard:
   *Workers & Pages → Create → Pages → Connect to Git → install/authorize for
   `tommyroar/is-the-mountain-out`*, then cancel out (the project itself is
   created by Terraform). This is a human click, not a terraform resource.
2. **Cut the R2 S3-API token** in the dashboard (Object Storage → API → Manage
   API Tokens) and drop the access key / secret into the repo-root `cf.env`.
3. Install `terraform`, and `node`/`npx` (the Worker deploy shells out to
   `npx wrangler`).

## Variables

All sensitive; pass via `TF_VAR_*` env vars (what `scripts/deploy-inference.sh`
does) or a gitignored `terraform.tfvars`:

| Variable | Source |
|---|---|
| `cloudflare_api_token` | CF dashboard — needs Workers + R2 + Pages + Containers scopes |
| `cloudflare_account_id` | `d7adee58513c1b2f770ccaac90cf114f` (also in `mountain.toml`) |
| `r2_access_key_id` | `cf.env` |
| `r2_secret_access_key` | `cf.env` |
| `ntfy_topic` | `ntfy.key` (only after PR #65 — Worker-side notifications — merges) |

## Import the existing R2 buckets before the first apply

Both buckets already exist (originally created via dashboard/MCP). They MUST be
imported into state first, or Terraform will try to recreate them and fail:

```sh
export CLOUDFLARE_API_TOKEN=...        # same token as the apply
ACCT=d7adee58513c1b2f770ccaac90cf114f

terraform import cloudflare_r2_bucket.captures "$ACCT/is-the-mountain-out"
terraform import cloudflare_r2_bucket.public   "$ACCT/is-the-mountain-out-public"
```

> `cloudflare_r2_managed_domain` and `cloudflare_r2_bucket_cors` do **not** support
> `terraform import` in provider v5.19.1. That's fine — the R2 API treats both as
> full-replacement PUTs, so the first `apply` simply overwrites whatever the
> dashboard set. Confirm the CORS origins in `r2.tf` match production before
> applying.
>
> The Pages project in `pages.tf` does not exist yet on the account, so it needs
> no import — `apply` creates it from scratch.

## Plan / apply

The normal path is the wrapper, which threads the `TF_VAR_*` env through for you:

```sh
PLAN_ONLY=1 scripts/deploy-inference.sh   # terraform plan
scripts/deploy-inference.sh               # terraform apply (+ wrangler deploy + secrets)
```

Or drive Terraform directly from this directory:

```sh
terraform init
terraform plan
terraform apply
```

After apply, `terraform output pages_subdomain` and `r2_public_bucket_url` give
the live URLs. The public bucket URL should match `VITE_STATE_URL` in
`web/.env.production` and the `VITE_STATE_URL` env in `pages.tf`.
