# Notifications

The project uses **ntfy.sh** for real-time push notifications to mobile devices (iOS/Android).

## Subscribe

1. Install the **ntfy** app.
2. Subscribe to the private topic UUID stored in `ntfy.key` at the repo root (gitignored — the topic value *is* the secret on ntfy.sh; anyone who knows it can publish or subscribe).

## What fires

The `mountain-inference` Cloudflare Worker (`worker/src/index.ts`) sends one notification on the **Not Out → visible** transition (i.e. when the previous tick's `state.json` had `is_out: false` and the current tick predicts `Full` or `Partial`).

| Trigger | Title | Priority | Tag |
|---|---|---|---|
| Not Out → Full or Partial | 🏔️ THE MOUNTAIN IS OUT | 5 (max) | `mountain_snow_capped` |

Message body includes the predicted class and the combined visible-class confidence.

## Secrets

The Worker holds two ntfy secrets, set via `wrangler secret put` (the live deploy path is wrangler, not Terraform):

| Secret | Required | Source | Purpose |
|---|---|---|---|
| `NTFY_TOPIC` | yes | `ntfy.key` | The private topic UUID to publish to. |
| `NTFY_TOKEN` | recommended | `ntfy-token.key` | ntfy.sh access token. Without it, the Worker publishes anonymously and is rate-limited **per source IP** — which returns HTTP 429 from Cloudflare's shared egress IPs (the daily anonymous quota is shared and routinely exhausted). With a token, the quota is attributed to your ntfy account. |

```bash
# from worker/
printf '%s' "$(tr -d '[:space:]' < ../ntfy.key)"       | npx wrangler secret put NTFY_TOPIC
printf '%s' "$(tr -d '[:space:]' < ../ntfy-token.key)"  | npx wrangler secret put NTFY_TOKEN
npx wrangler deploy   # secrets only go live on the next deploy
```

To mint a token: create a free account at https://ntfy.sh, then **Account → Access tokens → Create**. Save it to the gitignored `ntfy-token.key` at the repo root.

## Test

After deploying the Worker, hit the test endpoint:

```bash
curl -X POST https://mountain-inference.<your-cf-subdomain>.workers.dev/notify-test
```

That sends a one-shot test notification (priority 3) with no inference involved — useful for verifying the Worker secret + ntfy.sh path without waiting for a transition. The endpoint always returns `202` (the publish is queued via `waitUntil`); if nothing arrives on your phone, tail the Worker to see the real result: `cd worker && npx wrangler tail --format json` then re-fire — a `ntfy publish 429` line means the token is missing or invalid.

You can also publish directly from the terminal (bypassing the Worker entirely):

```bash
TOPIC=$(cat ntfy.key | tr -d '[:space:]')
curl -sS -X POST https://ntfy.sh/ -H "Content-Type: application/json" \
  -d "{\"topic\":\"$TOPIC\",\"title\":\"test\",\"message\":\"hello\"}"
```
