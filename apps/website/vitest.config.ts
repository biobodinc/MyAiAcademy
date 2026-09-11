import { defineConfig } from "vitest/config";

export default defineConfig({
  // Mirror the `@/*` path alias from tsconfig.json so components import the same way
  // under test as they do in the Next build.
  resolve: { alias: { "@": import.meta.dirname } },
  test: {
    include: ["tests/**/*.test.ts", "tests/**/*.test.tsx"],
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
  },
});
