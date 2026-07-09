import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "./",
  plugins: [react()],
  build: {
    outDir: "../src/openagent/static/widget",
    emptyOutDir: true,
    sourcemap: false
  }
});
