# MINIAPP_CLIENT_CARD_TZ

Project: `Счетчики Юг`

## Goal

Implement a customer card flow in Telegram Mini App so that the card is created in the app, synchronized with the site and Bitrix24, and immediately opens wholesale prices after activation.

## Business logic

- One card per client.
- Card number format: `SY-000001`.
- The source of truth for the card is `Bitrix24 + Mini App backend`.
- Mini App only displays the card and opens wholesale prices.
- The customer can be found manually in the store by card number.

## Customer statuses

- `Гость`
- `На проверке`
- `Карта активна`

## Registration flow

1. The client fills in the card form in Mini App.
2. Backend creates or updates the contact in Bitrix24.
3. The customer receives a human-readable card number.
4. QR code is generated for the card.
5. The card is shown in Mini App.
6. After synchronization the card becomes active and wholesale prices are shown.

## Data stored in Bitrix24

Recommended minimum set:

- `UF_CRM_CLIENT_CARD_NO`
- `UF_CRM_CLIENT_CARD_STATUS`
- `UF_CRM_CLIENT_CARD_QR`
- `UF_CRM_TG_USER_ID`
- `UF_CRM_TG_USERNAME`
- `UF_CRM_CLIENT_SOURCE`

Optional fields:

- `UF_CRM_CLIENT_DISCOUNT`
- `UF_CRM_CLIENT_CARD_REGISTERED_AT`
- `UF_CRM_APPROVAL_STATUS`
- `UF_CRM_ALLOWED_PRICE_TYPE`

## Mini App requirements

- Registration form should be simple and clear.
- The card screen must show:
  - card number
  - QR code
  - current status
  - access to wholesale prices
- If the site or CRM is temporarily unavailable, the app must show a clear status and keep the form data.
- The app must not rely on local `127.0.0.1` in production.

## Acceptance criteria

- The client can register a card in Mini App.
- Bitrix24 gets the contact and card data.
- The app shows the correct card status.
- The QR code is visible.
- Wholesale prices open when the card is active.
- The store can look up the client by card number.

