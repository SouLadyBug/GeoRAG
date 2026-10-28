import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// GITHUB_PAGES=1 builds the static showcase for https://<user>.github.io/GeoRAG/.
export default defineConfig({
  base: process.env.GITHUB_PAGES ? "/GeoRAG/" : "/",
  plugins: [react()],
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
  build: {
    chunkSizeWarningLimit: 1600,
    rollupOptions: {
      output: {
        manualChunks: { maplibre: ["maplibre-gl"], cytoscape: ["cytoscape"], echarts: ["echarts"] },
      },
    },
  },
});
