from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


BASE_DIR = Path(__file__).resolve().parent.parent
KNOWLEDGE_BASE_DIR = BASE_DIR / "knowledge-base"


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _load_local_env() -> None:
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class EntityConfig:
    name: str
    entity_type_id: int
    category_id: int
    active_stage_id: str


@dataclass(frozen=True)
class AppConfig:
    timezone: str
    bitrix_webhook: str
    bitrix_enabled: bool
    site_lookup_url: str
    output_path: Path
    diagnostics_path: Path
    empty_storefront_fallback_path: Path
    customer_api_host: str
    customer_api_port: int
    crm_request_mode: str
    crm_request_title_prefix: str
    popular_products: EntityConfig
    promotions: EntityConfig
    local_catalog_path: Path
    customer_fields: Dict[str, str]


def _default_customer_fields() -> Dict[str, str]:
    return {
        "telegram_user_id": "UF_CRM_TG_USER_ID",
        "telegram_username": "UF_CRM_TG_USERNAME",
        "telegram_source": "UF_CRM_TG_SOURCE",
        "phone_normalized": "UF_CRM_PHONE_NORMALIZED",
        "customer_type": "UF_CRM_CUSTOMER_TYPE",
        "client_card_id": "UF_CRM_CLIENT_CARD_ID",
        "client_qr_payload": "UF_CRM_CLIENT_QR_PAYLOAD",
        "card_status": "UF_CRM_CARD_STATUS",
        "approval_status": "UF_CRM_APPROVAL_STATUS",
        "allowed_price_type": "UF_CRM_ALLOWED_PRICE_TYPE",
        "discount_percent": "UF_CRM_DISCOUNT_PERCENT",
        "approved_at": "UF_CRM_APPROVED_AT",
        "rejected_at": "UF_CRM_REJECTED_AT",
        "last_sync_at": "UF_CRM_LAST_SYNC_AT",
        "company_name_snapshot": "UF_CRM_COMPANY_NAME_SNAPSHOT",
        "card_comment": "UF_CRM_CARD_COMMENT",
        "company_type_b2b": "UF_CRM_COMPANY_TYPE_B2B",
        "company_inn": "UF_CRM_COMPANY_INN",
        "company_sync_source": "UF_CRM_COMPANY_SYNC_SOURCE",
    }


def load_config() -> AppConfig:
    _load_local_env()
    canonical = _load_json(KNOWLEDGE_BASE_DIR / "canonical-model.json")
    bitrix = _load_json(KNOWLEDGE_BASE_DIR / "bitrix24-config.json")
    site = _load_json(KNOWLEDGE_BASE_DIR / "site-catalog-config.json")

    systems = canonical["systems"]
    webhook = os.environ.get("BITRIX24_WEBHOOK", "").strip()

    site_lookup_url = os.environ.get("SITE_CATALOG_LOOKUP_URL", "").strip()
    if not site_lookup_url:
        site_lookup_url = systems["site"]["domain"] + site["preferred_lookup_endpoint"]

    output_path = Path(
        os.environ.get(
            "STORE_OUTPUT_PATH",
            str(BASE_DIR / "output" / "storefront.json"),
        )
    )

    return AppConfig(
        timezone=canonical["timezone"],
        bitrix_webhook=webhook.rstrip("/") + "/" if webhook else "",
        bitrix_enabled=bool(webhook),
        site_lookup_url=site_lookup_url,
        output_path=output_path,
        diagnostics_path=Path(
            os.environ.get(
                "STORE_DIAGNOSTICS_PATH",
                str(BASE_DIR / "output" / "storefront.diagnostics.json"),
            )
        ),
        empty_storefront_fallback_path=Path(
            os.environ.get(
                "STORE_EMPTY_FALLBACK_PATH",
                str(BASE_DIR / "output" / "storefront.test.json"),
            )
        ),
        customer_api_host=os.environ.get("CUSTOMER_API_HOST", "127.0.0.1"),
        customer_api_port=int(os.environ.get("CUSTOMER_API_PORT", "8787")),
        crm_request_mode=os.environ.get("CRM_REQUEST_MODE", "lead").strip() or "lead",
        crm_request_title_prefix=os.environ.get("CRM_REQUEST_TITLE_PREFIX", "Telegram").strip() or "Telegram",
        popular_products=EntityConfig(
            name="popular_products",
            entity_type_id=bitrix["entities"]["popular_products"]["entity_type_id"],
            category_id=bitrix["entities"]["popular_products"]["category_id"],
            active_stage_id=bitrix["entities"]["popular_products"]["active_stage_id"],
        ),
        promotions=EntityConfig(
            name="promotions",
            entity_type_id=bitrix["entities"]["promotions"]["entity_type_id"],
            category_id=bitrix["entities"]["promotions"]["category_id"],
            active_stage_id=bitrix["entities"]["promotions"]["active_stage_id"],
        ),
        local_catalog_path=BASE_DIR / "catalog_priced.json",
        customer_fields=_default_customer_fields(),
    )
