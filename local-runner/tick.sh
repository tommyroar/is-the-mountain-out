#!/usr/bin/env bash
# One inference tick. Mirrors the Cloudflare Worker's scheduled() handler:
#   1. POST <inference>/predict
#   2. On success: overwrite web/public/state.json, append history.jsonl
#   3. On error:  append error record to history.jsonl; leave state.json alone
#   4. git pull --rebase && git commit && git push
#
# Drive this on */15 via launchd (com.mountain.inference.plist), cron, or
# Nomad periodic. Idempotent — exits 0 when there's nothing to commit.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -f "$SCRIPT_DIR/.env" ]]; then
  set -a; source "$SCRIPT_DIR/.env"; set +a
fi

INFERENCE_URL="${INFERENCE_URL:-http://127.0.0.1:8080}"
REPO_PATH="${REPO_PATH:-$(cd "$SCRIPT_DIR/.." && pwd)}"
GIT_BRANCH="${GIT_BRANCH:-main}"
GIT_AUTHOR_NAME="${GIT_AUTHOR_NAME:-github-actions[bot]}"
GIT_AUTHOR_EMAIL="${GIT_AUTHOR_EMAIL:-41898282+github-actions[bot]@users.noreply.github.com}"
STATE_PATH="${STATE_PATH:-web/public/state.json}"
HISTORY_PATH="${HISTORY_PATH:-web/public/history.jsonl}"

log() { printf '%s [tick] %s\n' "$(date -u +%FT%TZ)" "$*"; }
die() { printf '%s [tick] error: %s\n' "$(date -u +%FT%TZ)" "$*" >&2; exit 1; }

command -v jq    >/dev/null 2>&1 || die "jq is required (brew install jq)"
command -v curl  >/dev/null 2>&1 || die "curl is required"
command -v git   >/dev/null 2>&1 || die "git is required"

[[ -d "$REPO_PATH/.git" ]] || die "REPO_PATH=$REPO_PATH is not a git checkout"

iso_now() { date -u +%Y-%m-%dT%H:%M:%SZ; }

started_at="$(iso_now)"
started_epoch="$(date -u +%s)"

http_code=0
body_file="$(mktemp -t mountain-tick.XXXXXX)"
trap 'rm -f "$body_file"' EXIT

set +e
http_code=$(curl -sS -o "$body_file" -w '%{http_code}' \
  -X POST -H "Content-Type: application/json" \
  --max-time 60 \
  "$INFERENCE_URL/predict")
curl_exit=$?
set -e

finished_at="$(iso_now)"
duration="$(awk -v a="$started_epoch" -v b="$(date -u +%s)" 'BEGIN { printf "%.3f", b - a }')"

if [[ "$curl_exit" -ne 0 || "$http_code" != "200" ]]; then
  err_msg="inference call failed (curl_exit=$curl_exit, http=$http_code): $(head -c 500 "$body_file" | tr '\n' ' ')"
  log "$err_msg"
  status="error"
  record=$(jq -nc \
    --arg started "$started_at" \
    --arg finished "$finished_at" \
    --argjson dur "$duration" \
    --arg type "InferenceCallFailed" \
    --arg msg "$err_msg" \
    '{started_at:$started, finished_at:$finished, duration_seconds:$dur, status:"error", error:{type:$type, message:$msg}}')
else
  state_json="$(cat "$body_file")"
  status="ok"
  record=$(jq -nc \
    --arg started "$started_at" \
    --arg finished "$finished_at" \
    --argjson dur "$duration" \
    --argjson state "$state_json" \
    '{started_at:$started, finished_at:$finished, duration_seconds:$dur, status:"ok", state:$state}')
fi

cd "$REPO_PATH"

git fetch --quiet origin "$GIT_BRANCH"
git checkout --quiet "$GIT_BRANCH"
git pull --rebase --quiet origin "$GIT_BRANCH"

mkdir -p "$(dirname "$STATE_PATH")"
mkdir -p "$(dirname "$HISTORY_PATH")"

# Capture the previous headline class so we can decide whether the SPA
# rebuild + GitHub Actions notification is actually warranted.
prev_class=""
if [[ -f "$STATE_PATH" ]]; then
  prev_class="$(jq -r '.class_name // empty' "$STATE_PATH" 2>/dev/null || true)"
fi

# Always append to history.
printf '%s\n' "$record" >> "$HISTORY_PATH"

# State.json only on success — on error we keep the last good reading.
if [[ "$status" == "ok" ]]; then
  echo "$state_json" | jq '.' > "$STATE_PATH"
fi

git add "$STATE_PATH" "$HISTORY_PATH"
if git diff --staged --quiet; then
  log "no changes to commit"
  exit 0
fi

if [[ "$status" == "ok" ]]; then
  ts="$(jq -r '.timestamp_utc // empty' "$STATE_PATH")"
  new_class="$(jq -r '.class_name // empty' "$STATE_PATH" 2>/dev/null || true)"
  msg="chore: update mountain state ${ts:-$finished_at}"
  # When class_name is unchanged the SPA renders identically — skip the
  # update.yml run (and the GitHub mobile notification) by tagging the
  # commit. Error ticks intentionally do *not* skip CI: surfacing inference
  # failures is the whole point of the notification.
  if [[ -n "$prev_class" && "$prev_class" == "$new_class" ]]; then
    msg="$msg [skip ci]"
  fi
else
  msg="chore: log mountain inference error $finished_at"
fi

GIT_AUTHOR_NAME="$GIT_AUTHOR_NAME" \
GIT_AUTHOR_EMAIL="$GIT_AUTHOR_EMAIL" \
GIT_COMMITTER_NAME="$GIT_AUTHOR_NAME" \
GIT_COMMITTER_EMAIL="$GIT_AUTHOR_EMAIL" \
  git commit --quiet -m "$msg"

git push --quiet origin "$GIT_BRANCH"
log "pushed: $msg"
