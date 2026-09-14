import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig(({ command }) => ({
  plugins: [vue()],

  // build 产物落在 FastAPI 的 /static 下，所以静态资源必须带 /static/ 前缀，
  // 否则 index.html 会去请求 /assets/xxx.js —— 那个路径后端没挂，直接 404。
  base: command === 'build' ? '/static/' : '/',

  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) }
  },

  build: {
    outDir: '../server/static',
    emptyOutDir: true,
    chunkSizeWarningLimit: 800,
    rollupOptions: {
      output: {
        // Element Plus 全量 1MB+，单独切出来，业务代码改动时浏览器缓存不失效
        manualChunks: {
          vendor: ['vue', 'pinia', 'axios'],
          ui: ['element-plus', '@element-plus/icons-vue'],
          md: ['markdown-it']
        }
      }
    }
  },

  server: {
    // dev 模式代理后端，避免 CORS
    proxy: {
      '/api': { target: 'http://127.0.0.1:8800', changeOrigin: true, rewrite: p => p.replace(/^\/api/, '') }
    }
  }
}))
