# Telegram Bot

Minimal Telegram bot layer for `Счетчики Юг`.

What it does:

- responds to `/start`
- shows button menu
- opens Mini App catalog
- links to channel
- links to manager
- gives simple actions for promotions, bestsellers, and wholesale

Run flow:

1. Create bot in `@BotFather`
2. Put `TELEGRAM_BOT_TOKEN` into project `.env`
3. Start backend API if you want live storefront counts:

```bash
python3 sync_backend/customer_api.py
```

4. Install bot dependency:

```bash
python3 -m pip install -r requirements-bot.txt
```

5. Start bot:

```bash
python3 -m telegram_bot.app
```
