import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    // 로컬 개발: /api, /ws 를 백엔드(8000)로 프록시해 운영과 동일한 same-origin 구조 유지
    if (process.env.NODE_ENV === "development") {
      return [
        {
          source: "/api/:path*",
          destination: "http://localhost:8000/api/:path*",
        },
        {
          source: "/ws/:path*",
          destination: "http://localhost:8000/ws/:path*",
        },
      ];
    }
    return [];
  },
};

export default nextConfig;
