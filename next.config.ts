import type { NextConfig } from "next";

const backendUrl =
  process.env.BACKEND_URL?.replace(/\/$/, "") || "http://localhost:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        // The auth API is mounted under /api/v1 on FastAPI. Keep that prefix
        // when proxying it; the general API proxy below strips /api.
        source: "/api/v1/:path*",
        destination: `${backendUrl}/api/v1/:path*`,
      },
      {
        source: "/api/:path*",
        destination: `${backendUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
