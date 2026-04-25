// Cloudflare Worker that owns the */15 inference cadence.
//
// Cron handler:
//   1. Calls the bound container's /predict endpoint.
//   2. Wraps the call in the same try/finally shape as
//      tools/predict_state.py main() — every tick produces one structured
//      record (status: "ok" with state, or status: "error" with traceback).
//   3. On success: overwrites web/public/state.json via the GitHub Contents
//      API and appends the record to web/public/history.jsonl.
//   4. On failure: appends only the error record so state.json keeps showing
//      the last good reading.
//
// Output cadence and persistence are owned by Cloudflare; GitHub-hosted runners
// are no longer in the inference path.

import { Container, getContainer } from "@cloudflare/containers";

export class InferenceContainer extends Container {
  defaultPort = 8080;
  sleepAfter = "5m";
}

interface Env {
  INFERENCE_CONTAINER: DurableObjectNamespace<InferenceContainer>;
  GITHUB_OWNER: string;
  GITHUB_REPO: string;
  GITHUB_BRANCH: string;
  STATE_PATH: string;
  HISTORY_PATH: string;
  GITHUB_TOKEN: string;
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

const ghHeaders = (token: string) => ({
  Authorization: `Bearer ${token}`,
  Accept: "application/vnd.github+json",
  "X-GitHub-Api-Version": "2022-11-28",
  "User-Agent": "mountain-inference-worker",
});

async function readFile(env: Env, path: string): Promise<{ content: string; sha: string } | null> {
  const url = `https://api.github.com/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/contents/${path}?ref=${env.GITHUB_BRANCH}`;
  const resp = await fetch(url, { headers: ghHeaders(env.GITHUB_TOKEN) });
  if (resp.status === 404) return null;
  if (!resp.ok) {
    throw new Error(`GitHub GET ${path} failed: ${resp.status} ${await resp.text()}`);
  }
  const data = (await resp.json()) as { content: string; sha: string; encoding: string };
  const content =
    data.encoding === "base64"
      ? new TextDecoder().decode(Uint8Array.from(atob(data.content.replace(/\n/g, "")), (c) => c.charCodeAt(0)))
      : data.content;
  return { content, sha: data.sha };
}

async function writeFile(
  env: Env,
  path: string,
  content: string,
  message: string,
  prevSha: string | null,
): Promise<void> {
  const url = `https://api.github.com/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/contents/${path}`;
  const body: Record<string, unknown> = {
    message,
    content: btoa(unescape(encodeURIComponent(content))),
    branch: env.GITHUB_BRANCH,
  };
  if (prevSha) body.sha = prevSha;
  const resp = await fetch(url, {
    method: "PUT",
    headers: { ...ghHeaders(env.GITHUB_TOKEN), "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    throw new Error(`GitHub PUT ${path} failed: ${resp.status} ${await resp.text()}`);
  }
}

async function appendHistory(env: Env, record: HistoryRecord): Promise<void> {
  const existing = await readFile(env, env.HISTORY_PATH);
  const line = JSON.stringify(record) + "\n";
  const next = (existing?.content ?? "") + line;
  const ts = record.finished_at;
  await writeFile(env, env.HISTORY_PATH, next, `chore: log mountain inference ${ts}`, existing?.sha ?? null);
}

async function publishState(env: Env, state: PredictionState): Promise<void> {
  const existing = await readFile(env, env.STATE_PATH);
  const content = JSON.stringify(state, null, 2) + "\n";
  if (existing && existing.content === content) return;
  await writeFile(
    env,
    env.STATE_PATH,
    content,
    `chore: update mountain state ${state.timestamp_utc}`,
    existing?.sha ?? null,
  );
}

async function tick(env: Env): Promise<void> {
  const startedAt = new Date();
  let record: HistoryRecord;
  try {
    const state = await callContainer(env);
    await publishState(env, state);
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
    return new Response("mountain-inference worker\n", { status: 200 });
  },
} satisfies ExportedHandler<Env>;
