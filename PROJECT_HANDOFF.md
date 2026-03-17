# Project Handoff

## Project

Telegram Mini App / Telegram storefront for `Счетчики Юг`, connected to local preview, `sync_backend`, site catalog data, and Bitrix24.

Workspace:
- `/Users/igor_itmail.ru/Documents/ТГ счетчики юг`

## Main files

- `/Users/igor_itmail.ru/Documents/ТГ счетчики юг/index.html`
- `/Users/igor_itmail.ru/Documents/ТГ счетчики юг/preview-mobile.html`
- `/Users/igor_itmail.ru/Documents/ТГ счетчики юг/sync_backend/main.py`
- `/Users/igor_itmail.ru/Documents/ТГ счетчики юг/sync_backend/customer_api.py`
- `/Users/igor_itmail.ru/Documents/ТГ счетчики юг/sync_backend/config.py`
- `/Users/igor_itmail.ru/Documents/ТГ счетчики юг/sync_backend/clients/bitrix24.py`
- `/Users/igor_itmail.ru/Documents/ТГ счетчики юг/sync_backend/clients/site_catalog.py`
- `/Users/igor_itmail.ru/Documents/ТГ счетчики юг/sync_backend/services/request_service.py`
- `/Users/igor_itmail.ru/Documents/ТГ счетчики юг/sync_backend/services/preview_service.py`
- `/Users/igor_itmail.ru/Documents/ТГ счетчики юг/output/storefront.json`
- `/Users/igor_itmail.ru/Documents/ТГ счетчики юг/output/storefront.test.json`
- `/Users/igor_itmail.ru/Documents/ТГ счетчики юг/output/storefront.diagnostics.json`
- `/Users/igor_itmail.ru/Documents/ТГ счетчики юг/knowledge-base/bitrix24-first-items-checklist.md`

## Current status

Frontend:
- Telegram Mini App prototype restored in `index.html`
- local mobile preview available in `preview-mobile.html`
- Telegram WebApp integration added
- main screen visually polished
- frontend reads backend `health`, `storefront`, customer status/card, and request endpoints
- Mini App can work in fallback storefront mode

Backend:
- `sync_backend` restored
- storefront sync from Bitrix24 implemented
- site lookup and local fallback via `catalog_priced.json` work
- customer API restored
- request API restored
- local preview mode implemented when Bitrix24 is unavailable
- automatic storefront fallback implemented when smart-process sources are empty
- diagnostics JSON implemented for Bitrix24 smart-process fetches

## Backend endpoints

- `GET /api/health`
- `GET /api/telegram/storefront`
- `POST /api/telegram/customer/register`
- `GET /api/telegram/customer/status`
- `GET /api/telegram/customer/card`
- `GET /api/telegram/customer/resolve`
- `POST /api/telegram/request`

## Data flow

- site is the master source for catalog structure and product matching
- Bitrix24 is the source for smart-process storefront entries, CRM requests, and customer states
- backend is the integration layer between Telegram and Bitrix24
- frontend consumes backend APIs and displays Mini App flows

## Bitrix24 context

Webhook:
- configured and tested
- stored locally in project `.env`

Smart-process entities:
- `popular_products_tg`
  - `entityTypeId=1042`
  - `categoryId=23`
  - active stage: `DT1042_23:PREPARATION`
- `telegram_promotions`
  - `entityTypeId=1044`
  - `categoryId=27`
  - active stage: `DT1044_27:CLIENT`

Important finding:
- Bitrix24 currently returns `0` items for both entity types
- this is not a stage/date/xmlId filtering problem in code
- current empty storefront is caused by empty smart-process sources or missing read access for this webhook

## Current storefront behavior

Live sync:
- `sync_backend/main.py` fetches Bitrix24 items
- builds storefront from smart-process data plus site lookup
- writes diagnostics to `output/storefront.diagnostics.json`

Fallback behavior:
- if both smart-process collections are empty, backend publishes fallback storefront from:
  - `/Users/igor_itmail.ru/Documents/ТГ счетчики юг/output/storefront.test.json`
- published JSON includes:

```json
"fallback_mode": {
  "active": true,
  "source": "/Users/igor_itmail.ru/Documents/ТГ счетчики юг/output/storefront.test.json",
  "reason": "smart_process_empty"
}
```

Current actual result:
- `output/storefront.json` is populated from fallback
- current counts:
  - `popular_products`: 2
  - `promotions`: 1

## Diagnostics

Diagnostics file:
- `/Users/igor_itmail.ru/Documents/ТГ счетчики юг/output/storefront.diagnostics.json`

What it contains:
- counts by smart-process category
- counts by active stage
- stage distribution
- missing `xmlId` count
- missing date-range count
- sample fetched items
- fallback usage metadata

Current diagnostic result:
- `popular_products`
  - `active_stage_count=0`
  - `category_total_count=0`
- `promotions`
  - `active_stage_count=0`
  - `category_total_count=0`

## Local preview mode

If `BITRIX24_WEBHOOK` is not configured:
- `customer_api.py` runs in `local_preview`
- local registrations and requests are stored in:
  - `/Users/igor_itmail.ru/Documents/ТГ счетчики юг/output/preview_state.json`

This mode supports:
- customer registration
- customer status lookup
- customer card response
- request submission
- storefront delivery from local published JSON

## Frontend work already done

Main UI:
- Telegram-style shell and navigation restored
- home screen polished with stronger hero section
- pinned cards improved
- quick catalog section improved
- daily feed cards improved
- sync screen shows backend mode, storefront counts, diagnostics path, fallback status

Backend-aware UI:
- frontend requests `GET /api/health`
- frontend requests `GET /api/telegram/storefront`
- frontend requests customer state and card
- frontend can submit manager requests
- frontend can submit customer registration

Known UX limitation:
- registration and manager request still use `prompt()` dialogs
- these should eventually become proper in-app forms

## First Bitrix24 test items checklist

Detailed checklist file:
- `/Users/igor_itmail.ru/Documents/ТГ счетчики юг/knowledge-base/bitrix24-first-items-checklist.md`

Required fields for first `popular_products_tg` item:
- `title`
- `xmlId`
- `begindate`
- `closedate`
- `sourceDescription`
- `assignedById`
- correct category `23`
- correct stage `DT1042_23:PREPARATION`

Required fields for first `telegram_promotions` item:
- `title`
- `xmlId`
- `begindate`
- `closedate`
- `sourceDescription`
- `assignedById`
- correct category `27`
- correct stage `DT1044_27:CLIENT`
- matching site item must have valid promo pricing:
  - `old_price > promo_price`

## Important files produced during work

- `/Users/igor_itmail.ru/Documents/ТГ счетчики юг/output/storefront.json`
- `/Users/igor_itmail.ru/Documents/ТГ счетчики юг/output/storefront.test.json`
- `/Users/igor_itmail.ru/Documents/ТГ счетчики юг/output/storefront.diagnostics.json`
- `/Users/igor_itmail.ru/Documents/ТГ счетчики юг/output/preview_state.json`

## What has been verified

Verified:
- Bitrix24 webhook works
- sync runs against real Bitrix24
- current Bitrix24 result is empty for entity types `1042` and `1044`
- fallback storefront publication works
- diagnostics file writes correctly
- frontend can consume backend storefront
- preview service logic works

Not yet verified end-to-end:
- switch from fallback storefront to live smart-process data after real records are added
- proper in-app forms for registration and request flows
- final production behavior inside actual Telegram Mini App context with full backend availability

## Best next tasks

Recommended next steps:
- create the first real smart-process records in Bitrix24 and rerun sync
- verify storefront switches from fallback to live Bitrix24 data
- replace `prompt()` with native Mini App forms
- polish catalog screen visuals
- polish customer card screen visuals
- add an explicit visual live/fallback badge on the home screen
- surface live promotions/popular items more directly on the home screen
- verify webhook permissions if Bitrix24 UI already contains records but API still returns zero

## Prompt block for GPT

Use this block when handing off to another GPT:

```text
Project: Telegram Mini App for "Счетчики Юг"
Workspace: /Users/igor_itmail.ru/Documents/ТГ счетчики юг

Current status:
- Mini App frontend restored in index.html
- mobile preview exists in preview-mobile.html
- sync_backend restored
- customer API and request API work
- local preview mode exists without Bitrix24
- fallback storefront exists from output/storefront.test.json
- diagnostics exist in output/storefront.diagnostics.json
- home screen visuals already polished

Bitrix24:
- webhook is working
- smart-processes:
  - popular_products_tg: entityTypeId=1042, categoryId=23, active stage DT1042_23:PREPARATION
  - telegram_promotions: entityTypeId=1044, categoryId=27, active stage DT1044_27:CLIENT
- API currently returns 0 items for both entity types
- storefront is currently published through fallback_mode from storefront.test.json

Important files:
- /Users/igor_itmail.ru/Documents/ТГ счетчики юг/index.html
- /Users/igor_itmail.ru/Documents/ТГ счетчики юг/preview-mobile.html
- /Users/igor_itmail.ru/Documents/ТГ счетчики юг/sync_backend/main.py
- /Users/igor_itmail.ru/Documents/ТГ счетчики юг/sync_backend/customer_api.py
- /Users/igor_itmail.ru/Documents/ТГ счетчики юг/sync_backend/config.py
- /Users/igor_itmail.ru/Documents/ТГ счетчики юг/sync_backend/clients/bitrix24.py
- /Users/igor_itmail.ru/Documents/ТГ счетчики юг/sync_backend/clients/site_catalog.py
- /Users/igor_itmail.ru/Documents/ТГ счетчики юг/sync_backend/services/request_service.py
- /Users/igor_itmail.ru/Documents/ТГ счетчики юг/sync_backend/services/preview_service.py
- /Users/igor_itmail.ru/Documents/ТГ счетчики юг/output/storefront.json
- /Users/igor_itmail.ru/Documents/ТГ счетчики юг/output/storefront.test.json
- /Users/igor_itmail.ru/Documents/ТГ счетчики юг/output/storefront.diagnostics.json
- /Users/igor_itmail.ru/Documents/ТГ счетчики юг/knowledge-base/bitrix24-first-items-checklist.md

Need: prepare the next technical task based on this state.
```
