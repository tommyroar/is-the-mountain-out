// Cloudflare Worker that owns the */15 inference cadence.
//
// Cron handler:
//   1. Calls the bound container's /predict endpoint.
//   2. Wraps the call in a try/finally that produces one structured record per
//      tick (status: "ok" with state, or status: "error" with message).
//   3. On success: overwrites state.json in the public R2 bucket.
//   4. Always: appends a record to history.jsonl in R2 (GET, append, PUT —
//      R2 has no append op, but at one record per 15min the file stays small).
//
// The container is passed R2 credentials as env vars so it can pull the
// latest checkpoint from R2 on first /predict call. Worker writes the
// inference output to a separate public R2 bucket the SPA reads from
// directly — no GitHub Contents API in the inference path.

import { Container, getContainer } from "@cloudflare/containers";
import { notifyDiscordTest, notifyMountainVisibility } from "./discord-mountain-notify";

interface Env {
  INFERENCE_CONTAINER: DurableObjectNamespace<InferenceContainer>;
  STATE_BUCKET: R2Bucket;
  R2_ACCESS_KEY_ID: string;
  R2_SECRET_ACCESS_KEY: string;
  // Discord webhook URL the Worker posts visibility transitions to. Optional so
  // a missing secret degrades to a logged skip rather than a thrown error. Set
  // out-of-band with `wrangler secret put DISCORD_WEBHOOK_URL`.
  DISCORD_WEBHOOK_URL?: string;
}

export class InferenceContainer extends Container<Env> {
  defaultPort = 8080;
  sleepAfter = "5m";

  override envVars = {
    R2_ACCESS_KEY_ID: this.env.R2_ACCESS_KEY_ID,
    R2_SECRET_ACCESS_KEY: this.env.R2_SECRET_ACCESS_KEY,
  };
}

interface PredictionState {
  timestamp_utc: string;
  class_index: number;
  class_name: string;
  is_out: boolean;
  confidence: Record<string, number>;
  weather: Record<string, unknown>;
  webcam_url: string;
  model_version: string | null;
}

type HistoryRecord =
  | {
      started_at: string;
      finished_at: string;
      duration_seconds: number;
      status: "ok";
      state: PredictionState;
    }
  | {
      started_at: string;
      finished_at: string;
      duration_seconds: number;
      status: "error";
      error: { type: string; message: string };
    };

const STATE_KEY = "state.json";
const HISTORY_KEY = "history.jsonl";

const isoUtc = (d: Date) => d.toISOString().replace(/\.\d{3}Z$/, "Z");

async function callContainer(env: Env): Promise<PredictionState> {
  const stub = getContainer(env.INFERENCE_CONTAINER);
  const resp = await stub.fetch("http://container/predict", { method: "POST" });
  if (!resp.ok) {
    const body = await resp.text().catch(() => "<unreadable>");
    throw new Error(`container /predict returned ${resp.status}: ${body.slice(0, 500)}`);
  }
  return (await resp.json()) as PredictionState;
}

async function publishState(env: Env, state: PredictionState): Promise<void> {
  await env.STATE_BUCKET.put(STATE_KEY, JSON.stringify(state, null, 2) + "\n", {
    httpMetadata: { contentType: "application/json" },
  });
}

async function getPreviousState(env: Env): Promise<PredictionState | null> {
  try {
    const obj = await env.STATE_BUCKET.get(STATE_KEY);
    if (!obj) return null;
    return JSON.parse(await obj.text()) as PredictionState;
  } catch (e) {
    console.warn("failed to read previous state for transition check:", e);
    return null;
  }
}

// Fire only on the Not Out → visible transition, mirroring tools/detect_mountain.py.
async function notifyTransition(env: Env, prev: PredictionState | null, next: PredictionState): Promise<void> {
  if (!next.is_out) return;
  if (prev?.is_out) return;
  const visible = (next.confidence?.full ?? 0) + (next.confidence?.partial ?? 0);
  const label = next.class_name === "full" ? "Full" : "Partial";
  await notifyMountainVisibility(env, {
    visible: true,
    confidence: visible,
    label,
    imageUrl: next.webcam_url,
    timestamp: next.timestamp_utc,
  });
}

async function sendNotificationTest(env: Env): Promise<void> {
  await notifyDiscordTest(env);
}

async function appendHistory(env: Env, record: HistoryRecord): Promise<void> {
  const existing = await env.STATE_BUCKET.get(HISTORY_KEY);
  const prev = existing ? await existing.text() : "";
  const next = prev + JSON.stringify(record) + "\n";
  await env.STATE_BUCKET.put(HISTORY_KEY, next, {
    httpMetadata: { contentType: "application/x-ndjson" },
  });
}

async function tick(env: Env): Promise<void> {
  const startedAt = new Date();
  let record: HistoryRecord;
  try {
    // Read prev state BEFORE the new write so we can compare for transition detection.
    const prev = await getPreviousState(env);
    const state = await callContainer(env);
    await publishState(env, state);
    await notifyTransition(env, prev, state);
    const finishedAt = new Date();
    record = {
      started_at: isoUtc(startedAt),
      finished_at: isoUtc(finishedAt),
      duration_seconds: Number(((finishedAt.getTime() - startedAt.getTime()) / 1000).toFixed(3)),
      status: "ok",
      state,
    };
  } catch (err) {
    const finishedAt = new Date();
    const e = err as Error;
    record = {
      started_at: isoUtc(startedAt),
      finished_at: isoUtc(finishedAt),
      duration_seconds: Number(((finishedAt.getTime() - startedAt.getTime()) / 1000).toFixed(3)),
      status: "error",
      error: { type: e.name || "Error", message: e.message ?? String(err) },
    };
    console.error("inference tick failed:", e);
  }
  await appendHistory(env, record);
}

export default {
  async scheduled(_event: ScheduledController, env: Env, ctx: ExecutionContext) {
    ctx.waitUntil(tick(env));
  },

  async fetch(req: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(req.url);
    if (url.pathname === "/run" && req.method === "POST") {
      ctx.waitUntil(tick(env));
      return new Response("queued\n", { status: 202 });
    }
    if (url.pathname === "/notify-test" && req.method === "POST") {
      ctx.waitUntil(sendNotificationTest(env));
      return new Response("test notification queued\n", { status: 202 });
    }
    return new Response("mountain-inference worker\n", { status: 200 });
  },
} satisfies ExportedHandler<Env>;
