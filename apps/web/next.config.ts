import path from "node:path";
import type { NextConfig } from "next";

// API proxy: /api/v1/* → ${WR3_API_URL}/v1/* is implemented as a runtime
// Route Handler at `apps/web/app/api/v1/[...path]/route.ts`. We DON'T use
// `rewrites()` here because Next.js bakes rewrite targets at build time —
// on CF Workers that means rotating the upstream URL requires a full
// rebuild. The route handler reads `process.env.WR3_API_URL` at request
// time, so the dashboard env var actually takes effect immediately.

const nextConfig: NextConfig = {
  reactStrictMode: true,
  transpilePackages: ["@wr3/shared"],
  // Pin the workspace root only when we have a file URL (local dev) — CF's
  // remote build environment also has __dirname but the resolution above
  // works there too.
  turbopack: {
    root: path.resolve(__dirname, "../.."),
  },
};

export default nextConfig;
