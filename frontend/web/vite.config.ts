import { defineConfig, type Plugin } from "vite";
import vue from "@vitejs/plugin-vue";
import { fileURLToPath, URL } from "node:url";

/**
 * 兼容 frontend/live 中历史 ES Module 的 `?v=stageXX` 缓存查询参数，
 * 让 Vite/Rollup 将带版本号的相对导入归一为同一模块，避免重复打包或解析失败。
 */
function stripLiveVersionQuery(): Plugin {
  return {
    name: "strip-live-version-query",
    enforce: "pre",
    async resolveId(source, importer, options) {
      if (!source.includes("?v=")) return null;
      const clean = source.replace(/\?v=[^#]+/, "");
      return this.resolve(clean, importer, { ...options, skipSelf: true });
    },
  };
}

export default defineConfig({
  plugins: [stripLiveVersionQuery(), vue()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
      "@live": fileURLToPath(new URL("../live", import.meta.url)),
    },
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    fs: {
      allow: [".."],
    },
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: false,
      },
      "/healthz": "http://127.0.0.1:8000",
      "/readyz": "http://127.0.0.1:8000",
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    sourcemap: false,
  },
});
