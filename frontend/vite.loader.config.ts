import { defineConfig } from "vite";

export default defineConfig({
  build: {
    outDir: "../src/openagent/static",
    emptyOutDir: false,
    sourcemap: false,
    minify: false,
    lib: {
      entry: "src/sidebar-loader.ts",
      name: "OpenAgentLoader",
      formats: ["iife"],
      fileName: () => "sidebar.js"
    },
    rollupOptions: {
      output: {
        entryFileNames: "sidebar.js"
      }
    }
  }
});
