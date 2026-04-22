import { defineConfig } from "vite";
import { resolve } from "path";

export default defineConfig({
  build: {
    outDir: "app/static/dist",
    emptyOutDir: false,
    rollupOptions: {
      input: {
        webphone: resolve(process.cwd(), "frontend/webphone-modern.js"),
      },
      output: {
        entryFileNames: "[name].js",
      },
    },
  },
});