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

The Worker holds the topic as a secret (`NTFY_TOPIC`), pushed via terraform from the `ntfy_topic` variable (see `terraform/cloudflare_worker.tf` and `scripts/deploy-inference.sh`).

## Test

After deploying the Worker, hit the test endpoint:

```bash
curl -X POST https://mountain-inference.<your-cf-subdomain>.workers.dev/notify-test
```

That sends a one-shot test notification (priority 3) with no inference involved — useful for verifying the Worker secret + ntfy.sh path without waiting for a transition.

You can also publish directly from the terminal (bypassing the Worker entirely):

```bash
TOPIC=$(cat ntfy.key | tr -d '[:space:]')
curl -sS -X POST https://ntfy.sh/ -H "Content-Type: application/json" \
  -d "{\"topic\":\"$TOPIC\",\"title\":\"test\",\"message\":\"hello\"}"
```
