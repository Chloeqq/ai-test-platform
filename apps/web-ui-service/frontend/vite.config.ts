import { resolve } from "node:path";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 8013,
    strictPort: true,
    proxy: {
      "/api": {
        target: process.env.VITE_API_TARGET || "http://127.0.0.1:8014",
        changeOrigin: true,
      },
      "/health": {
        target: process.env.VITE_API_TARGET || "http://127.0.0.1:8014",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: resolve(__dirname, "../app/static/react"),
    emptyOutDir: true,
    sourcemap: true,
    rollupOptions: {
      output: {
        entryFileNames: "assets/main.js",
        chunkFileNames: "assets/[name].js",
        assetFileNames: (assetInfo) => {
          const name = String(assetInfo.name || "");
          if (name.endsWith(".css")) {
            return "assets/main.css";
          }
          return "assets/[name][extname]";
        },
      },
    },
  },
});
