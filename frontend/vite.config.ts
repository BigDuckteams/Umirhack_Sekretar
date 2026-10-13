import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Сборка кладётся прямо в Python-пакет: сервер отдаёт её по /static/app/, Node для запуска не нужен.
export default defineConfig(({ command }) => ({
  base: command === "build" ? "/static/app/" : "/",
  plugins: [react()],
  build: {
    outDir: "../dekanat/web/static/app",
    emptyOutDir: true,
    sourcemap: false,
    chunkSizeWarningLimit: 600,
  },
  server: {
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test-setup.ts",
    css: false,
  },
}));
