import { R2Bucket, KVNamespace } from '@cloudflare/workers-types';

export interface Env {
	MOUNTAIN_CAPTURES: R2Bucket;
	MOUNTAIN_STATE: KVNamespace;
	WEBCAM_URL: string;
	METAR_STATION: string;
}

interface CollectorState {
	session_id: string;
	status: string;
	capture_count: number;
	plan_total: number;
	interval_seconds: number;
	last_capture_at: string | null;
	next_capture_at: string | null;
	updated_at: string;
}

export default {
	async scheduled(event: ScheduledEvent, env: Env, ctx: ExecutionContext) {
		await performCapture(env);
	},

	async fetch(request: Request, env: Env, ctx: ExecutionContext) {
		const url = new URL(request.url);

		if (url.pathname === '/capture' && request.method === 'POST') {
			await performCapture(env);
			return new Response('Capture triggered', { status: 200 });
		}

		if (url.pathname === '/state' && request.method === 'GET') {
			const state = await env.MOUNTAIN_STATE.get('collector_state.json');
			return new Response(state, {
				headers: { 'Content-Type': 'application/json' },
			});
		}

		if (url.pathname === '/list' && request.method === 'GET') {
			const limit = parseInt(url.searchParams.get('limit') || '50');
			const objects = await env.MOUNTAIN_CAPTURES.list({ prefix: 'captures/', limit });
			const list = objects.objects.map((o) => o.key);
			return new Response(JSON.stringify(list), {
				headers: { 'Content-Type': 'application/json' },
			});
		}

		if (url.pathname === '/get' && request.method === 'GET') {
			const key = url.searchParams.get('key');
			if (!key) return new Response('Key required', { status: 400 });
			const object = await env.MOUNTAIN_CAPTURES.get(key);
			if (!object) return new Response('Not Found', { status: 404 });
			const headers = new Headers();
			object.writeHttpMetadata(headers);
			headers.set('etag', object.httpEtag);
			return new Response(object.body, { headers });
		}

		return new Response('Not Found', { status: 404 });
	},
};

async function performCapture(env: Env) {
	const now = new Date();
	const dateStr = now.toISOString().split('T')[0].replace(/-/g, '');
	const timeStr = now.toISOString().split('T')[1].replace(/:/g, '').replace(/\./g, '_').replace('Z', '_UTC');

	const baseKey = `captures/${dateStr}/${timeStr}`;

	// 1. Fetch Image
	const imageResponse = await fetch(env.WEBCAM_URL);
	if (imageResponse.ok) {
		const imageBlob = await imageResponse.blob();
		await env.MOUNTAIN_CAPTURES.put(`${baseKey}/images/capture.jpg`, imageBlob, {
			httpMetadata: { contentType: 'image/jpeg' },
		});
	}

	// 2. Fetch METAR
	const metarUrl = `https://tgftp.nws.noaa.gov/data/observations/metar/stations/${env.METAR_STATION}.TXT`;
	const metarResponse = await fetch(metarUrl);
	if (metarResponse.ok) {
		const metarText = await metarResponse.text();
		await env.MOUNTAIN_CAPTURES.put(`${baseKey}/metar/metar.txt`, metarText, {
			httpMetadata: { contentType: 'text/plain' },
		});
	}

	// 3. Update State in KV
	const stateStr = await env.MOUNTAIN_STATE.get('collector_state.json');
	let state: CollectorState = stateStr
		? JSON.parse(stateStr)
		: {
				session_id: 'cloud-worker',
				status: 'Idle',
				capture_count: 0,
				plan_total: 0,
				interval_seconds: 600,
				last_capture_at: null,
				next_capture_at: null,
				updated_at: now.toISOString(),
		  };

	state.capture_count += 1;
	state.last_capture_at = now.toISOString();
	state.updated_at = now.toISOString();
	state.status = 'Idle';

	await env.MOUNTAIN_STATE.put('collector_state.json', JSON.stringify(state));
}
