import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  transpilePackages: ["@wr3/shared"],
  // Pin the workspace root so Turbopack 16+ doesn't auto-detect an unrelated
  // package-lock.json higher up the filesystem and emit a "multiple lockfiles"
  // warning on every dev start.
  // Pin to the monorepo root so Turbopack doesn't auto-detect an unrelated
  // package-lock.json sitting in $HOME and pick that as the root.
  turbopack: {
    root: path.resolve(__dirname, "../.."),
  },
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${process.env.WR3_API_URL ?? "http://localhost:8001"}/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
