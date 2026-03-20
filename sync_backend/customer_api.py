from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from wsgiref.simple_server import make_server

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from sync_backend.clients.bitrix24 import Bitrix24Client
from sync_backend.config import load_config
from sync_backend.logging_utils import configure_logging
from sync_backend.models import CustomerRegistrationPayload, TelegramRequestPayload
from sync_backend.services.customer_service import CustomerService
from sync_backend.services.preview_service import PreviewService
from sync_backend.services.request_service import RequestService


def run() -> int:
    logger = configure_logging()
    config = load_config()
    if config.bitrix_enabled:
        bitrix_client = Bitrix24Client(config)
        service = CustomerService(config, bitrix_client)
        request_service = RequestService(config, bitrix_client)
        backend_mode = "bitrix24"
    else:
        preview_service = PreviewService(config)
        service = preview_service
        request_service = preview_service
        backend_mode = "local_preview"

    def app(environ, start_response):
        method = environ["REQUEST_METHOD"].upper()
        parsed = urlparse(environ.get("PATH_INFO", ""))
        path = parsed.path
        try:
            if method == "POST" and path == "/api/telegram/customer/register":
                body_size = int(environ.get("CONTENT_LENGTH") or 0)
                raw = environ["wsgi.input"].read(body_size) if body_size > 0 else b"{}"
                payload = json.loads(raw.decode("utf-8"))
                response = service.register_customer(_registration_payload_from_json(payload))
                return _respond(start_response, 200 if response.get("ok") else 400, response)

            if method == "POST" and path == "/api/telegram/request":
                body_size = int(environ.get("CONTENT_LENGTH") or 0)
                raw = environ["wsgi.input"].read(body_size) if body_size > 0 else b"{}"
                payload = json.loads(raw.decode("utf-8"))
                response = request_service.submit_request(_request_payload_from_json(payload))
                return _respond(start_response, 200 if response.get("ok") else 400, response)

            if method == "GET" and path == "/api/telegram/customer/status":
                params = parse_qs(environ.get("QUERY_STRING", ""))
                response = service.get_customer_context(
                    phone=_single(params, "phone"),
                    telegram_user_id=_single(params, "telegram_user_id"),
                    contact_id=_int_or_none(_single(params, "contact_id")),
                )
                return _respond(start_response, 200 if response.get("ok") else 404, response)

            if method == "GET" and path == "/api/telegram/customer/card":
                params = parse_qs(environ.get("QUERY_STRING", ""))
                response = service.get_customer_card(
                    phone=_single(params, "phone"),
                    telegram_user_id=_single(params, "telegram_user_id"),
                    contact_id=_int_or_none(_single(params, "contact_id")),
                )
                return _respond(start_response, 200 if response.get("ok") else 404, response)

            if method == "GET" and path == "/api/telegram/customer/resolve":
                params = parse_qs(environ.get("QUERY_STRING", ""))
                response = service.resolve_customer(
                    card_id=_single(params, "card_id"),
                    qr_payload=_single(params, "qr_payload"),
                )
                return _respond(start_response, 200 if response.get("ok") else 404, response)

            if method == "GET" and path == "/api/telegram/storefront":
                if not config.output_path.exists():
                    return _respond(
                        start_response,
                        404,
                        {"ok": False, "error_code": "STOREFRONT_NOT_FOUND", "path": str(config.output_path)},
                    )
                response = json.loads(config.output_path.read_text(encoding="utf-8"))
                response["ok"] = True
                return _respond(start_response, 200, response)

            if method == "GET" and path == "/api/telegram/catalog":
                catalog_path = config.local_catalog_path
                if not catalog_path.exists():
                    return _respond(
                        start_response,
                        404,
                        {"ok": False, "error_code": "CATALOG_NOT_FOUND", "path": str(catalog_path)},
                    )
                catalog_payload = json.loads(catalog_path.read_text(encoding="utf-8"))
                return _respond(
                    start_response,
                    200,
                    {
                        "ok": True,
                        "source": "local_catalog_snapshot",
                        "catalog_path": str(catalog_path),
                        "items": catalog_payload,
                    },
                )

            if method == "GET" and path == "/api/health":
                storefront_counts = {"popular_products": 0, "promotions": 0}
                fallback_mode = {"active": False, "source": "", "reason": ""}
                if config.output_path.exists():
                    try:
                        storefront_payload = json.loads(config.output_path.read_text(encoding="utf-8"))
                        storefront_counts = {
                            "popular_products": len(storefront_payload.get("popular_products") or []),
                            "promotions": len(storefront_payload.get("promotions") or []),
                        }
                        fallback_mode = storefront_payload.get("fallback_mode") or fallback_mode
                    except Exception:
                        storefront_counts = {"popular_products": 0, "promotions": 0}
                return _respond(
                    start_response,
                    200,
                    {
                        "ok": True,
                        "mode": backend_mode,
                        "bitrix_webhook_configured": bool(config.bitrix_webhook),
                        "site_lookup_url": config.site_lookup_url,
                        "storefront_path": str(config.output_path),
                        "catalog_path": str(config.local_catalog_path),
                        "diagnostics_path": str(config.diagnostics_path),
                        "empty_fallback_path": str(config.empty_storefront_fallback_path),
                        "storefront_counts": storefront_counts,
                        "fallback_mode": fallback_mode,
                        "crm_request_mode": config.crm_request_mode,
                        "entities": {
                            "popular_products": {
                                "entity_type_id": config.popular_products.entity_type_id,
                                "category_id": config.popular_products.category_id,
                                "active_stage_id": config.popular_products.active_stage_id,
                            },
                            "promotions": {
                                "entity_type_id": config.promotions.entity_type_id,
                                "category_id": config.promotions.category_id,
                                "active_stage_id": config.promotions.active_stage_id,
                            },
                        },
                    },
                )

            return _respond(start_response, 404, {"ok": False, "error_code": "NOT_FOUND"})
        except Exception as exc:
            logger.exception("customer_api_error path=%s error=%s", path, exc)
            return _respond(start_response, 500, {"ok": False, "error_code": "INTERNAL_ERROR"})

    logger.info("customer_api_started host=%s port=%s", config.customer_api_host, config.customer_api_port)
    with make_server(config.customer_api_host, config.customer_api_port, app) as server:
        server.serve_forever()
    return 0


def _registration_payload_from_json(data: dict) -> CustomerRegistrationPayload:
    return CustomerRegistrationPayload(
        first_name=str(data.get("first_name", "")).strip(),
        last_name=str(data.get("last_name", "")).strip(),
        phone=str(data.get("phone", "")).strip(),
        city=str(data.get("city", "")).strip(),
        customer_type=str(data.get("customer_type", "")).strip(),
        company_name=str(data.get("company_name", "")).strip(),
        inn=str(data.get("inn", "")).strip(),
        comment=str(data.get("comment", "")).strip(),
        telegram_user_id=str(data.get("telegram_user_id", "")).strip(),
        telegram_username=str(data.get("telegram_username", "")).strip(),
        telegram_chat_id=str(data.get("telegram_chat_id", "")).strip(),
        source=str(data.get("source", "telegram")).strip() or "telegram",
    )


def _request_payload_from_json(data: dict) -> TelegramRequestPayload:
    return TelegramRequestPayload(
        request_type=str(data.get("request_type", "")).strip(),
        message=str(data.get("message", "")).strip(),
        product_xml_id=str(data.get("product_xml_id", "")).strip(),
        product_name=str(data.get("product_name", "")).strip(),
        quantity=str(data.get("quantity", "")).strip(),
        first_name=str(data.get("first_name", "")).strip(),
        last_name=str(data.get("last_name", "")).strip(),
        phone=str(data.get("phone", "")).strip(),
        company_name=str(data.get("company_name", "")).strip(),
        city=str(data.get("city", "")).strip(),
        telegram_user_id=str(data.get("telegram_user_id", "")).strip(),
        telegram_username=str(data.get("telegram_username", "")).strip(),
        telegram_chat_id=str(data.get("telegram_chat_id", "")).strip(),
        source=str(data.get("source", "telegram")).strip() or "telegram",
    )


def _single(params: dict, key: str) -> str:
    values = params.get(key) or [""]
    return values[0]


def _int_or_none(value: str):
    value = (value or "").strip()
    if not value:
        return None
    return int(value)


def _respond(start_response, status_code: int, payload: dict):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    status_text = {
        200: "200 OK",
        400: "400 Bad Request",
        404: "404 Not Found",
        500: "500 Internal Server Error",
    }.get(status_code, f"{status_code} OK")
    start_response(
        status_text,
        [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Content-Length", str(len(body))),
        ],
    )
    return [body]


if __name__ == "__main__":
    raise SystemExit(run())
