# Техническая документация

Учебный бэкенд на FastAPI с PostgreSQL и PostGIS: каталог казанских событий,
геопоиск, аналитика и синтетические бронирования.

- [Спецификация OpenAPI](openapi.yml)
- [О проекте](../README.md)

## Запуск в Docker

Нужна заранее созданная БД PostgreSQL с установленным PostGIS;
для учебного окружения используется `postgis/postgis:17-3.6`.
Пользователю БД нужны права на создание таблиц и расширения PostGIS,
если оно ещё не создано администратором.

Скопируйте [`.env.example`](../.env.example) в `.env` и задайте подключение к БД.
Из корня репозитория выполните:

```sh
docker build -t kazan-events-backend .
docker run --rm --name backend --network app-network --env-file .env kazan-events-backend
```

`app-network` — общая сеть PostgreSQL, бэкенда и NGINX фронтенда.
`PG_HOST` должен указывать на контейнер БД в этой сети.

При запуске приложение применяет миграцию и заполняет пустую БД демоданными.
Существующие данные сохраняются. При недоступности БД подключение повторяется,
а `/health/ready` возвращает HTTP 503 до успешной инициализации.
Этот адрес используется в Docker healthcheck; `/health/live` проверяет работу процесса.

## Переменные окружения

| Переменная | Назначение | По умолчанию |
| --- | --- | --- |
| `PG_HOST` | Адрес PostgreSQL | `db` |
| `PG_PORT` | Порт PostgreSQL | `5432` |
| `PG_DB_NAME` | Имя базы данных | Обязательная |
| `PG_USER_NAME` | Имя пользователя | Обязательная |
| `PG_USER_PASSWORD` | Пароль | Обязательная |
| `SEED_MODE` | `sample` — демоданные, `empty` — пустой каталог | `sample` |

Приложение не читает `.env` самостоятельно: в Docker его передаёт `--env-file`,
при локальном запуске переменные задаются в оболочке.

## Проксирование через NGINX

Фронтенд обращается к API по относительным URL `/api/v1/...`.
Добавьте в блок `server` NGINX:

```nginx
location /api/ {
    proxy_pass http://backend:8000;
    proxy_set_header Host $http_host;
}

location ~ ^/(docs|redoc|openapi\.json|health)(/|$) {
    proxy_pass http://backend:8000;
    proxy_set_header Host $http_host;
}
```

`backend` — имя контейнера бэкенда. Отсутствие `/` после порта в `proxy_pass`
сохраняет полный путь запроса. Swagger UI доступен по `/docs`, ReDoc — по `/redoc`,
схема API — по `/openapi.json`.

## Работа клиента с API

Клиент обходит коллекции по страницам, использует UUID и справочники из ответов
сервера и поддерживает пустой каталог. Учебную точку отсчёта `reference_time`
возвращает `GET /api/v1/meta`; она сохраняется после переноса БД.

Рейтинги, прогнозы, подбор событий, поиск дубликатов и конфликтов расписания
реализует клиент на основе данных и агрегатов API. CSV также разбирает клиент
и отправляет через `POST /api/v1/events/bulk` пакетами до 200 операций;
атомарность действует внутри одного пакета. Адрес и координаты задаются отдельно:
геокодирования и маршрутизации в сервере нет.

## Хранение и перенос БД

Учебное окружение: backend `1.0.0`, схема `2026_01_kazan`, PostgreSQL 17,
PostGIS 3.6. Фактические версии и размеры набора возвращает
`GET /api/v1/dataset/summary`.

Подключите volume PostgreSQL к `/var/lib/postgresql/data` и оставьте БД
во внутренней Docker-сети. Для переноса используйте логический дамп вместе
с метаданными набора:

```sh
docker exec db pg_dump -U postgres -d kazan_events -Fc --no-owner --no-acl -f /tmp/dataset.dump
docker cp db:/tmp/dataset.dump ./dataset.dump
```

В `dataset-manifest.json` сохраните ответ `/api/v1/dataset/summary` и добавьте
поле `sha256` с контрольной суммой дампа. Приостановите изменения данных
на время экспорта и получения счётчиков, чтобы манифест соответствовал архиву.
Перед восстановлением проверьте источник, контрольную сумму и совместимость версий.

Восстанавливайте дамп в новую БД до первого запуска бэкенда:

```sh
docker exec db createdb -U postgres -T template0 kazan_events_imported
docker cp ./dataset.dump db:/tmp/dataset.dump
docker exec db pg_restore -U postgres -d kazan_events_imported --no-owner --no-acl --single-transaction --exit-on-error /tmp/dataset.dump
```

Укажите `PG_DB_NAME=kazan_events_imported` и запустите бэкенд. Проверьте
`/health/ready`, совпадение `dataset.dataset_id`, `schema_version`, `reference_time`
и `counts` в `/api/v1/dataset/summary` с манифестом, а также `/api/v1/events/nearby`.
Повторный запуск сохраняет импортированные данные и не добавляет seed.

## Разработка и тесты

Нужен Python 3.12 или новее. Создайте и активируйте виртуальное окружение,
затем установите приложение:

```sh
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
python -m ruff check app
python -m ruff format --check app
python -m pytest -m "not integration"
```

Для локального запуска задайте `PG_*` в оболочке (`PG_HOST=127.0.0.1`,
если БД доступна на хосте) и выполните:

```sh
python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

Полный набор проверок запускается командой `python -m pytest`. Интеграционные
тесты требуют отдельный PostgreSQL с PostGIS и переменные `PG_*`. Фикстуры
создают и удаляют базы `test_events_*`; пользователю нужны соответствующие права
и право установки PostGIS. Без обязательных переменных эти тесты пропускаются.

Для проверки дампа дополнительно нужны Docker CLI и `TEST_POSTGRES_CONTAINER`
с именем или ID тестового контейнера PostgreSQL. Без этой переменной
пропускается только тест `pg_dump`/`pg_restore`.

Нагрузочный тест создаёт 10 000 событий, 2 000 площадок и 100 000 бронирований.
Он проверяет грубые регрессии с порогом 10 с на запрос. Целевые времена после
прогрева — список до 500 мс, геопоиск до 1 с, агрегаты до 2 с — измеряются отдельно
и зависят от окружения.

## GitHub Actions

- [Тесты](../.github/workflows/test.yml): lint, форматирование и полный pytest
  на Python 3.12 с PostgreSQL 17/PostGIS 3.6. Запускаются для pull request
  и push в `main`.
- [Docker](../.github/workflows/docker.yml): публикация в GHCR с тегами `latest`
  и `sha-<полный SHA коммита>` при push в `main`.
- [Swagger](../.github/workflows/swagger.yml): публикация OpenAPI и Swagger UI
  в GitHub Pages при push в `main`.

Пайплайны независимы и поддерживают ручной запуск; публикация доступна только
из `main`. Для GHCR используется `GITHUB_TOKEN`; если пакет уже существует,
репозиторию нужен доступ к нему через **Manage Actions access**.
Для Pages выберите **Settings → Pages → Source → GitHub Actions**.

[Опубликованный Swagger](https://nelkor.github.io/kazan-events/) служит справочником.
Для выполнения запросов используйте `/docs` работающего бэкенда.
