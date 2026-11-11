# Frontend

React + Vite + Ant Design + TanStack Query.

## Запуск для разработки

```bash
cd frontend/app
npm install
npm run dev
```

Открыть http://127.0.0.1:5173. По умолчанию `npm run dev` работает на заглушках API: логины `teacher`, `director`, `head`, `group_head`, `admin`, пароль `demo`.

Чтобы работать с настоящим backend (должен быть запущен на `localhost:8000`):

```bash
VITE_API_MODE=real npm run dev
```

## Сборка

`npm run build` всегда собирает с настоящим backend, код заглушек в сборку не попадает. В Docker фронт собирается так же: `docker compose up --build`, приложение на http://localhost:8080.
