import { defineConfig } from 'vite';

export default defineConfig({
  build: {
    target: 'es2020',
    // three.js is only fetched when a 3D chapter approaches the viewport
    chunkSizeWarningLimit: 650,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/three')) return 'three';
          if (id.includes('node_modules/gsap')) return 'gsap';
        },
      },
    },
  },
});
