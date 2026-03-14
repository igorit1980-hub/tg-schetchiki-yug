from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class SyncError:
    code: str
    message: str
    xml_id: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None


@dataclass
class SyncStats:
    popular_fetched: int = 0
    promotions_fetched: int = 0
    popular_after_filter: int = 0
    promotions_after_filter: int = 0
    popular_after_dedupe: int = 0
    promotions_after_dedupe: int = 0
    joined_products: int = 0
    skipped_items: int = 0


@dataclass
class SyncResult:
    storefront: Dict[str, Any]
    stats: SyncStats
    errors: List[SyncError]


@dataclass(frozen=True)
class CustomerRegistrationPayload:
    first_name: str
    last_name: str
    phone: str
    city: str
    customer_type: str
    company_name: str
    inn: str
    comment: str
    telegram_user_id: str
    telegram_username: str
    telegram_chat_id: str
    source: str


@dataclass(frozen=True)
class CustomerContext:
    contact_id: int
    company_id: Optional[int]
    full_name: str
    phone: str
    customer_type: str
    approval_status: str
    card_status: str
    allowed_price_type: str
    discount_percent: float
    client_card_id: Optional[str]
    client_qr_payload: Optional[str]
    telegram_user_id: Optional[str]
    telegram_username: Optional[str]
    company_name: Optional[str]
    last_sync_at: Optional[str]
    raw: Dict[str, Any]
