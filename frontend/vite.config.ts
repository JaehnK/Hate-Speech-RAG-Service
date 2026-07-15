import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    strictPort: true,
    proxy: {
      "/api": "http://web:8000",
      "/health": "http://web:8000",
      "/docs": "http://web:8000",
      "/openapi.json": "http://web:8000",
    },
  },
});
