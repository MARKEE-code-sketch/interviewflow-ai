import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/start": "http://localhost:7860",
      "/sessions": "http://localhost:7860",
      "/api": "http://localhost:7860",
    },
  },
});
