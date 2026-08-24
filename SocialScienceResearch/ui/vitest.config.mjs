import { defineConfig } from "vitest/config";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  test: {
    environment: "jsdom",
    globals: false,
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["./vitest.setup.ts"],
    restoreMocks: true,
    clearMocks: true,
    testTimeout: 30000,
    hookTimeout: 30000,
    server: {
      deps: {
        // xlsx is CommonJS; inline it so it is transformed by esbuild instead
        // of externalized and required() in the ESM worker (which would throw
        // and leave importing modules with undefined exports).
        inline: ["xlsx"],
      },
    },
  },
});
