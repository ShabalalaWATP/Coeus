import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  preview: {
    headers: {
      "Cache-Control": "no-store",
      "Content-Security-Policy":
        "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self' http://127.0.0.1:8001; img-src 'self' data:; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'",
      "Cross-Origin-Embedder-Policy": "require-corp",
      "Cross-Origin-Opener-Policy": "same-origin",
      "Cross-Origin-Resource-Policy": "same-origin",
      "Permissions-Policy": "camera=(), geolocation=(), microphone=()",
      "X-Frame-Options": "DENY",
    },
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
  },
  test: {
    environment: "jsdom",
    globals: true,
    exclude: ["node_modules/**", "dist/**", "tests/e2e/**", "tests/e2e-postgres/**"],
    setupFiles: ["./src/test/setup.ts"],
    coverage: {
      provider: "v8",
      reporter: ["text", "json-summary"],
      all: true,
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/main.tsx", "src/vite-env.d.ts", "src/test/**", "src/**/*.test.{ts,tsx}"],
      thresholds: {
        lines: 95,
        branches: 95,
        functions: 95,
        statements: 95,
      },
    },
  },
});
