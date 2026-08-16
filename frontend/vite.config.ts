import { readFileSync } from 'node:fs'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// نسخه از `package.json` خوانده می‌شود، نه از یک ثابت دوم در کد.
//
// پیش از این در دو جا نوشته شده بود (`package.json` و `appInfo.ts`) با یادداشتی
// که «همگام نگهشان دارید» — و چیزی که باید دستی همگام بماند، دیر یا زود نمی‌ماند.
// حالا یک منبع دارد و فوتر همان را نشان می‌دهد که بسته‌بندی شده.
const pkg = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf8'))

export default defineConfig({
  plugins: [react(), tailwindcss()],
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
