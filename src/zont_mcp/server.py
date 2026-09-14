"""MCP-сервер для API ZONT."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any, Literal, Optional

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from .client import ZontApiError, client_from_env
from .redact import redact_sensitive
from .timeseries import decode_timeseries

mcp = MCPServer("zont-mcp")
_client = None


def _get_client():
    global _client
    if _client is None:
        _client = client_from_env()
    return _client


async def _call(method: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        return await _get_client().post(method, body)
    except ZontApiError as exc:
        # ToolError messages are passed through to the caller; other exceptions are
        # masked by the framework, so ZONT's error_ui would otherwise be hidden.
        raise ToolError(str(exc)) from exc


# --- Аутентификация ---------------------------------------------------


@mcp.tool()
async def zont_get_authtoken(client_name: str) -> dict[str, Any]:
    """Получить долгоживущий аутентификационный токен ZONT по логину/паролю.

    Требует, чтобы сервер был запущен с ZONT_LOGIN и ZONT_PASSWORD. Полученный
    токен можно передать в переменную окружения ZONT_TOKEN для последующих запусков.

    client_name: человекопонятное название приложения, запрашивающего токен.
    """
    return await _call("get_authtoken", {"client_name": client_name})


# --- Устройства ---------------------------------------------------------


@mcp.tool()
async def zont_list_devices(
    load_io: Optional[bool] = None, reveal_sensitive: Optional[bool] = False
) -> dict[str, Any]:
    """Получить список всех устройств пользователя ZONT и их настроек.

    По умолчанию чувствительные поля (пароль устройства для подключения к серверу
    ZONT, пароль домашнего Wi-Fi, IMEI, ICCID SIM-карты, номер телефона владельца)
    маскируются значением "***REDACTED***", так как метод devices отдаёт их в
    открытом виде. Запрашивай reveal_sensitive=true только когда эти данные
    действительно нужны (например, перед переносом Wi-Fi-сети на новый роутер).

    load_io: возвращать ли в поле io текущие состояния каждого устройства.
    reveal_sensitive: вернуть чувствительные поля без маскирования.
    """
    data = await _call("devices", {"load_io": load_io})
    return data if reveal_sensitive else redact_sensitive(data)


@mcp.tool()
async def zont_add_device(
    devtype: str,
    name: str,
    serial: str,
    timezone: int,
    tel_password: Optional[str] = None,
    notes: Optional[str] = None,
    wifi_credentials: Optional[list[dict[str, str]]] = None,
    boiler_vendor: Optional[str] = None,
    boiler_model: Optional[str] = None,
) -> dict[str, Any]:
    """Добавить новое устройство в аккаунт пользователя ZONT.

    devtype: идентификатор типа устройства, например T100, T102, L1000, ZTC-700, SX250 и т.д.
    name: название устройства для пользователя.
    serial: серийный номер устройства.
    timezone: часовой пояс устройства.
    tel_password: телефонный пароль для GSM-устройств (только цифры).
    notes: произвольные заметки об устройстве.
    wifi_credentials: параметры Wi-Fi сетей вида [{"ssid": ..., "password": ...}] (только для устройств с Wi-Fi).
    boiler_vendor: производитель котла.
    boiler_model: модель котла.
    """
    return await _call(
        "add_device",
        {
            "devtype": devtype,
            "name": name,
            "serial": serial,
            "timezone": timezone,
            "tel_password": tel_password,
            "notes": notes,
            "wifi_credentials": wifi_credentials,
            "boiler_vendor": boiler_vendor,
            "boiler_model": boiler_model,
        },
    )


@mcp.tool()
async def zont_delete_device(
    device_id: int,
    transfer: Optional[bool] = None,
    transfer_username: Optional[str] = None,
    clear_access: Optional[bool] = None,
    clear_data: Optional[bool] = None,
) -> dict[str, Any]:
    """Удалить устройство из аккаунта пользователя ZONT (или передать другому пользователю).

    device_id: ID устройства.
    transfer: передать устройство другому пользователю вместо удаления.
    transfer_username: логин пользователя-получателя (только если transfer=true).
    clear_access: отозвать доступ других пользователей к устройству.
    clear_data: удалить все накопленные данные устройства.
    """
    return await _call(
        "delete_device",
        {
            "device_id": device_id,
            "transfer": transfer,
            "transfer_username": transfer_username,
            "clear_access": clear_access,
            "clear_data": clear_data,
        },
    )


@mcp.tool()
async def zont_update_device(device_id: int, settings: dict[str, Any]) -> dict[str, Any]:
    """Изменить настройки устройства ZONT.

    Например режим термостата, целевые температуры, доверенные номера и т.д.
    Передайте только те поля настроек, которые нужно изменить — остальные сохранят
    прежние значения. Полный список возможных настроек описан в разделе «Параметры
    устройств» документации ZONT API (общие, беспроводная сеть, автомобиль, отопление).

    device_id: ID устройства.
    settings: объект настроек устройства, которые нужно изменить, например
        {"thermostat_mode_temps": {"comfort": 21}}.
    """
    return await _call("update_device", {"device_id": device_id, **settings})


@mcp.tool()
async def zont_set_io_port(
    device_id: int,
    portname: Literal["guard-state", "siren", "engine-block", "webasto", "auto-ignition"],
    type: Literal["bool", "string", "auto-ignition"],
    value: Any,
) -> dict[str, Any]:
    """Отправить устройству команду на изменение состояния.

    Управляет охраной (guard-state), сиреной (siren), блокировкой двигателя
    (engine-block), подогревателем (webasto) или автозапуском (auto-ignition).
    Команда доставляется, только когда устройство на связи.

    portname: имя состояния, которым нужно управлять.
    type: тип значения — "string" для guard-state, "auto-ignition" для auto-ignition,
        "bool" для остальных.
    value: требуемое значение — true/false для bool; "enabled"/"disabled" для
        guard-state; объект {"state": ..., "time"?: ...} для auto-ignition.
    """
    return await _call(
        "set_io_port",
        {"device_id": device_id, "portname": portname, "type": type, "value": value},
    )


@mcp.tool()
async def zont_send_custom_command(device_id: int, command_id: int) -> dict[str, Any]:
    """Отправить устройству (ZTC-7xx, Mega SX) пользовательскую команду.

    Команды заданы в настроечной утилите. Идентификатор команды берётся из
    настройки custom_controls устройства (см. zont_list_devices).

    device_id: ID устройства.
    command_id: ID команды.
    """
    return await _call("send_custom_command", {"device_id": device_id, "command_id": command_id})


@mcp.tool()
async def zont_send_z3k_command(
    device_id: int,
    object_id: int,
    command_name: str,
    command_args: dict[str, Any],
    firmware_version: Optional[int] = None,
    is_guaranteed: Optional[bool] = True,
) -> dict[str, Any]:
    """Отправить недокументированную z3k-команду устройству (H-2000+/H1V/Climatic и т.п.).

    ВНИМАНИЕ: метод send_z3k_command отсутствует в официальной документации ZONT API.
    Формат восстановлен вручную перехватом сетевых запросов веб-интерфейса ZONT
    (my.zont.online) — используй осторожно и проверяй результат через zont_list_devices.

    Известный пример: изменение целевой температуры контура отопления —
    command_name="TargetTemperature", object_id=<id контура из z3k_config.heating_circuits
    или z3k_config.boiler_adapters>, command_args={"value": <новая температура>}.

    device_id: ID устройства.
    object_id: ID объекта z3k (например, id отопительного контура).
    command_name: имя команды (например "TargetTemperature").
    command_args: аргументы команды, например {"value": 19}.
    firmware_version: версия прошивки устройства (из devices[].firmware_version[0]);
        если не передать, будет опущена в запросе.
    is_guaranteed: требовать ли гарантированную доставку команды (по умолчанию true).
    """
    body: dict[str, Any] = {
        "device_id": device_id,
        "object_id": object_id,
        "command_name": command_name,
        "command_args": command_args,
        "request_time": int(time.time() * 1000),
        "is_guaranteed": is_guaranteed,
    }
    if firmware_version is not None:
        body["firmware_version"] = firmware_version
    return await _call("send_z3k_command", body)


@mcp.tool()
async def zont_set_heating_target_temp(device_id: int, circuit: str, value: float) -> dict[str, Any]:
    """Изменить целевую температуру отопительного контура (z3k-устройства: H1V, H-2000+ и т.п.).

    Это высокоуровневая обёртка над недокументированным send_z3k_command — сама находит
    нужный контур по названию, поэтому не требует заранее знать его внутренний object_id.
    Предпочитай этот инструмент вместо zont_send_z3k_command, если просто нужно поднять
    или опустить температуру отопления/ГВС/бойлера.

    device_id: ID устройства (из zont_list_devices).
    circuit: название контура или его подстрока, без учёта регистра — например "отопление",
        "вода"/"гвс", "котел". Также можно передать числовой ID контура
        (z3k_config.heating_circuits[].id) как строку.
    value: новая целевая температура, °C.

    Возвращает объект с полями circuit_id, circuit_name, previous_target_temp,
    new_target_temp — свежепрочитанными после отправки команды, чтобы сразу видеть
    результат без отдельного вызова zont_list_devices.
    """
    before = await _call("devices", {"load_io": True})
    device = next((d for d in before.get("devices", []) if d.get("id") == device_id), None)
    if device is None:
        raise ToolError(f"Устройство {device_id} не найдено")

    circuits = device.get("z3k_config", {}).get("heating_circuits", [])
    if not circuits:
        raise ToolError(
            f"У устройства {device_id} нет z3k_config.heating_circuits — это не z3k-устройство "
            "с отопительными контурами, используй zont_update_device вместо этого инструмента."
        )

    match = None
    if circuit.strip().isdigit():
        wanted_id = int(circuit.strip())
        match = next((c for c in circuits if c.get("id") == wanted_id), None)
    if match is None:
        needle = circuit.strip().lower()
        candidates = [c for c in circuits if needle in (c.get("name") or "").lower()]
        if len(candidates) == 1:
            match = candidates[0]
        elif len(candidates) > 1:
            names = ", ".join(f'"{c.get("name")}" (id={c.get("id")})' for c in candidates)
            raise ToolError(f'Неоднозначное название контура "{circuit}", подходят: {names}')

    if match is None:
        available = ", ".join(f'"{c.get("name")}" (id={c.get("id")})' for c in circuits)
        raise ToolError(f'Контур "{circuit}" не найден. Доступные контуры: {available}')

    circuit_id = match["id"]
    circuit_name = match.get("name")
    z3k_state_before = device.get("io", {}).get("z3k-state", {}).get(str(circuit_id), {})
    previous_target_temp = z3k_state_before.get("target_temp")
    firmware_version = (device.get("firmware_version") or [None])[0]

    await zont_send_z3k_command(
        device_id=device_id,
        object_id=circuit_id,
        command_name="TargetTemperature",
        command_args={"value": value},
        firmware_version=firmware_version,
    )

    # Устройство подтверждает новое значение не мгновенно — опрашиваем несколько раз,
    # пока target_temp не сойдётся с запрошенным (или не кончится число попыток).
    z3k_state_after: dict[str, Any] = {}
    for attempt in range(5):
        await asyncio.sleep(0 if attempt == 0 else 1)
        after = await _call("devices", {"load_io": True})
        device_after = next((d for d in after.get("devices", []) if d.get("id") == device_id), {})
        z3k_state_after = device_after.get("io", {}).get("z3k-state", {}).get(str(circuit_id), {})
        if z3k_state_after.get("target_temp") == value:
            break

    return {
        "ok": True,
        "circuit_id": circuit_id,
        "circuit_name": circuit_name,
        "previous_target_temp": previous_target_temp,
        "new_target_temp": z3k_state_after.get("target_temp"),
        "confirmed": z3k_state_after.get("target_temp") == value,
    }


# --- Данные и события -----------------------------------------------------


@mcp.tool()
async def zont_load_data(
    requests: list[dict[str, Any]], decode: Optional[bool] = True
) -> dict[str, Any]:
    """Загрузить историю данных устройств.

    Показания температурных датчиков, работа термостата, GPS-треки, события,
    состояние контроллера и т.д. Можно запросить несколько устройств и типов
    данных за один вызов. Временные метки — unix time (секунды с 1970-01-01 UTC).

    ZONT кодирует исторические ряды в формате Delta-time Array — каждая метка
    времени, кроме первой, хранится как разница в секундах от предыдущей, что
    неудобно читать напрямую. По умолчанию (decode=true) такие ряды
    раскодируются в список {"time": <unix>, "value": ...} с абсолютными
    метками времени. Передай decode=false, чтобы получить сырой формат ZONT.

    requests: список запросов вида {"device_id": int, "data_types": [str, ...],
        "mintime"?: int, "maxtime"?: int}. data_types, например: temperature,
        thermostat_work, gps, events, custom_controls, z3k_temperature,
        z3k_boiler_adapter, ztc_state.
    decode: раскодировать Delta-time Array в абсолютные метки времени (по умолчанию true).
    """
    data = await _call("load_data", {"requests": requests})
    return decode_timeseries(data) if decode else data


@mcp.tool()
async def zont_raw_events(
    device_id: int,
    mintime: int,
    maxtime: int,
    only: Optional[list[str]] = None,
    except_: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Получить историю событий устройства за заданный промежуток времени.

    Постановка/снятие с охраны, тревоги, GPS/GSM, автозапуск и т.д.

    device_id: ID устройства.
    mintime: начало диапазона (unix time, включительно).
    maxtime: конец диапазона (unix time, включительно).
    only: возвращать только события этих типов.
    except_: не возвращать события этих типов (соответствует полю "except" в API).
    """
    return await _call(
        "raw_events",
        {
            "device_id": device_id,
            "mintime": mintime,
            "maxtime": maxtime,
            "only": only,
            "except": except_,
        },
    )


# --- Архивы -----------------------------------------------------------


@mcp.tool()
async def zont_generate_archive(
    device_id: int, mintime: int, maxtime: int, split_by: Literal["days", "months"]
) -> dict[str, Any]:
    """Запросить создание архива со всеми данными устройства за период времени.

    Возвращает archive_id, который затем нужно передать в zont_download_archive.

    device_id: ID устройства.
    mintime: начало диапазона (unix time, включительно).
    maxtime: конец диапазона (unix time, включительно).
    split_by: разбиение файлов внутри архива — по дням ("days") или по месяцам ("months").
    """
    return await _call(
        "generate_archive",
        {"device_id": device_id, "mintime": mintime, "maxtime": maxtime, "split_by": split_by},
    )


@mcp.tool()
async def zont_download_archive(archive_id: str, output_path: str) -> dict[str, Any]:
    """Скачать zip-архив, ранее созданный zont_generate_archive, и сохранить на диск.

    archive_id: идентификатор архива, полученный от zont_generate_archive.
    output_path: путь к файлу, куда сохранить скачанный zip-архив.
    """
    try:
        res = await _get_client().get_raw("download_generated_archive", {"archive_id": archive_id})
    except ZontApiError as exc:
        raise ToolError(str(exc)) from exc
    resolved = Path(output_path).resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_bytes(res.content)
    return {"ok": True, "saved_to": str(resolved), "bytes": len(res.content)}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
