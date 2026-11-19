import type { NextConfig } from "next";

// The browser only ever talks to this origin. /api/* is proxied server-side to FastAPI so auth
// cookies stay first-party (HttpOnly, SameSite=Lax) and no API URL or secret ships to the client.
const API_INTERNAL_URL = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000";

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
];

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  poweredByHeader: false,
  experimental: {
    // Uploads (up to 15 MB each) pass through the /api proxy: the default 10 MB body cap and
    // 30-second proxy timeout would cut large documents off.
    proxyClientMaxBodySize: "20mb",
    proxyTimeout: 300_000,
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_INTERNAL_URL}/api/:path*` }];
  },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
