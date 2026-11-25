# Инструкция: отдельный запуск backend

Backend проекта — это приложение на FastAPI. Ниже описаны два способа его запуска без frontend:

1. локально при помощи Uvicorn;
2. в отдельном Docker-контейнере.

После запуска backend будет доступен по адресу <http://localhost:8000>.

Полезные адреса:

- Swagger UI: <http://localhost:8000/docs>;
- проверка состояния: <http://localhost:8000/health>;
- OpenAPI-схема: <http://localhost:8000/openapi.json>.

---

## 1. Запуск при помощи Uvicorn

### 1.1. Перейти в каталог backend

Все команды этого раздела выполняются из каталога `app/backend`:

```bash
cd app/backend
```

### 1.2. Создать и активировать виртуальное окружение

Создать окружение:

```bash
python3 -m venv .venv
```

Активировать его в Linux или macOS:

```bash
source .venv/bin/activate
```

В Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

### 1.3. Установить зависимости

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

Файл `requirements-dev.txt` устанавливает зависимости backend и инструменты для тестирования.

### 1.4. Применить миграции базы данных

```bash
alembic upgrade head
```

По умолчанию используется SQLite-база:

```text
db_store/burn_out.db
```

При первом запуске приложение добавит начальные роли, виды работ, административную учётную запись и шаблоны опросов.

### 1.5. Запустить Uvicorn

Режим разработки с автоматической перезагрузкой после изменения файлов:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Здесь:

```text
app.main:app       объект app из файла app/main.py
--host 0.0.0.0     принимать подключения на всех сетевых интерфейсах
--port 8000        использовать порт 8000
--reload           перезапускать сервер после изменения исходного кода
```

Проверить работу backend можно командой:

```bash
curl http://localhost:8000/health
```

Ожидаемый ответ:

```json
{"status":"ok"}
```

Чтобы остановить сервер, нажмите `Ctrl + C`.

Чтобы выйти из виртуального окружения, выполните:

```bash
deactivate
```

### 1.6. Подключение к PostgreSQL вместо SQLite

Перед миграцией и запуском задайте переменную `DATABASE_URL`:

```bash
export DATABASE_URL='postgresql+psycopg://user:password@localhost:5432/teacher_workload'
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

PostgreSQL должен быть запущен заранее, а база данных из строки подключения — создана.

---

## 2. Запуск backend при помощи Docker

Для этого способа нужны установленные и запущенные Docker Engine или Docker Desktop. Команды также выполняются из каталога `app/backend`.

### 2.1. Собрать Docker-образ

```bash
docker build -t mindmood-backend:local .
```

Здесь:

```text
docker build                 собрать образ
-t mindmood-backend:local    задать имя и тег образа
.                            использовать Dockerfile из текущего каталога
```

Проверить созданный образ:

```bash
docker images mindmood-backend
```

### 2.2. Создать каталоги для постоянных данных

```bash
mkdir -p ../data/backend-db ../data/cache
```

В `../data/backend-db` будут храниться SQLite-база и загруженные файлы, а в `../data/cache` — кэш ML-моделей. Эти данные сохранятся после удаления контейнера.

### 2.3. Запустить контейнер

```bash
docker run -d \
  --name mindmood-backend \
  --restart unless-stopped \
  -p 8000:8000 \
  -e DATABASE_URL=sqlite:////app/db_store/burn_out.db \
  -v "$(pwd)/../data/backend-db:/app/db_store" \
  -v "$(pwd)/../data/cache:/app/.cache/huggingface" \
  mindmood-backend:local \
  sh -c 'alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000'
```

Перед запуском Uvicorn контейнер применит миграции Alembic. Поэтому команда подходит и для первого запуска с пустой базой.

Основные параметры:

```text
-d                    запустить контейнер в фоне
--name                 задать имя контейнера
--restart              перезапускать контейнер после сбоя или перезагрузки Docker
-p 8000:8000           открыть порт backend на компьютере
-e DATABASE_URL=...    указать путь к SQLite внутри контейнера
-v                     подключить каталоги с постоянными данными
```

На Windows PowerShell вместо `$(pwd)` используйте `${PWD}`.

### 2.4. Проверить контейнер и backend

Показать запущенный контейнер:

```bash
docker ps --filter name=mindmood-backend
```

Посмотреть логи:

```bash
docker logs mindmood-backend
```

Следить за логами в реальном времени:

```bash
docker logs -f mindmood-backend
```

Проверить endpoint состояния:

```bash
curl http://localhost:8000/health
```

### 2.5. Управление контейнером

Остановить:

```bash
docker stop mindmood-backend
```

Снова запустить:

```bash
docker start mindmood-backend
```

Перезапустить:

```bash
docker restart mindmood-backend
```

Зайти внутрь работающего контейнера:

```bash
docker exec -it mindmood-backend sh
```

### 2.6. Пересобрать backend после изменения кода

Остановить и удалить старый контейнер:

```bash
docker stop mindmood-backend
docker rm mindmood-backend
```

Собрать образ заново:

```bash
docker build -t mindmood-backend:local .
```

После этого повторите команду `docker run` из раздела 2.3.

Каталог `../data` при удалении контейнера не удаляется, поэтому база данных и кэш сохраняются.

---

## 3. Частые проблемы

### Порт 8000 уже занят

Остановите процесс или контейнер, который использует порт. Либо в полной команде `docker run` из раздела 2.3 замените публикацию порта:

```bash
-p 8001:8000
```

В этом случае backend будет доступен по адресу <http://localhost:8001>.

### Контейнер сразу остановился

Посмотрите причину в логах:

```bash
docker ps -a --filter name=mindmood-backend
docker logs mindmood-backend
```

### Изменения Python-кода не появились в Docker

Исходный код копируется в образ во время `docker build`. После его изменения удалите старый контейнер, пересоберите образ и запустите новый контейнер.

### Нужно полностью очистить Docker-базу

Сначала остановите и удалите контейнер. Затем вручную удалите содержимое каталога `../data/backend-db`. Это необратимо удалит локальные данные backend, поэтому перед очисткой при необходимости сделайте резервную копию.
