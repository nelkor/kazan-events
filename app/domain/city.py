"""City-specific vocabulary and map defaults shared by all application layers."""

from typing import Literal

CITY_NAME = "Казань"
CITY_NAME_EN = "Kazan"
CITY_SLUG = "kazan-events"
# Часовой пояс Казани (UTC+03:00).
CITY_TIMEZONE = "Europe/Moscow"

CityName = Literal["Казань"]
DistrictCode = Literal["AVIA", "VAH", "KIR", "MOS", "NSAV", "PRIV", "SOV"]

# Семь районов города: https://my.kzn.ru/ (раздел «Районы Казани»).
# Коды — стабильные идентификаторы этого API, а не официальные коды районов.
DISTRICTS = {
    "AVIA": "Авиастроительный район",
    "VAH": "Вахитовский район",
    "KIR": "Кировский район",
    "MOS": "Московский район",
    "NSAV": "Ново-Савиновский район",
    "PRIV": "Приволжский район",
    "SOV": "Советский район",
}

# Театр оперы и балета: площадь Свободы, 2; первая демонстрационная площадка.
CONTROL_POINT = {"latitude": 55.795518, "longitude": 49.124544, "radius_m": 3000}
