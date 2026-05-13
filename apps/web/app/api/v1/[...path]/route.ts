/**
 * Runtime proxy: /api/v1/* → ${WR3_API_URL}/v1/*
 *
 * Why this is a Route Handler instead of `next.config.ts` rewrites:
 * `rewrites()` bakes the destination URL into worker.js at build time, so
 * rotating WR3_API_URL on the Cloudflare dashboard did nothing until a
 * fresh deploy. This handler reads `process.env.WR3_API_URL` at REQUEST
 * time, so dashboard changes take effect immediately on next request.
 *
 * Compatibility note: do NOT add `export const runtime = "edge"` here.
 * OpenNext-CF already runs every handler inside workerd, and the explicit
 * `edge` declaration confuses its build pipeline — the resulting bundle
 * crashes at request time with a bare 500.
 */

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

// Notice: Next.js 15+ types `params` as `Promise<...>`. Next.js 14 (and
// some OpenNext builds) keep it sync. We accept BOTH by treating it as
// `unknown` and resolving with `await Promise.resolve(...)` — the await
// is a no-op on a plain object and unwraps a Promise without crashing.
// This avoids the "TypeError: ctx.params.then is not a function" class
// of errors that surface as a bare 500 from the OpenNext shim.
type Params = { path?: string[] };
type Ctx = { params: Params | Promise<Params> };

async function proxy(req: Request, ctx: Ctx): Promise<Response> {
  try {
    const params = await Promise.resolve(ctx.params);
    const pathParts = params?.path ?? [];
    const rawOrigin = process.env.WR3_API_URL ?? "http://localhost:8001";
    const apiOrigin = rawOrigin.replace(/\/$/, "");
    const url = new URL(req.url);
    const target = `${apiOrigin}/v1/${pathParts.join("/")}${url.search}`;

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
          target,
        }),
        {
          status: 502,
          headers: { "content-type": "application/json" },
        },
      );
    }

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
    return new Response(
      JSON.stringify({
        error: "proxy_internal",
        message: (e as Error)?.message ?? String(e),
        stack: ((e as Error)?.stack ?? "").split("\n").slice(0, 5),
      }),
      {
        status: 500,
        headers: { "content-type": "application/json" },
      },
    );
  }
}

export async function GET(req: Request, ctx: Ctx) {
  return proxy(req, ctx);
}
export async function POST(req: Request, ctx: Ctx) {
  return proxy(req, ctx);
}
export async function PUT(req: Request, ctx: Ctx) {
  return proxy(req, ctx);
}
export async function PATCH(req: Request, ctx: Ctx) {
  return proxy(req, ctx);
}
export async function DELETE(req: Request, ctx: Ctx) {
  return proxy(req, ctx);
}
export async function OPTIONS(req: Request, ctx: Ctx) {
  return proxy(req, ctx);
}
