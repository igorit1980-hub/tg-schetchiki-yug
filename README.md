# TG Schetchiki Yug

Telegram storefront prototype for "Счетчики Юг" with:

- static storefront UI in `index.html`
- product and promo source files in `catalog_*.json`
- shared integration docs in `knowledge-base/`
- Python sync backend in `sync_backend/`

## Repository layout

- `index.html` - storefront prototype
- `knowledge-base/` - data contracts and integration notes
- `sync_backend/` - Bitrix24/site sync skeleton
- `output/` - generated local artifacts

## Local setup

1. Copy `.env.example` values into your shell environment.
2. Set `BITRIX24_WEBHOOK` to your own Bitrix24 incoming webhook.
3. Run the sync backend:

```bash
python3 sync_backend/main.py
```

4. Run the customer API:

```bash
python3 sync_backend/customer_api.py
```

## Notes for GitHub

- The repository does not store production secrets.
- Generated output file `output/storefront.json` is ignored.
- Replace example URLs with real values only through environment variables.
