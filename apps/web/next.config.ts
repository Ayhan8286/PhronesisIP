import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination:
          process.env.NEXT_PUBLIC_API_URL
            ? `${process.env.NEXT_PUBLIC_API_URL}/api/v1/:path*`
            : "/apps/api/index.py/api/v1/:path*",
      },
      {
        source: "/api/inngest",
        destination:
          process.env.NEXT_PUBLIC_API_URL
            ? `${process.env.NEXT_PUBLIC_API_URL}/api/inngest`
            : "/apps/api/index.py/api/inngest",
      },
    ];
  },
};

export default nextConfig;
