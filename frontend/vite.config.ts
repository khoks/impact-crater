import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// FastAPI dev server defaults to localhost:8765 (per backend/impact_crater/cli.py).
// Vite dev server proxies /api/* to it so the SPA can call the same paths
// the production build uses (where FastAPI serves both the frontend and the API).
const FASTAPI_DEV_TARGET = process.env.IC_API_TARGET ?? "http://127.0.0.1:8765";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: false,
    proxy: {
      "/api": {
        target: FASTAPI_DEV_TARGET,
        changeOrigin: true,
        ws: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
