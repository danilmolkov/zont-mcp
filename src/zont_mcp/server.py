"""MCP-сервер для API ZONT."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Optional

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from .client import ZontApiError, client_from_env

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
async def zont_list_devices(load_io: Optional[bool] = None) -> dict[str, Any]:
    """Получить список всех устройств пользователя ZONT и их настроек.

    load_io: возвращать ли в поле io текущие состояния каждого устройства.
    """
    return await _call("devices", {"load_io": load_io})


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


# --- Данные и события -----------------------------------------------------


@mcp.tool()
async def zont_load_data(requests: list[dict[str, Any]]) -> dict[str, Any]:
    """Загрузить историю данных устройств.

    Показания температурных датчиков, работа термостата, GPS-треки, события,
    состояние контроллера и т.д. Можно запросить несколько устройств и типов
    данных за один вызов. Временные метки — unix time (секунды с 1970-01-01 UTC).

    requests: список запросов вида {"device_id": int, "data_types": [str, ...],
        "mintime"?: int, "maxtime"?: int}. data_types, например: temperature,
        thermostat_work, gps, events, custom_controls, z3k_temperature,
        z3k_boiler_adapter, ztc_state.
    """
    return await _call("load_data", {"requests": requests})


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
