# Telegram Bot Launch Checklist

## 1. Create bot in Telegram

1. Open `@BotFather`
2. Send `/newbot`
3. Set name:
   - `Счетчики Юг Bot`
4. Set username:
   - for example `schetchiki_yug_bot`
5. Copy the token

## 2. Configure bot profile

1. Send `/setuserpic`
2. Choose your bot
3. Upload:
   - `/Users/igor_itmail.ru/Documents/ТГ счетчики юг/bot-avatar-schetchiki-yug.png`

Optional:

1. `/setdescription`
2. Use:

```text
Каталог инженерного оборудования Счетчики Юг.
Открыть каталог, посмотреть акции, связаться с менеджером.
```

3. `/setabouttext`
4. Use:

```text
Каталог, акции, оптовый заказ.
```

## 3. Fill `.env`

Add these variables to project `.env`:

```text
TELEGRAM_BOT_TOKEN=replace_with_botfather_token
TELEGRAM_BOT_NAME=Счетчики Юг Bot
TELEGRAM_CHANNEL_URL=https://t.me/schetchiki_yug
TELEGRAM_MANAGER_USERNAME=schetchiki_yug
TELEGRAM_MINIAPP_URL=https://igorit1980-hub.github.io/tg-schetchiki-yug/
TELEGRAM_BACKEND_BASE_URL=http://127.0.0.1:8787
```

## 4. Start local services

1. Start backend API:

```bash
python3 sync_backend/customer_api.py
```

2. Install bot dependencies:

```bash
python3 -m pip install -r requirements-bot.txt
```

3. Start bot:

```bash
python3 -m telegram_bot.app
```

## 5. Verify

1. Open your bot in Telegram
2. Send `/start`
3. Check buttons:
   - `Открыть каталог`
   - `Акции`
   - `Хиты продаж`
   - `Оптовый заказ`
   - `Канал`
   - `Менеджер`
4. Open Mini App from bot
5. Check that the channel link opens correctly
