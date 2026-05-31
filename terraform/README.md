# Terraform for is-the-mountain-out — **deferred, not the active deploy path**

This directory holds a working Terraform configuration for the Cloudflare side
of the stack. **It is intentionally not used to deploy today.** It was stashed
off `main` (branch `terraform-stash`) and is re-proposed here as a documented
decision so the work isn't lost and can be adopted later if the trade-offs shift.

If you just want to deploy, see `scripts/deploy-inference.sh` and the wrangler
flow below — you do **not** need Terraform.

---

## The active deploy model: wrangler-direct

The Worker + container is deployed directly with wrangler, authenticated by the
operator's `wrangler login` **OAuth session**:

```sh
cd worker
npx wrangler deploy                                   # Worker + container app
printf '%s' "$VALUE" | npx wrangler secret put NAME   # secrets (R2 creds, NTFY_TOPIC)
```

R2 buckets and the Pages project already exist (created via the dashboard / MCP).
Nothing in the live path requires a hand-cut API token.

## Why Terraform is deferred

1. **It would reintroduce a long-lived secret.** The Cloudflare Terraform
   provider authenticates *only* via an `api_token` — there is no OAuth path.
   Adopting Terraform means cutting, storing, and rotating a
   `CLOUDFLARE_API_TOKEN` that the wrangler-direct model doesn't need.
2. **For the Worker it adds indirection without declarative value.** Look at
   `cloudflare_worker.tf`: every resource is a `null_resource` + `local-exec`
   that just shells out to `wrangler deploy` / `wrangler secret put`. Terraform
   isn't managing Worker state declaratively here — it's a wrapper around
   wrangler, so it inherits wrangler's behaviour plus a token requirement and an
   extra tool in the chain.
3. **The infra it *would* manage declaratively (R2, Pages) already exists** and
   isn't churning. Bringing it under Terraform is IaC hygiene, not a functional
   need — and some resources can't be cleanly imported (see Caveats).
4. **It isn't the current blocker.** Deploying the inference container is gated
   on the **Workers Paid plan** ($5/mo), which Terraform does nothing to change.

## Trade-offs

| | wrangler-direct (current) | Terraform IaC (this dir) |
|---|---|---|
| Auth | OAuth session, no stored token | Requires a long-lived `CLOUDFLARE_API_TOKEN` |
| Worker deploy | Native wrangler | `null_resource` → wrangler (same thing, wrapped) |
| Infra source of truth | Dashboard / MCP / wrangler.toml | Declarative `.tf` (reviewable, reproducible) |
| Drift / review | None; imperative, ad-hoc | `terraform plan` diff before apply |
| Secrets | Set ad-hoc per deploy | Declared alongside infra in one place |
| Ceremony | Minimal | init / plan / apply, state to manage |
| R2 domain + CORS | Set once in dashboard | First apply **overwrites** dashboard (no import in v5) |

**Recommendation:** keep wrangler-direct while the infra is small and stable.
Revisit Terraform when there are enough Cloudflare resources that declarative
review + reproducibility outweigh the token-management cost — e.g. if the stack
grows beyond a single Worker + two buckets + one Pages project.

## If/when you adopt it

1. Authorize the Cloudflare GitHub App on the repo (Pages needs the OAuth grant
   before a Git source can bind).
2. Import the two pre-existing R2 buckets so the first apply doesn't try to
   recreate them:
   ```sh
   terraform import cloudflare_r2_bucket.captures <account_id>/is-the-mountain-out
   terraform import cloudflare_r2_bucket.public   <account_id>/is-the-mountain-out-public
   ```
3. Provide `cloudflare_api_token`, `cloudflare_account_id`, `r2_access_key_id`,
   `r2_secret_access_key` via `terraform.tfvars` or `TF_VAR_*` env.
4. `terraform plan` → review (the R2 managed-domain + CORS rules are
   full-replacement PUTs that overwrite whatever the dashboard set — confirm the
   CORS origins match production) → `terraform apply`.

### Caveats
- `cloudflare_r2_managed_domain` / `cloudflare_r2_bucket_cors` do **not** support
  `terraform import` in provider v5.x — the first apply overwrites the
  dashboard-set values (intended, but verify they match prod first).
- The R2 S3-API token is still cut manually in the dashboard (the v5 provider's
  token-policy block is unstable); it flows through the Worker as a secret either
  way.

## Relationship to PR #66

PR #66 (`terraform-reclaim-cloudflare`) is a **superset** of this directory — it
adds `r2.tf` and `pages.tf` to reclaim the buckets and Pages project. Both are
deferred for the same reasons above. If Terraform is adopted, consolidate on the
#66 branch (or fold its `r2.tf`/`pages.tf` in here) rather than maintaining two.
