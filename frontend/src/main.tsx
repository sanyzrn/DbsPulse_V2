import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
// فونت self-host به‌جای Google Fonts: بدون وابستگی به CDN خارجی (فیلترینگ/تحریم)،
// بدون نشت IP کاربران، و سازگار با CSP سخت‌گیرانه
import '@fontsource/vazirmatn/400.css'
import '@fontsource/vazirmatn/500.css'
import '@fontsource/vazirmatn/700.css'
import './index.css'
import App from './App.tsx'
import { AuthProvider } from './auth/AuthContext.tsx'
import { ErrorBoundary } from './components/ErrorBoundary.tsx'
import { ToastProvider } from './components/Toast.tsx'
import { ConfirmProvider } from './components/ConfirmDialog.tsx'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // خطاهای 401/403/404 با تلاش دوباره درست نمی‌شوند؛ فقط خطای شبکه یک‌بار retry می‌شود
      retry: 1,
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <ConfirmProvider>
            <AuthProvider>
              <ErrorBoundary title="مشکلی در بارگذاری برنامه پیش آمد">
                <App />
              </ErrorBoundary>
            </AuthProvider>
          </ConfirmProvider>
        </ToastProvider>
      </QueryClientProvider>
    </BrowserRouter>
  </StrictMode>,
)
