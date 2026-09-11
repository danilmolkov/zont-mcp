# zont-mcp

MCP-сервер для [API ZONT](https://zont-online.ru/api/docs/) — позволяет любому MCP-клиенту
(Claude, и т.п.) читать состояние устройств ZONT / Mega SX и управлять ими: охрана, сирена,
блокировка двигателя, автозапуск, термостат, история событий и данных, архивы.

## Настройка

Сервер получает учётные данные ZONT из переменных окружения:

| Переменная | Обязательна | Описание |
|---|---|---|
| `ZONT_CLIENT` | да | Ваш e-mail или контакт — отправляется в заголовке `X-ZONT-Client` |
| `ZONT_TOKEN` | нет* | Аутентификационный токен ZONT (предпочтительный способ) |
| `ZONT_LOGIN` | нет* | Логин ZONT (если токена нет) |
| `ZONT_PASSWORD` | нет* | Пароль ZONT (если токена нет) |

\* нужно задать либо `ZONT_TOKEN`, либо пару `ZONT_LOGIN`/`ZONT_PASSWORD`.

Токен можно получить один раз через инструмент `zont_get_authtoken` (запустив сервер с
логином/паролем), а затем использовать его вместо пароля.

### Пример конфигурации для Claude Code / Claude Desktop

```json
{
  "mcpServers": {
    "zont": {
      "command": "uvx",
      "args": ["zont-mcp"],
      "env": {
        "ZONT_CLIENT": "you@example.com",
        "ZONT_TOKEN": "xxxxxxxxxxxxxxxxxx"
      }
    }
  }
}
```

Пакет пока не опубликован в PyPI — до публикации запускайте из исходников:
`uvx --from /absolute/path/to/zont-mcp zont-mcp`, либо напрямую из git:
`uvx --from git+https://github.com/danilmolkov/zont-mcp zont-mcp`.

## Инструменты

| Инструмент | Метод ZONT API | Описание |
|---|---|---|
| `zont_get_authtoken` | `get_authtoken` | Получить токен по логину/паролю |
| `zont_list_devices` | `devices` | Список устройств и их настроек/состояний |
| `zont_add_device` | `add_device` | Добавить устройство |
| `zont_delete_device` | `delete_device` | Удалить устройство / передать другому пользователю |
| `zont_update_device` | `update_device` | Изменить настройки устройства |
| `zont_set_io_port` | `set_io_port` | Управление охраной/сиреной/блокировкой/автозапуском |
| `zont_send_custom_command` | `send_custom_command` | Отправить пользовательскую команду |
| `zont_load_data` | `load_data` | История датчиков, термостата, GPS, событий и т.д. |
| `zont_raw_events` | `raw_events` | История событий устройства |
| `zont_generate_archive` | `generate_archive` | Запросить создание архива данных |
| `zont_download_archive` | `download_generated_archive` | Скачать готовый архив на диск |

## Разработка

```bash
uv sync            # установить зависимости
uv run zont-mcp     # запустить сервер напрямую
```
