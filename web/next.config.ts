import type { NextConfig } from "next";

// Builds are a static export served by FastAPI (StaticFiles(html=True)) from web/dist; rewrites are not
// supported with export, so the API proxy exists in `next dev` only.
const dev = process.env.NODE_ENV === "development";
const API = "http://127.0.0.1:8000";

const config: NextConfig = dev
  ? {
      trailingSlash: true,
      skipTrailingSlashRedirect: true, // else /api/x is 308'd to /api/x/ before the proxy
      async rewrites() {
        return ["/api/:path*", "/sse", "/snapshot/:path*", "/media/:path*"].map((source) => ({
          source,
          destination: `${API}${source}`,
        }));
      },
    }
  : { output: "export", trailingSlash: true, images: { unoptimized: true } };

export default config;
