# Local Mac container runner

Alternative to the Cloudflare Workers Container deployment. Runs the same
`inference/Dockerfile` image on a long-running host (typically the Mac mini)
and pushes inference results to git on a `*/15` cadence via launchd.

The Cloudflare path remains primary. Use this when you want a self-hosted
fallback, when working offline, or for testing the container locally.

## Pick one — don't run both at once

Both paths commit to `web/public/state.json` and `web/public/history.jsonl`
on `main`. Running them simultaneously will cause `git push` races and double
history entries. Stop one before bringing up the other:

- Cloudflare: `wrangler delete mountain-inference` (or unbind the cron in the dash)
- Local: `launchctl unload ~/Library/LaunchAgents/com.mountain.inference.plist`

## Setup

```bash
cd local-runner
cp .env.example .env
$EDITOR .env                       # set INFERENCE_IMAGE_TAG, REPO_PATH, etc.
docker compose up -d
docker compose logs -f inference   # wait for "Application startup complete"
./tick.sh                          # one-off run; verify a commit lands on main
```

`tick.sh` is idempotent — it pulls before committing and exits 0 when
`/predict` returned the same state as the previous tick.

## `*/15` cadence via launchd

```bash
sed "s|__PROJECT_PATH__|$(cd .. && pwd)|" \
  com.mountain.inference.plist > ~/Library/LaunchAgents/com.mountain.inference.plist
launchctl load ~/Library/LaunchAgents/com.mountain.inference.plist

# Watch it tick:
tail -f /tmp/mountain_inference.out /tmp/mountain_inference.err
```

Stop:

```bash
launchctl unload ~/Library/LaunchAgents/com.mountain.inference.plist
docker compose down
```

## Building the image locally instead of pulling

To run a local build (e.g. unmerged inference changes):

```bash
docker build -f ../inference/Dockerfile -t mountain-inference:dev ..
INFERENCE_IMAGE_TAG=dev docker compose up -d
```

(Or override `image:` to `mountain-inference:dev` directly in
`docker-compose.yml` while iterating.)

## Authenticating the git push

`tick.sh` uses the host's existing `git push` credentials — typically the
SSH key already configured for this repo. No extra secrets are needed on the
host because the writes go through the local git remote, not the GitHub API.

If the remote is HTTPS instead of SSH and you don't want to be prompted on
every push, set up a credential helper or switch the remote to SSH:

```bash
git -C "$REPO_PATH" remote set-url origin git@github.com:tommyroar/is-the-mountain-out.git
```

## How it relates to the rest of the deployment

- `inference/Dockerfile` — the actual model server; identical to what
  Cloudflare runs.
- `worker/` — Cloudflare-specific cron + GitHub Contents API client. Replaced
  here by `tick.sh` (cron + local git push).
- `terraform/cloudflare_worker.tf` — not used by this runner.
- `scripts/deploy-inference.sh` — deploys the Cloudflare path.
