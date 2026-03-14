# Sync Backend

Технический skeleton для синхронизации:

- `Bitrix24` -> выборки популярных товаров и акций
- сайт -> lookup товара по `xml_id`
- builder -> сборка `storefront.json`
- publisher -> безопасная публикация JSON
- customer API -> регистрация клиента, статус карты, поиск по QR/номеру карты

## Структура

- [sync_backend/main.py](/Users/igor_itmail.ru/Documents/сайт насосы-юг/ТГ счетчики юг/sync_backend/main.py)
- [sync_backend/config.py](/Users/igor_itmail.ru/Documents/сайт насосы-юг/ТГ счетчики юг/sync_backend/config.py)
- [sync_backend/models.py](/Users/igor_itmail.ru/Documents/сайт насосы-юг/ТГ счетчики юг/sync_backend/models.py)
- [sync_backend/logging_utils.py](/Users/igor_itmail.ru/Documents/сайт насосы-юг/ТГ счетчики юг/sync_backend/logging_utils.py)
- [sync_backend/clients/bitrix24.py](/Users/igor_itmail.ru/Documents/сайт насосы-юг/ТГ счетчики юг/sync_backend/clients/bitrix24.py)
- [sync_backend/clients/site_catalog.py](/Users/igor_itmail.ru/Documents/сайт насосы-юг/ТГ счетчики юг/sync_backend/clients/site_catalog.py)
- [sync_backend/services/builder.py](/Users/igor_itmail.ru/Documents/сайт насосы-юг/ТГ счетчики юг/sync_backend/services/builder.py)
- [sync_backend/services/publisher.py](/Users/igor_itmail.ru/Documents/сайт насосы-юг/ТГ счетчики юг/sync_backend/services/publisher.py)
- [sync_backend/services/customer_service.py](/Users/igor_itmail.ru/Documents/сайт насосы-юг/ТГ счетчики юг/sync_backend/services/customer_service.py)
- [sync_backend/customer_api.py](/Users/igor_itmail.ru/Documents/сайт насосы-юг/ТГ счетчики юг/sync_backend/customer_api.py)

## Что уже умеет

- читать конфиг из `knowledge-base/*.json`
- получать все страницы `crm.item.list`
- фильтровать записи по стадии, категории, датам и `xmlId`
- дедуплицировать записи по `xml_id`
- обогащать данные товарами сайта
- собирать итоговый JSON
- публиковать его атомарной заменой файла
- работать как промежуточный API для клиентского Telegram-слоя

## Как запускать

```bash
python3 sync_backend/main.py
```

Для клиентского API:

```bash
python3 sync_backend/customer_api.py
```

## Переменные окружения

- `BITRIX24_WEBHOOK`
  Обязателен. Укажите входящий webhook Bitrix24 через переменную окружения.
- `SITE_CATALOG_LOOKUP_URL`
  Если задан, используется как lookup endpoint сайта вместо дефолтного.
- `STORE_OUTPUT_PATH`
  Если задан, используется как путь публикации итогового JSON.
- `CUSTOMER_API_HOST`
  Хост для клиентского API. По умолчанию `127.0.0.1`.
- `CUSTOMER_API_PORT`
  Порт для клиентского API. По умолчанию `8787`.

## Текущий режим

По умолчанию publisher кладет итоговый файл в:

`/Users/igor_itmail.ru/Documents/ТГ счетчики юг/output/storefront.json`

Это локальный publish-target для отладки. Дальше его можно заменить на production endpoint на стороне сайта.

## Customer API endpoints

- `POST /api/telegram/customer/register`
- `GET /api/telegram/customer/status`
- `GET /api/telegram/customer/card`
- `GET /api/telegram/customer/resolve`

Это skeleton без внешних зависимостей на stdlib WSGI. Он рассчитан как промежуточный слой между Telegram и `Битрикс24`.
