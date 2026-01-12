import react from "@vitejs/plugin-react";
import path from "path";
import { defineConfig } from "vite";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 3000,
    host: "0.0.0.0", // Allow external access
    strictPort: true,
    allowedHosts: [
      "beacon-library.famillelallier.net",
      "localhost",
      "127.0.0.1",
    ],
    watch: {
      usePolling: true, // Required for Docker on some systems
    },
    hmr: {
      // Explicitly configure HMR to use the same host and port as the page
      // The browser will connect via WSS on port 443 (HTTPS default)
      host: "beacon-library.famillelallier.net",
      protocol: "wss",
      clientPort: 443,
      // No path override - use default /
    },
    proxy: {
      "/api": {
        target: "http://backend:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
