# Customer API Contract

## 1. Цель

Это ТЗ описывает backend API для клиентского слоя Telegram-витрины:

- регистрация клиента из Telegram
- синхронизация с `Битрикс24`
- получение статуса карты
- получение режима цен
- поиск клиента по номеру карты или QR

Этот API должен быть промежуточным слоем между Telegram и `Битрикс24`.

## 2. Главный принцип

- Telegram не должен напрямую писать в `Битрикс24`
- Telegram работает только через backend API
- backend API нормализует данные, ищет или обновляет клиента в `Битрикс24` и возвращает Telegram канонический статус

## 3. Базовые endpoint'ы первой версии

Нужны 4 endpoint'а:

1. `POST /api/telegram/customer/register`
2. `GET /api/telegram/customer/status`
3. `GET /api/telegram/customer/card`
4. `GET /api/telegram/customer/resolve`

## 4. POST /api/telegram/customer/register

### Назначение

Создать нового клиента из Telegram или обновить существующего.

### Request body

```json
{
  "first_name": "Иван",
  "last_name": "Иванов",
  "phone": "+7 900 123-45-67",
  "city": "Ростов-на-Дону",
  "customer_type": "installer",
  "company_name": "ООО Монтаж Юг",
  "inn": "6165000000",
  "comment": "Регистрация из Telegram",
  "telegram_user_id": "123456789",
  "telegram_username": "ivanov",
  "telegram_chat_id": "123456789",
  "source": "telegram"
}
```

### Обязательные поля

- `first_name`
- `phone`
- `city`
- `customer_type`
- `telegram_user_id`
- `source`

### Логика

1. нормализовать телефон
2. найти контакт по нормализованному телефону
3. если не найден, искать по `telegram_user_id`
4. если найден один контакт:
   - обновить контакт
5. если не найден:
   - создать контакт
6. установить или обновить поля:
   - `approval_status = approved`
   - `allowed_price_type = wholesale`
   - `card_status = active`
7. если компания указана:
   - привязать к существующей компании
   - либо сохранить в ручном сопоставлении без потери заявки
8. вернуть клиенту статус карты и доступ к оптовым ценам

### Response

```json
{
  "ok": true,
  "action": "created",
  "contact_id": 1542,
  "company_id": 218,
  "customer_state": "approved_wholesale",
  "approval_status": "approved",
  "card_status": "active",
  "allowed_price_type": "wholesale",
  "message": "Карта создана и активирована, оптовые цены открыты"
}
```

### Возможные значения `action`

- `created`
- `updated`
- `conflict`

## 5. GET /api/telegram/customer/status

### Назначение

Вернуть текущее состояние клиента для Telegram-интерфейса.

### Query params

Минимум один из параметров:

- `phone`
- `telegram_user_id`
- `contact_id`

Пример:

`GET /api/telegram/customer/status?telegram_user_id=123456789`

### Логика

1. найти контакт
2. прочитать его поля в `Битрикс24`
3. вычислить итоговый режим Telegram

### Response

```json
{
  "ok": true,
  "contact_id": 1542,
  "company_id": 218,
  "customer_state": "approved_wholesale",
  "approval_status": "approved",
  "card_status": "active",
  "allowed_price_type": "wholesale",
  "discount_percent": 10,
  "can_view_wholesale_prices": true,
  "can_use_loyalty_card": true,
  "last_sync_at": "2026-03-09T12:30:00+03:00"
}
```

### Правило расчета `customer_state`

- `guest` если клиент не найден
- `pending_review` если контакт есть, но карта еще не активирована или синхронизация не завершена
- `approved_wholesale` если:
  - `approval_status = approved`
  - `card_status = active`
  - `allowed_price_type = wholesale`
- `rejected` если `approval_status = rejected`
- `archived` если `card_status = archived` или `blocked`

## 6. GET /api/telegram/customer/card

### Назначение

Вернуть данные для визуализации карты клиента в Telegram.

### Query params

Минимум один из параметров:

- `phone`
- `telegram_user_id`
- `contact_id`

### Response

```json
{
  "ok": true,
  "contact_id": 1542,
  "full_name": "Иван Иванов",
  "phone": "+7 900 123-45-67",
  "company_name": "ООО Монтаж Юг",
  "customer_type": "installer",
  "client_card_id": "SY-104582",
  "client_qr_payload": "LOYALTY:SY-104582",
  "approval_status": "approved",
  "card_status": "active",
  "allowed_price_type": "wholesale",
  "discount_percent": 10,
  "card_label": "КАРТА ПОСТОЯННОГО ПОКУПАТЕЛЯ",
  "manual_entry_code": "SY-104582"
}
```

### Правило

Если карта не активна, endpoint все равно может вернуть карточку, но Telegram должен показывать ее в состоянии:

- `на проверке`
- `не активна`
- `ожидает синхронизации`

## 7. GET /api/telegram/customer/resolve

### Назначение

Найти клиента по QR или номеру карты для ручного или сканерного сценария.

### Query params

Один из параметров:

- `card_id`
- `qr_payload`

Примеры:

- `GET /api/telegram/customer/resolve?card_id=SY-104582`
- `GET /api/telegram/customer/resolve?qr_payload=LOYALTY:SY-104582`

### Response

```json
{
  "ok": true,
  "contact_id": 1542,
  "full_name": "Иван Иванов",
  "company_id": 218,
  "company_name": "ООО Монтаж Юг",
  "approval_status": "approved",
  "card_status": "active",
  "allowed_price_type": "wholesale",
  "discount_percent": 10,
  "customer_type": "installer"
}
```

### Правило

Этот endpoint нужен и для магазина, и для внутренних проверок, и для Telegram-слоя.

## 8. Общая логика поиска клиента

Порядок поиска:

1. по нормализованному телефону
2. по `telegram_user_id`
3. по `client_card_id`
4. по `client_qr_payload`

Если найдено больше одной записи:

- возвращать `ok=false`
- код ошибки `DUPLICATE_CONTACT`
- не открывать автоматически оптовый режим

## 9. Правила синхронизации с Bitrix24

### При регистрации

backend API должен:

- создать или обновить `Контакт`
- записать Telegram-поля
- установить стартовые статусы
- вернуть Telegram промежуточное состояние

### При чтении статуса

backend API должен:

- читать актуальный статус из `Битрикс24`
- не полагаться на локальный кэш как на единственный источник истины

### При чтении карты

backend API должен:

- возвращать текущую карту по полям контакта
- вернуть и QR payload, и номер карты для ручного ввода

## 10. Ошибки API

Коды ошибок:

- `VALIDATION_ERROR`
- `CONTACT_NOT_FOUND`
- `DUPLICATE_CONTACT`
- `BITRIX24_UNAVAILABLE`
- `INVALID_PHONE`
- `INVALID_CARD_ID`
- `INVALID_QR_PAYLOAD`
- `MISSING_REQUIRED_FIELDS`

## 11. Правила допуска к оптовому режиму

Telegram должен открыть оптовый режим только если API возвращает:

- `approval_status = approved`
- `card_status = active`
- `allowed_price_type = wholesale`
- `can_view_wholesale_prices = true`

Во всех остальных случаях Telegram должен показывать только розничный режим.

## 12. Практический ответ для Telegram UI

Telegram-интерфейсу достаточно следующих признаков:

- `customer_state`
- `can_view_wholesale_prices`
- `can_use_loyalty_card`
- `client_card_id`
- `client_qr_payload`
- `discount_percent`

## 13. Минимальная безопасность

- не возвращать в QR и API лишние персональные данные без необходимости
- не открывать оптовые цены по одному только номеру телефона без статуса
- логировать все конфликты дубликатов
- ограничивать запись в API только серверной частью Telegram-интеграции

## 14. Что нужно реализовать дальше

Следующим этапом backend должен получить:

- клиент `Битрикс24` для `Контактов` и `Компаний`
- нормализатор телефона
- резолвер компании
- сервис генерации `client_card_id`
- сервис генерации `client_qr_payload`
- статусный сервис, который считает `customer_state`
