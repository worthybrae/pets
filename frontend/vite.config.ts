import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  envDir: '..',
  // shared/ sits beside frontend/ and holds the block registry and worldgen fixture.
  // Only allow it and the project root itself, not the whole repo (which would also
  // expose backend/ and other unrelated files over the dev server's /@fs/ route).
  server: { fs: { allow: ['.', '../shared'] } },
  test: { environment: 'node', include: ['src/**/*.test.ts'] },
})
