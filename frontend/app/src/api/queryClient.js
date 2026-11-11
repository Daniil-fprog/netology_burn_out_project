import { QueryClient } from '@tanstack/react-query';

// Один клиент на приложение: одинаковые запросы с одинаковым ключом выполняются
// один раз, результат переиспользуется всеми компонентами (без дублей к API).
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      gcTime: 5 * 60_000,
      refetchOnWindowFocus: false,
      retry: (count, err) => !(err?.status >= 400 && err?.status < 500) && count < 1,
    },
    mutations: { retry: false },
  },
});
