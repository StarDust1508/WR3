/**
 * Runtime proxy: /api/v1/* → ${WR3_API_URL}/v1/*
 *
 * Why this is a Route Handler and not a `next.config.ts` rewrite:
 *   `rewrites()` is evaluated at BUILD time. With Cloudflare Workers + the
 *   @opennextjs adapter the rewrite destination is baked into the compiled
 *   worker.js, so changing the env var on the CF dashboard does NOT change
 *   the proxy target until the next deploy. That's why our incidents page
 *   kept showing 502 even after the operator updated WR3_API_URL — the
 *   worker was still calling the old serveo URL.
 *
 *   Reading the env inside the Route Handler defers the lookup to REQUEST
 *   time. Now the operator can rotate the upstream URL (e.g. fresh serveo
 *   tunnel after a restart) from the dashboard and the change is live on
 *   the next request — no rebuild required.
 *
 * Why a single `[...path]` catch-all instead of one route per endpoint:
 *   Same proxy logic for every method/path. Less code, easier to keep in
 *   sync with the backend, and SSE streams (e.g. /v1/scan/{job}/events)
 *   work transparently because we forward the upstream Response body
 *   verbatim — CF Workers supports streaming response bodies.
 */

// NOTE on runtime: do NOT set `runtime = "edge"` here. OpenNext-CF runs
// every handler in workerd already, and the explicit `edge` declaration
// makes the build emit a different shape that crashes at request time
// (500 Internal Server Error from the worker, no useful log). Just omit
// the runtime export — OpenNext picks the right one.
export const dynamic = "force-dynamic";

const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailers",
  "transfer-encoding",
  "upgrade",
  "host",
  "content-length",
]);

async function proxy(
  req: Request,
  ctx: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  try {
    const params = await ctx.params;
    const path = params.path ?? [];
    const apiOrigin = (
      process.env.WR3_API_URL ?? "http://localhost:8001"
    ).replace(/\/$/, "");
    const url = new URL(req.url);
    const target = `${apiOrigin}/v1/${path.join("/")}${url.search}`;

    // Filter outgoing headers: hop-by-hop and host MUST be dropped
    // (Cloudflare would otherwise echo our own gateway as Host to the
    // origin and confuse routing on serveo / tunnels).
    const headers = new Headers();
    req.headers.forEach((value, key) => {
      if (!HOP_BY_HOP_HEADERS.has(key.toLowerCase())) {
        headers.set(key, value);
      }
    });

    const init: RequestInit = {
      method: req.method,
      headers,
      redirect: "manual",
    };
    if (req.method !== "GET" && req.method !== "HEAD") {
      // Forward the original body. arrayBuffer() materialises it so CF
      // Workers's fetch can take it across the Worker boundary.
      init.body = await req.arrayBuffer();
    }

    let upstream: Response;
    try {
      upstream = await fetch(target, init);
    } catch (e) {
      return new Response(
        JSON.stringify({
          error: "upstream_unreachable",
          message: (e as Error).message,
          target_host: new URL(target).host,
        }),
        {
          status: 502,
          headers: { "content-type": "application/json" },
        },
      );
    }

    // Pass response headers through, minus hop-by-hop. We MUST keep
    // content-type so streaming (text/event-stream for SSE) works.
    const respHeaders = new Headers();
    upstream.headers.forEach((value, key) => {
      if (!HOP_BY_HOP_HEADERS.has(key.toLowerCase())) {
        respHeaders.set(key, value);
      }
    });

    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: respHeaders,
    });
  } catch (e) {
    // Catch-all so the worker never throws a bare 500. If we reach here
    // something is wrong with our own code (bad params, fetch unavailable,
    // etc.). Surface the error message so the operator can diagnose
    // without digging through CF Workers logs.
    return new Response(
      JSON.stringify({
        error: "proxy_internal_error",
        message: (e as Error).message,
        stack: (e as Error).stack?.split("\n").slice(0, 5),
      }),
      {
        status: 500,
        headers: { "content-type": "application/json" },
      },
    );
  }
}

export async function GET(req: Request, ctx: { params: Promise<{ path: string[] }> }) {
  return proxy(req, ctx);
}
export async function POST(req: Request, ctx: { params: Promise<{ path: string[] }> }) {
  return proxy(req, ctx);
}
export async function PUT(req: Request, ctx: { params: Promise<{ path: string[] }> }) {
  return proxy(req, ctx);
}
export async function PATCH(req: Request, ctx: { params: Promise<{ path: string[] }> }) {
  return proxy(req, ctx);
}
export async function DELETE(req: Request, ctx: { params: Promise<{ path: string[] }> }) {
  return proxy(req, ctx);
}
export async function OPTIONS(req: Request, ctx: { params: Promise<{ path: string[] }> }) {
  return proxy(req, ctx);
}
