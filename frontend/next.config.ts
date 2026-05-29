import type { NextConfig } from "next";

const isProd = process.env.NODE_ENV === "production";

const nextConfig: NextConfig = {
  ...(isProd ? { output: "export" as const } : {}),
  experimental: {
    serverActions: {
      allowedOrigins: ["localhost:3000"],
    },
  },
  images: {
    unoptimized: true,
    remotePatterns: [{ protocol: "https", hostname: "**" }],
  },
  ...(isProd
    ? {}
    : {
        async rewrites() {
          return [
            { source: "/api/:path*", destination: "http://127.0.0.1:5000/api/:path*" },
            { source: "/auth/:path*", destination: "http://127.0.0.1:5000/auth/:path*" },
            { source: "/socket.io/:path*", destination: "http://127.0.0.1:5000/socket.io/:path*" },
          ];
        },
      }),
};

export default nextConfig;
