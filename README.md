# Казанские события

HTTP-сервер казанских событий для запуска в контейнере.
Используется в лабораторных работах авторского курса по DevOps.

- [Swagger](https://nelkor.github.io/kazan-events)
- [Документация](docs/README.md)
- [Спецификация OpenAPI](docs/openapi.yml)

Имя образа Docker: `ghcr.io/nelkor/kazan-events`.

Для работы нужен PostgreSQL с расширением PostGIS. Параметры подключения
задаются через [переменные окружения](docs/README.md#переменные-окружения);
пример — [`.env.example`](.env.example).
