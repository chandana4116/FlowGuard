import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Forward /api and /evidence to the FastAPI backend, so the browser sees ONE origin.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/evidence": "http://127.0.0.1:8000",
    },
  },
});
