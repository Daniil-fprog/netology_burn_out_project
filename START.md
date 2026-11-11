# Инструкция: запуск проекта в Docker без Docker Compose

Эта инструкция нужна для тренировки базовой работы с Docker на проекте, где есть два приложения:

- `backend` — Python/FastAPI-приложение;
- `frontend` — React-приложение (`frontend/app`, Vite): собирается в Docker и отдаётся через Nginx, запросы `/api/` и `/users/` Nginx проксирует в backend.

Цель: вручную собрать два Docker-образа, запустить два контейнера, связать их через Docker-сеть, посмотреть логи, зайти внутрь контейнеров, остановить, перезапустить и удалить их.

---

## 1. Основные команды Docker

### 1.1. `docker build`

```bash
docker build -t my-backend:1.0 ./backend
```

Команда собирает Docker-образ из Dockerfile.

Схема:

```text
Dockerfile → image
```

То есть Docker читает инструкции из `Dockerfile` и создаёт готовый образ приложения.

Пример:

```bash
docker build -t my-backend:1.0 ./backend
```

Здесь:

```text
docker build          собрать образ
-t my-backend:1.0     задать имя и тег образа
./backend             папка, где лежит Dockerfile backend
```

---

### 1.2. `docker run`

```bash
docker run -d --name my-backend-container my-backend:1.0
```

Команда запускает контейнер из образа.

Схема:

```text
image → container
```

Образ — это шаблон приложения.  
Контейнер — это запущенный экземпляр приложения.

---

### 1.3. `docker ps`

```bash
docker ps
```

Показывает запущенные контейнеры.

Если нужно увидеть все контейнеры, включая остановленные:

```bash
docker ps -a
```

---

### 1.4. `docker logs`

```bash
docker logs my-backend-container
```

Показывает вывод приложения и ошибки внутри контейнера.

Логи в реальном времени:

```bash
docker logs -f my-backend-container
```

Выйти из просмотра логов:

```bash
Ctrl + C
```

Контейнер при этом не остановится.

---

### 1.5. `docker exec`

```bash
docker exec -it my-backend-container sh
```

Позволяет зайти внутрь уже запущенного контейнера.

Например, внутри можно проверить файлы:

```bash
ls -la
pwd
```

Выйти из контейнера:

```bash
exit
```

---

### 1.6. `docker stop / start / restart`

Остановить контейнер:

```bash
docker stop my-backend-container
```

Запустить остановленный контейнер:

```bash
docker start my-backend-container
```

Перезапустить контейнер:

```bash
docker restart my-backend-container
```

---

### 1.7. `docker rm`

```bash
docker rm my-backend-container
```

Удаляет контейнер.

Важно: удалить можно только остановленный контейнер. Поэтому сначала обычно выполняют:

```bash
docker stop my-backend-container
docker rm my-backend-container
```

---

### 1.8. `docker rmi`

```bash
docker rmi my-backend:1.0
```

Удаляет Docker-образ.

Перед удалением образа нужно удалить контейнеры, которые были созданы из этого образа.

---

### 1.9. `docker network`

```bash
docker network create my-app-network
```

Создаёт Docker-сеть.

Сеть нужна, чтобы контейнеры могли обращаться друг к другу по имени.

Например, если backend и frontend находятся в одной сети, frontend-контейнер может обратиться к backend-контейнеру по имени контейнера.

---

### 1.10. `docker volume` / `-v`

```bash
-v "$(pwd)/data/db:/app/db"
```

Volume нужен, чтобы сохранить данные вне контейнера.

Например, если база данных лежит внутри контейнера, она может потеряться при удалении контейнера.

Чтобы данные сохранялись на компьютере, подключают папку с хоста внутрь контейнера.

Пример:

```bash
-v "$(pwd)/data/db:/app/db"
```

Это значит:

```text
папка ./data/db на компьютере
подключается как /app/db внутри контейнера
```

---

## 2. Полный тренировочный сценарий

Ниже полный сценарий запуска backend и frontend в двух контейнерах без Docker Compose.

---

### 2.1. Перейти в корень проекта

```bash
cd /path/to/project
```

Например структура проекта может быть такой:

```text
project/
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
└── frontend/
    ├── Dockerfile
    ├── src/
    └── nginx.conf
```

---

### 2.2. Собрать backend-образ

```bash
docker build -t my-backend:1.0 ./backend
```

После сборки можно проверить, что образ появился:

```bash
docker images
```

В списке должен быть образ:

```text
my-backend   1.0
```

---

### 2.3. Собрать frontend-образ

```bash
docker build -t my-frontend:1.0 ./frontend
```

Проверить:

```bash
docker images
```

В списке должны быть оба образа:

```text
my-backend    1.0
my-frontend   1.0
```

---

### 2.4. Создать Docker-сеть

```bash
docker network create my-app-network
```

Проверить список сетей:

```bash
docker network ls
```

Сеть нужна для того, чтобы backend и frontend могли находиться в одном изолированном Docker-пространстве.

---

### 2.5. Создать папку под базу данных

```bash
mkdir -p ./data/db
```

Эта папка будет находиться на компьютере, а внутри backend-контейнера будет доступна как:

```text
/app/db
```

Так база данных не потеряется при удалении контейнера.

---

### 2.6. Запустить backend-контейнер

```bash
docker run -d \
  --name my-backend-container \
  --network my-app-network \
  --restart unless-stopped \
  -p 8000:8000 \
  -v "$(pwd)/data/db:/app/db" \
  my-backend:1.0
```

Разбор команды:

```text
docker run                       запустить контейнер
-d                               запустить в фоне
--name my-backend-container      имя контейнера
--network my-app-network         подключить контейнер к Docker-сети
--restart unless-stopped         автоматически перезапускать, если контейнер упал
-p 8000:8000                     порт компьютера 8000 → порт контейнера 8000
-v "$(pwd)/data/db:/app/db"      подключить папку с базой данных
my-backend:1.0                   образ, из которого запускается контейнер
```

Проверить, что контейнер запущен:

```bash
docker ps
```

---

### 2.7. Запустить frontend-контейнер

```bash
docker run -d \
  --name my-frontend-container \
  --network my-app-network \
  --restart unless-stopped \
  -p 8080:80 \
  my-frontend:1.0
```

Разбор команды:

```text
docker run                         запустить контейнер
-d                                 запустить в фоне
--name my-frontend-container       имя контейнера
--network my-app-network           подключить к той же Docker-сети
--restart unless-stopped           автоматически перезапускать, если контейнер упал
-p 8080:80                         порт компьютера 8080 → порт контейнера 80
my-frontend:1.0                    образ frontend
```

Порт:

```text
8080:80
```

означает:

```text
localhost:8080 на компьютере
попадает на порт 80 внутри frontend-контейнера
```

---

### 2.8. Проверить запущенные контейнеры

```bash
docker ps
```

Ожидаемый результат:

```text
my-backend-container    Up    0.0.0.0:8000->8000/tcp
my-frontend-container   Up    0.0.0.0:8080->80/tcp
```

---

### 2.9. Открыть приложение

Backend Swagger:

```text
http://localhost:8000/docs
```

Frontend:

```text
http://localhost:8080
```

Если backend работает, страница `/docs` должна открыться.

Если frontend работает, должна открыться HTML-страница приложения.

---

## 3. Работа с логами

### 3.1. Посмотреть логи backend

```bash
docker logs my-backend-container
```

В логах backend можно увидеть:

- ошибки запуска;
- ошибки импорта Python-модулей;
- ошибки подключения к базе;
- вывод `print`;
- логи FastAPI/Uvicorn.

---

### 3.2. Посмотреть логи frontend

```bash
docker logs my-frontend-container
```

В логах frontend можно увидеть ошибки Nginx.

---

### 3.3. Смотреть логи backend в реальном времени

```bash
docker logs -f my-backend-container
```

Это удобно, когда приложение работает, а ты делаешь запросы из браузера и хочешь видеть, что происходит внутри контейнера.

Выйти:

```bash
Ctrl + C
```

---

## 4. Работа внутри контейнеров

### 4.1. Зайти внутрь backend-контейнера

```bash
docker exec -it my-backend-container sh
```

Внутри контейнера проверить файлы приложения:

```bash
ls -la /app
```

Проверить папку базы данных:

```bash
ls -la /app/db
```

Выйти из контейнера:

```bash
exit
```

---

### 4.2. Зайти внутрь frontend-контейнера

```bash
docker exec -it my-frontend-container sh
```

Проверить, что собранные файлы приложения скопировались в Nginx:

```bash
ls -la /usr/share/nginx/html
```

Проверить конфигурацию Nginx:

```bash
nginx -t
```

Выйти:

```bash
exit
```

---

## 5. Управление контейнерами

### 5.1. Остановить контейнеры

```bash
docker stop my-backend-container my-frontend-container
```

После этого контейнеры остановятся.

Проверить:

```bash
docker ps
```

Они исчезнут из списка запущенных контейнеров.

Но их можно увидеть так:

```bash
docker ps -a
```

---

### 5.2. Запустить контейнеры снова

```bash
docker start my-backend-container my-frontend-container
```

Проверить:

```bash
docker ps
```

---

### 5.3. Перезапустить backend-контейнер

```bash
docker restart my-backend-container
```

Это полезно, если нужно быстро перезапустить backend.

---

## 6. Удаление контейнеров, сети и образов

### 6.1. Удалить контейнеры

Сначала остановить:

```bash
docker stop my-backend-container my-frontend-container
```

Потом удалить:

```bash
docker rm my-backend-container my-frontend-container
```

Проверить:

```bash
docker ps -a
```

---

### 6.2. Удалить Docker-сеть

```bash
docker network rm my-app-network
```

Если сеть используется запущенными контейнерами, Docker не даст её удалить. Сначала нужно остановить и удалить контейнеры.

---

### 6.3. Удалить образы

```bash
docker rmi my-backend:1.0
docker rmi my-frontend:1.0
```

Если Docker пишет, что образ используется контейнером, значит сначала нужно удалить контейнеры через `docker rm`.

---

## 7. Краткая шпаргалка команд

```bash
# перейти в проект
cd /path/to/project

# собрать backend
docker build -t my-backend:1.0 ./backend

# собрать frontend
docker build -t my-frontend:1.0 ./frontend

# создать сеть
docker network create my-app-network

# создать папку под базу
mkdir -p ./data/db

# запустить backend
docker run -d \
  --name my-backend-container \
  --network my-app-network \
  --restart unless-stopped \
  -p 8000:8000 \
  -v "$(pwd)/data/db:/app/db" \
  my-backend:1.0

# запустить frontend
docker run -d \
  --name my-frontend-container \
  --network my-app-network \
  --restart unless-stopped \
  -p 8080:80 \
  my-frontend:1.0

# посмотреть запущенные контейнеры
docker ps

# посмотреть все контейнеры, включая остановленные
docker ps -a

# открыть backend
# http://localhost:8000/docs

# открыть frontend
# http://localhost:8080

# посмотреть логи backend
docker logs my-backend-container

# посмотреть логи frontend
docker logs my-frontend-container

# смотреть логи backend в реальном времени
docker logs -f my-backend-container

# зайти внутрь backend
docker exec -it my-backend-container sh

# зайти внутрь frontend
docker exec -it my-frontend-container sh

# остановить контейнеры
docker stop my-backend-container my-frontend-container

# запустить контейнеры снова
docker start my-backend-container my-frontend-container

# перезапустить backend
docker restart my-backend-container

# удалить контейнеры
docker stop my-backend-container my-frontend-container
docker rm my-backend-container my-frontend-container

# удалить сеть
docker network rm my-app-network

# удалить образы
docker rmi my-backend:1.0
docker rmi my-frontend:1.0
```

---

## 8. Что важно понять после тренировки

После выполнения этой инструкции нужно понимать:

```text
Dockerfile — инструкция для сборки образа.

Image / образ — готовый шаблон приложения.

Container / контейнер — запущенный экземпляр образа.

Port / порт — способ открыть приложение из контейнера наружу.

Network / сеть — способ связать контейнеры между собой.

Volume / -v — способ сохранить данные вне контейнера.

Logs / логи — основной способ искать ошибки.

Restart policy — правило автоматического перезапуска контейнера.
```

Главная схема:

```text
Dockerfile → docker build → image → docker run → container
```

Для проекта с backend и frontend:

```text
backend Dockerfile → backend image → backend container
frontend Dockerfile → frontend image → frontend container
```

Docker-сеть нужна, чтобы контейнеры могли взаимодействовать друг с другом, а проброс портов нужен, чтобы открыть приложение из браузера на компьютере.