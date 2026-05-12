import path from "node:path";
import type { NextConfig } from "next";

// `WR3_API_URL` must be set to the FastAPI origin (e.g. a Cloudflare Tunnel
// or serveo URL while developing). The rewrite below proxies every
// /api/v1/* call the Mini App makes back to that origin so the browser
// sees same-origin responses — no CORS, no preflight.
//
// In production on Cloudflare Workers, OpenNext.js translates these
// rewrites into Worker fetch calls — they happen at the edge, not in
// the browser.
const apiOrigin = process.env.WR3_API_URL ?? "http://localhost:8001";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  transpilePackages: ["@wr3/shared"],
  // Pin the workspace root only when we have a file URL (local dev) — CF's
  // remote build environment also has __dirname but the resolution above
  // works there too.
  turbopack: {
    root: path.resolve(__dirname, "../.."),
  },
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${apiOrigin}/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
