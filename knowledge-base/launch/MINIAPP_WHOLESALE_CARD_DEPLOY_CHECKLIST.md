# Mini App Wholesale Card Deploy Checklist

Цель: замкнуть боевой сценарий `Telegram Mini App -> сайт -> Bitrix24 -> статус карты -> оптовые цены`.

## 1. Что уже подготовлено в коде

- Mini App отправляет регистрацию карты через `POST /api/telegram/customer/register`
- backend умеет отправлять регистрацию на сайт через:
  - `SITE_WHOLESALE_SYNC_API_URL`
  - `SITE_WHOLESALE_SYNC_API_TOKEN`
- на сайте подготовлен endpoint:
  - `/local/api/telegram-miniapp-wholesale-register.php`
- endpoint создает результат формы `OPTOVIKI` (`WEB_FORM_ID = 11`)
- existing site hooks уже должны:
  - синхронизировать результат формы в Bitrix24
  - создавать site-user после перевода формы в статус `12`

## 2. Что нужно выложить на сайт

Файл:

- `/local/api/telegram-miniapp-wholesale-register.php`

Из репозитория сайта:

- [telegram-miniapp-wholesale-register.php](/Users/igor_itmail.ru/Documents/Сайт Счетчики-юг/_workspace/live-copy/home/bitrix/www/local/api/telegram-miniapp-wholesale-register.php)

## 3. Что нужно добавить на сайте

Создать файл:

- `/local/telegram-miniapp-config.php`

Содержимое:

```php
<?php
return [
    'sync_token' => 'CHANGE_ME_STRONG_SECRET',
];
```

## 4. Что нужно настроить в Mini App backend

В [`.env`](/Users/igor_itmail.ru/Documents/ТГ счетчики юг/.env) указать:

```text
SITE_WHOLESALE_SYNC_API_URL=https://xn----7sbhjpnneqb.xn--p1ai/local/api/telegram-miniapp-wholesale-register.php
SITE_WHOLESALE_SYNC_API_TOKEN=CHANGE_ME_STRONG_SECRET
```

После этого перезапустить:

```bash
python3 sync_backend/customer_api.py
```

## 5. Какой payload уходит с Mini App на сайт

Передаются:

- `first_name`
- `last_name`
- `phone`
- `email`
- `city`
- `customer_type`
- `telegram_user_id`
- `telegram_username`
- `contact_id`
- `client_card_id`
- `source`
- `comment`

На сайте они складываются в форму `OPTOVIKI`:

- `CLIENT_NAME`
- `PHONE`
- `EMAIL`
- `MESSAGE`
- `INN` остаётся пустым

## 6. Как выглядит бизнес-цепочка после деплоя

1. Клиент в Mini App нажимает `Зарегистрировать карту`
2. Mini App отправляет данные в backend
3. backend:
   - создает/обновляет контакт в Bitrix24
   - создает `client_card_id`
   - отправляет заявку на сайт endpoint
4. сайт создает результат формы `OPTOVIKI`
5. site hook синхронизирует результат формы в Bitrix24
6. менеджер проверяет клиента и переводит заявку в нужный статус
7. после одобрения:
   - у клиента в Mini App меняется статус карты
   - открываются оптовые цены

## 7. Что проверить после выкладки

### Mini App

- форма регистрации открывается
- заявка отправляется без ошибки
- после отправки статус становится `На проверке`

### Сайт

- в веб-форме `OPTOVIKI` появился новый результат
- в тексте результата есть пометка, что источник — Telegram Mini App / Счетчики Юг

### Bitrix24

- контакт создан или обновлен
- есть телефон, email, тип клиента
- есть источник `telegram-channel-schetchiki-yug`
- есть номер карты

### После одобрения

- статус клиента в Mini App меняется с `На проверке` на `Карта активна`
- прайс в приложении переключается на оптовый

## 8. Что сейчас ограничивает локальную проверку

Локальная копия сайта не содержит полный runtime `Bitrix`, поэтому endpoint локально отвечает:

- `BITRIX_RUNTIME_NOT_FOUND`

Это ожидаемо для текущей локальной copy и не означает, что endpoint написан неправильно. Полноценная проверка возможна только после выкладки на боевой сайт.
