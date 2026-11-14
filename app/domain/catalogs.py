from app.domain.city import DISTRICTS as DISTRICTS

SCHEMA_VERSION = "2026_01_kazan"
SEED_VERSION = "kazan_sample_1"

# Русские названия остаются предметными данными, а не сообщениями сервера.
GENRES = {
    "concert": "Концерт",
    "theatre": "Театр",
    "standup": "Стендап",
    "lecture": "Лекция",
    "exhibition": "Выставка",
    "festival": "Фестиваль",
    "cinema": "Кино",
    "workshop": "Мастер-класс",
    "excursion": "Экскурсия",
}
AGE_RATINGS = (0, 6, 12, 16, 18)
EVENT_STATUSES = ("draft", "published", "cancelled", "archived")
RESERVATION_STATUSES = ("confirmed", "cancelled")
