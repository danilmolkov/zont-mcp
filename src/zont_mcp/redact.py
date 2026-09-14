"""Маскирование чувствительных полей в ответах ZONT API.

Метод devices (и вложенный z3k_config) возвращает секреты устройства целиком:
пароль подключения устройства к серверу ZONT, пароль домашнего Wi-Fi, IMEI, ICCID
SIM-карты, номер телефона владельца и т.д. По умолчанию эти поля маскируются
перед тем, как ответ увидит модель — вызывающий может явно запросить полные
данные (см. reveal_sensitive в zont_list_devices), когда они действительно нужны.
"""

from __future__ import annotations

from typing import Any

REDACTED = "***REDACTED***"

# Ключи, чьё скалярное значение целиком заменяется на REDACTED.
_SENSITIVE_KEYS = {
    "password",
    "pass",
    "usbpassword",
    "tel_password",
    "imei",
    "phone",
    "foreign_msisdn",
}

# Ключи, чей объект целиком (со всеми вложенными полями) заменяется на REDACTED —
# для них незачем сохранять частичную структуру (например ICCID вместе с датой).
_SENSITIVE_OBJECT_KEYS = {
    "iccid",
    "stationary_location",  # {"loc": [lon, lat]} — координаты объекта
    "location",  # z3k_config.location: {"x": ..., "y": ...} — координаты объекта
}


def redact_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, val in value.items():
            key_lower = key.lower()
            if val in (None, "", False):
                result[key] = val
            elif key_lower in _SENSITIVE_OBJECT_KEYS:
                result[key] = REDACTED
            elif key_lower in _SENSITIVE_KEYS:
                result[key] = REDACTED
            else:
                result[key] = redact_sensitive(val)
        return result
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    return value
