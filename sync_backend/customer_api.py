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
from sync_backend.models import CustomerRegistrationPayload
from sync_backend.services.customer_service import CustomerService


def run() -> int:
    logger = configure_logging()
    config = load_config()
    service = CustomerService(config, Bitrix24Client(config))

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
