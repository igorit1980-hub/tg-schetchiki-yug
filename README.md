# TG Schetchiki Yug

Telegram storefront prototype for "Счетчики Юг" with:

- static storefront UI in `index.html`
- product and promo source files in `catalog_*.json`
- shared integration docs in `knowledge-base/`
- Python sync backend in `sync_backend/`
- Telegram bot layer in `telegram_bot/`

## Repository layout

- `index.html` - storefront prototype
- `knowledge-base/` - data contracts and integration notes
- `sync_backend/` - Bitrix24/site sync skeleton
- `telegram_bot/` - Telegram bot entrypoint and config
- `output/` - generated local artifacts

## Local setup

1. Create `.env` from `.env.example`.
2. Set `BITRIX24_WEBHOOK` to your Bitrix24 incoming webhook if you want live CRM sync.
3. Adjust `SITE_CATALOG_LOOKUP_URL` only if the site lookup endpoint differs from the default.
4. Run the storefront sync when Bitrix24 access is configured:

```bash
python3 sync_backend/main.py
```

5. Run the Telegram backend API:

```bash
python3 sync_backend/customer_api.py
```

6. If you want to launch the Telegram bot:

```bash
python3 -m pip install -r requirements-bot.txt
python3 -m telegram_bot.app
```

If `BITRIX24_WEBHOOK` is missing, `customer_api.py` now starts in `local_preview` mode:

- `GET /api/health` reports `mode=local_preview`
- customer registration/card/request endpoints use `output/preview_state.json`
- `GET /api/telegram/storefront` still serves the last published storefront JSON
- `index.html` can use this mode for local Mini App preview without live Bitrix24 access

If smart-process items are empty, `sync_backend/main.py` can publish fallback storefront data from `output/storefront.test.json` so Mini App preview stays populated while Bitrix24 content is being prepared.

## Mini App wholesale card flow

The production path for wholesale card registration is now:

- `Mini App -> customer_api.py -> site endpoint -> Bitrix24 -> card status in Mini App`

Mini App backend supports these env vars:

```text
SITE_WHOLESALE_SYNC_API_URL=https://xn----ftbemal0cj7bc5f.xn--p1ai/local/api/telegram-miniapp-wholesale-register.php
SITE_WHOLESALE_SYNC_API_TOKEN=CHANGE_ME_STRONG_SECRET
```

The deployment checklist for this flow is stored in:

- [MINIAPP_WHOLESALE_CARD_DEPLOY_CHECKLIST.md](/Users/igor_itmail.ru/Documents/ТГ счетчики юг/knowledge-base/launch/MINIAPP_WHOLESALE_CARD_DEPLOY_CHECKLIST.md)

Current live state:

- card registration already creates a contact in Bitrix24
- the card gets an id like `SY-XXXXXX`
- Mini App can already show `pending_review` via backend fallback state even if `UF_CRM_*` fields are not created yet

## Local Telegram run

If Telegram Mini App on this Mac shows `Load failed`, first make sure the local customer API is running:

```bash
./scripts/run_customer_api.command
```

Quick health check:

```bash
./scripts/check_customer_api.command
```
- full site sync still depends on the production endpoint `/local/api/telegram-miniapp-wholesale-register.php` returning `200 OK` instead of `404`

## Restored API syncs

The backend now covers these directions:

- `Bitrix24 -> storefront.json`
  Popular products and promotions are read from Bitrix24 smart-processes, validated, joined with site catalog data by `xml_id`, and published to `output/storefront.json`.
- `Bitrix24 -> storefront diagnostics`
  Each sync also writes `output/storefront.diagnostics.json` with counts by category and stage, plus sample records for debugging empty smart-process results.
- `empty smart-process -> fallback storefront`
  If both smart-process collections are empty, sync can publish `output/storefront.test.json` as a temporary storefront and mark it with `fallback_mode`.
- `site -> backend`
  Product lookup is resolved through `SITE_CATALOG_LOOKUP_URL` with local catalog fallback.
- `Telegram -> Bitrix24`
  Customer registration/status/card/resolve endpoints are exposed through `customer_api.py`.
- `Telegram -> Bitrix24 requests`
  `POST /api/telegram/request` creates a CRM lead or deal depending on `CRM_REQUEST_MODE`.
- `Telegram <- backend storefront`
  `GET /api/telegram/storefront` returns the last published storefront payload.

## Available API endpoints

- `GET /api/health`
- `GET /api/telegram/storefront`
- `POST /api/telegram/customer/register`
- `GET /api/telegram/customer/status`
- `GET /api/telegram/customer/card`
- `GET /api/telegram/customer/resolve`
- `POST /api/telegram/request`

## Useful local files

- `output/storefront.json` - last published storefront payload
- `output/storefront.diagnostics.json` - Bitrix24 diagnostics for smart-process fetches
- `output/storefront.test.json` - temporary fallback storefront for local preview
- `output/preview_state.json` - local preview registrations and requests
- `knowledge-base/bitrix24-first-items-checklist.md` - checklist for the first test records in Bitrix24
- `knowledge-base/launch/BOT_LAUNCH_CHECKLIST.md` - BotFather and local bot startup checklist

## Notes for the repository

- The repository does not store production secrets.
- Generated output file `output/storefront.json` is ignored.
- Generated diagnostics file `output/storefront.diagnostics.json` is ignored.
- Generated local preview state `output/preview_state.json` is ignored.
- Replace example URLs with real values only through environment variables.
