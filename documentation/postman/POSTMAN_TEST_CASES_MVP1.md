# Тест-кейсы Postman для MVP 1

Используйте коллекцию `BurnOut_MVP1.postman_collection.json`. Выполняйте разделы по порядку: `01` → `08`.

## 1. Подготовка

1. Запустите backend на `http://127.0.0.1:8000`.
2. В переменной коллекции `base_url` укажите адрес backend.
3. По умолчанию используется администратор:
   - логин: `daniil`;
   - пароль: `admin123`.
4. Укажите даты:
   - `test_date` — дата нагрузки и дневного опроса, например `2026-11-18`;
   - `date_from` — начало периода, например `2026-11-01`;
   - `date_to` — конец периода, например `2026-11-30`.

ID и токены коллекция сохраняет автоматически.

## 2. Система и авторизация

| Проверка | Что отправить | Что должно произойти |
|---|---|---|
| Health check | `GET /health` | `200`, тело `{"status":"ok"}` |
| API v1 | `GET /api/v1/home` | `200`, сообщение `FastAPI работает` |
| Вход администратора | `POST /api/v1/users/login` с `daniil/admin123` | `200`, получен `access_token` |
| Неверный пароль | Тот же запрос с неправильным паролем | `401` |
| Регистрация преподавателя | `name`, уникальный `login`, `password` | `200`, получен числовой `id` |
| Повторный логин | Зарегистрировать пользователя с тем же `login` | `400` |
| Запрос без JWT | `GET /api/v1/users/me` без Bearer Token | `401` |
| Текущий пользователь | `GET /api/v1/users/me` с JWT | `200`, данные владельца токена |

Пример регистрации:

```json
{
  "name": "Тестовый преподаватель",
  "login": "teacher_test_1",
  "password": "postman123",
  "phone": null
}
```

## 3. Права system_admin

| Проверка | Что отправить | Что должно произойти |
|---|---|---|
| Список пользователей | `GET /api/v1/users/` с токеном администратора | `200`, массив пользователей |
| Пользователь по ID | `GET /api/v1/users/{teacher_user_id}` | `200`, массив с одним пользователем |
| Запрет для teacher | Повторить эти запросы с токеном преподавателя | `403` |
| Создание школы администратором | `POST /api/v1/schools` | `201`, получен `school_id` |
| Запрет создания школы | Повторить с токеном преподавателя | `403` |
| Глобальный доступ администратора | `GET /api/v1/schools` | `200`, созданная школа есть в списке без отдельного доступа администратора |

Тело создания школы:

```json
{
  "name": "Тестовая школа",
  "external_code": "school-test-1"
}
```

## 4. Преподаватель и доступ к школе

### Создание профиля

`POST /api/v1/schools/{school_id}/teachers` с токеном администратора:

```json
{
  "user_id": {{teacher_user_id}},
  "external_id": "teacher-test-1",
  "full_name": "Тестовый преподаватель",
  "subject": "Математика"
}
```

Ожидается: `201`, в ответе есть строковый `id`. Он сохраняется как `teacher_id`.

### Выдача доступа

`POST /api/v1/schools/{school_id}/access`:

```json
{
  "user_id": {{teacher_user_id}},
  "role": "teacher"
}
```

Ожидается: `201`, возвращены `user_id`, `school_id`, `role=teacher`.

Дополнительные проверки:

- повторная выдача доступа тому же пользователю — `409`;
- роль `teacher` без связанного профиля `teachers.user_id` — `422`;
- создание преподавателя обычным пользователем — `403`;
- `GET /api/v1/schools/{school_id}/teachers?page=1&page_size=50` — `200`, созданный преподаватель находится в `items`.

## 5. Виды работ

| Проверка | Что отправить | Что должно произойти |
|---|---|---|
| Список | `GET /api/v1/work-types?include_archived=false` | `200`, массив активных видов работ |
| Создание | `POST /api/v1/work-types` | `201`, создан новый вид работы |
| Изменение | `PATCH /api/v1/work-types/{id}` | `200`, поля изменены |
| Архивирование | `POST /api/v1/work-types/{id}/archive` | `200`, `is_active=false` |
| Запрет для teacher | Создание, изменение или архивирование с JWT teacher | `403` |

Тело создания:

```json
{
  "code": "postman_test",
  "name": "Тестовая работа",
  "category_group": "other",
  "complexity_weight": 0.1,
  "requires_comment": false
}
```

Для повторного запуска измените `code`, так как он должен быть уникальным.

## 6. Фактическая нагрузка преподавателя

Выполняйте с токеном преподавателя.

### Создание дневной записи

`POST /api/v1/schools/{school_id}/workload/daily`:

```json
{
  "teacher_id": "{{teacher_id}}",
  "work_date": "{{test_date}}",
  "day_type": "Учебный день",
  "status": "draft",
  "comment": "Тест Postman",
  "entries": [
    {
      "duration_hours": 2.5,
      "unit": "clock_hour",
      "work_type_id": "{{work_type_id}}",
      "location": "school",
      "comment": "Проведение занятий"
    }
  ]
}
```

Ожидается: `201`, `actual.id` сохраняется как `daily_log_id`, `actual.total_hours=2.5`.

### Изменение записи

`PATCH /api/v1/schools/{school_id}/workload/daily/{daily_log_id}`:

```json
{
  "status": "completed",
  "comment": "Рабочий день завершён"
}
```

Ожидается: `200`, `actual.status=completed`, `actual.total_complete=true`.

### Просмотр

- `GET .../workload/daily?date_from=...&date_to=...` — `200`, запись находится в `items`;
- `GET .../workload/weekly?week_from=...&week_to=...` — `200`, есть `actual_hours` и `completed_days`.

### Ошибки

- повторная запись того же преподавателя на ту же дату — `409`;
- чужой `teacher_id` — `403`;
- неизвестный или архивный `work_type_id` — `422`;
- сумма работ больше 24 часов — `422`;
- неправильный `sort` — `422`.

## 7. Опросы и согласие

Выполняйте с токеном преподавателя.

### Каталог

| Запрос | Ожидается |
|---|---|
| `GET .../surveys` | `200`, доступны `daily_checkin`, `weekly_reflection`, `monthly_wellbeing` |
| `GET .../surveys/daily_checkin` | `200`, текущая версия опроса |
| `GET .../surveys/daily_checkin/versions/1.0.0` | `200`, версия `1.0.0` |

### Согласие

`POST /api/v1/schools/{school_id}/teachers/{teacher_id}/survey-consents`:

```json
{
  "policy_version": "1.0",
  "purpose": "survey_storage",
  "method": "web",
  "proof_reference": "postman"
}
```

Ожидается: `201`, получен `consent_id`.

### Создание черновика

`POST /api/v1/schools/{school_id}/survey-responses`:

```json
{
  "survey_code": "daily_checkin",
  "survey_version": "1.0.0",
  "assessment_date": "{{test_date}}",
  "period_start": "{{test_date}}",
  "period_end": "{{test_date}}",
  "comment_reference_date": "{{test_date}}",
  "source": "web_form",
  "status": "draft",
  "consent_record_id": "{{consent_id}}",
  "answers": {
    "fatigue_score": 3,
    "stress_score": 2
  }
}
```

Ожидается: `201`, статус `draft`, получен `survey_response_id`.

### Заполнение и отправка

1. `PATCH .../survey-responses/{survey_response_id}` с заголовком `If-Match: 1` и всеми обязательными ответами — `200`, `lock_version` увеличен.
2. `POST .../survey-responses/{survey_response_id}/submit` — `200`, статус `submitted`.
3. `GET .../survey-responses/{survey_response_id}` — `200`, ответы доступны владельцу.
4. `GET .../survey-responses?teacher_id=...` — `200`, ответ находится в `items`.
5. `GET .../teachers/{teacher_id}/survey-history` — `200`, ответ находится в истории.

Проверки ошибок:

- отправка без действующего согласия `survey_storage` — `403`;
- отсутствие обязательного ответа — `422`;
- значение шкалы меньше 1 или больше 5 — `422`;
- неизвестный код вопроса — `422`;
- второй активный ответ за тот же период — `409`;
- изменение уже отправленного ответа через `PATCH` — `409`.

## 8. Аналитика и экспорт

Выполняйте с JWT администратора до отзыва ответа.

| Проверка | Что отправить | Что должно произойти |
|---|---|---|
| Охват | `GET .../survey-analytics/completion?date_from=...&date_to=...` | `200`, для преподавателя есть `completed`, `expected`, `completion_rate` |
| Нагрузка и самочувствие | `GET .../teachers/{teacher_id}/workload-and-wellbeing?date_from=...&date_to=...` | `200`, запись содержит `workload` и `surveys` |
| Экспорт JSON | `GET .../surveys/exports?format=json&report=responses` | `200`, преподаватель указан как `teacher_key`, сырого ФИО нет |
| Экспорт CSV | Изменить `format` на `csv` | `200`, скачивается CSV |
| Экспорт XLSX | Изменить `format` на `xlsx` | `200`, скачивается XLSX |

## 9. Импорт шаблонов опросов

В запросе `Импорт шаблонов опросов` выберите файл:

`app/backend/app/data/teacher_wellbeing_surveys.json`

- `dry_run=true` — ожидается `200`, `valid=true`, показано количество шаблонов и вопросов;
- `dry_run=false` — ожидается `200`, совместимые шаблоны импортированы или пропущены как уже существующие;
- повреждённый JSON — `400`;
- запрос с JWT преподавателя — `403`.

## 10. Отзыв данных

Эти запросы выполняйте последними.

1. `POST .../survey-responses/{survey_response_id}/withdraw` — `200`, статус `withdrawn`.
2. Повторный отзыв ответа — `200`, состояние не меняется.
3. `POST .../survey-consents/{consent_id}/withdraw` — `200`, заполнено `withdrawn_at`.
4. Попытка отправить новый ответ с отозванным согласием — `403`.

## 11. Проверка аудита

Публичного endpoint для чтения аудита в MVP 1 нет. После тестов проверьте SQLite:

```sql
SELECT action, entity_type, entity_id, school_id, actor_id, changed_at
FROM audit_events
ORDER BY changed_at DESC;
```

Должны присутствовать события:

- `create / school`;
- `create / teacher`;
- `grant / user_school_access`;
- `create / work_type` и его изменение/архивирование;
- `create / daily_work_logs` и `update / daily_work_logs`;
- `create / survey_consent`;
- `export / surveys`;
- `withdraw / survey_response`;
- `withdraw / survey_consent`.

