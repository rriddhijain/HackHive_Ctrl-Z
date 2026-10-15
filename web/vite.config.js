import { defineConfig } from "vite";
import tailwindcss from "@tailwindcss/vite";

const api = "http://127.0.0.1:8000";
export default defineConfig({
  plugins: [tailwindcss()],
  esbuild: { jsx: "automatic" },
  server: { proxy: { "/api": api, "/sse": api, "/stream": api, "/media": api } },
});
