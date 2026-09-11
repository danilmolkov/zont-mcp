"""Декодирование формата Delta-time Array (DTA), используемого ZONT API в load_data.

DTA — это массив пар [время, значение], где первая метка времени абсолютная
(unix time, секунды с 1970-01-01 UTC), а каждая последующая — либо снова
абсолютная (если положительная), либо разница в секундах от предыдущей метки
(если отрицательная: |значение| нужно ПРИБАВИТЬ к предыдущей метке). См. раздел
«Формат Delta-time Array» в https://zont-online.ru/api/docs/.

Проверено на реальных данных устройства: при смене целевой температуры контура
ГВС в 1789121580 (unix time) сервер вернул точку [-6540, 45] от базовой метки
1789115040 — 1789115040 - (-6540) = 1789121580. Совпадает с фактическим временем
изменения, подтверждённым отдельно через zont_list_devices.
"""

from __future__ import annotations

from typing import Any


def _looks_like_dta(value: Any) -> bool:
    if not isinstance(value, list) or not value:
        return False
    for item in value:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            return False
        if not isinstance(item[0], int) or isinstance(item[0], bool):
            return False
    return True


def decode_dta(raw: list) -> list[dict[str, Any]]:
    """Раскодировать один DTA-массив в список {"time": <unix>, "value": ...}."""
    result: list[dict[str, Any]] = []
    ts = 0
    for i, (t, value) in enumerate(raw):
        if i == 0 or t >= 0:
            ts = t
        else:
            ts = ts - t
        result.append({"time": ts, "value": value})
    return result


def decode_timeseries(value: Any) -> Any:
    """Рекурсивно найти и раскодировать все DTA-массивы внутри структуры ответа."""
    if _looks_like_dta(value):
        return decode_dta(value)
    if isinstance(value, dict):
        return {k: decode_timeseries(v) for k, v in value.items()}
    if isinstance(value, list):
        return [decode_timeseries(v) for v in value]
    return value
