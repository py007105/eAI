import { defineConfig } from "vitest/config";
import { loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
const apiProxy = (target: string) => ({
  "/api": {
    target,
    changeOrigin: true,
    rewrite: (path: string) => path.replace(/^\/api/, ""),
  },
});
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "VITE_API_TARGET");
  const target = env.VITE_API_TARGET?.trim() || "http://127.0.0.1:8000";
  return {
    plugins: [react(), tailwindcss()],
    server: { fs: { allow: [".."] }, proxy: apiProxy(target) },
    preview: { proxy: apiProxy(target) },
    test: {
      environment: "jsdom",
      environmentOptions: { jsdom: { url: "http://localhost/" } },
      setupFiles: "./tests/setup.ts",
      restoreMocks: true,
    },
  };
});
