import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  transpilePackages: ["@wr3/shared"],
  experimental: {
    typedRoutes: true,
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
