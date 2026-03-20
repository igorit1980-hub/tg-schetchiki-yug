from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List, Optional
import json
from urllib.request import Request, urlopen

from ..config import AppConfig
from ..models import CustomerContext, CustomerRegistrationPayload
from ..clients.bitrix24 import Bitrix24Client


class CustomerService:
    def __init__(self, config: AppConfig, bitrix_client: Bitrix24Client) -> None:
        self.config = config
        self.bitrix = bitrix_client
        self.f = config.customer_fields

    def register_customer(self, payload: CustomerRegistrationPayload) -> Dict[str, Any]:
        if not payload.first_name or not payload.phone or not payload.city or not payload.customer_type or not payload.telegram_user_id:
            return {
                "ok": False,
                "error_code": "MISSING_REQUIRED_FIELDS",
                "message": "Не заполнены обязательные поля регистрации",
            }
        normalized_phone = normalize_phone(payload.phone)
        if not normalized_phone:
            return {"ok": False, "error_code": "INVALID_PHONE", "message": "Некорректный телефон"}

        contacts = self._find_contacts(normalized_phone, payload.telegram_user_id)
        if len(contacts) > 1:
            return {
                "ok": False,
                "action": "conflict",
                "error_code": "DUPLICATE_CONTACT",
                "message": "Найдено несколько контактов, нужна ручная проверка",
            }

        company_id = self._resolve_company_id(payload.company_name, payload.inn, payload.customer_type)
        fields = self._build_registration_fields(payload, normalized_phone, company_id)

        action = "created"
        if contacts:
            contact_id = int(contacts[0]["ID"])
            self.bitrix.update_contact(contact_id, fields)
            action = "updated"
        else:
            contact_id = self.bitrix.create_contact(fields)

        card_id = generate_card_id(contact_id)
        qr_payload = generate_qr_payload(card_id)
        self.bitrix.update_contact(
            contact_id,
            {
                self.f["client_card_id"]: card_id,
                self.f["client_qr_payload"]: qr_payload,
                self.f["card_status"]: "issued",
                self.f["last_sync_at"]: current_iso(),
            },
        )

        site_sync = self._sync_registration_to_site(payload, contact_id=contact_id, company_id=company_id, card_id=card_id)
        context = self.get_customer_context(contact_id=contact_id)
        return {
            "ok": True,
            "action": action,
            "contact_id": contact_id,
            "company_id": company_id,
            "client_card_id": card_id,
            "site_sync": site_sync,
            "customer_state": context["customer_state"],
            "approval_status": context["approval_status"],
            "card_status": context["card_status"],
            "allowed_price_type": context["allowed_price_type"],
            "message": "Карта зарегистрирована. Заявка отправлена на проверку менеджеру",
        }

    def get_customer_context(
        self,
        phone: str = "",
        telegram_user_id: str = "",
        contact_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        contact = self._resolve_contact(phone=phone, telegram_user_id=telegram_user_id, contact_id=contact_id)
        if contact is None:
            return {
                "ok": True,
                "customer_state": "guest",
                "can_view_wholesale_prices": False,
                "can_use_loyalty_card": False,
            }

        context = self._contact_to_context(contact)
        return {
            "ok": True,
            "contact_id": context.contact_id,
            "company_id": context.company_id,
            "customer_state": calculate_customer_state(context),
            "approval_status": context.approval_status,
            "card_status": context.card_status,
            "allowed_price_type": context.allowed_price_type,
            "discount_percent": context.discount_percent,
            "can_view_wholesale_prices": context.allowed_price_type == "wholesale"
            and context.approval_status == "approved"
            and context.card_status == "active",
            "can_use_loyalty_card": context.card_status == "active",
            "last_sync_at": context.last_sync_at,
        }

    def get_customer_card(
        self,
        phone: str = "",
        telegram_user_id: str = "",
        contact_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        contact = self._resolve_contact(phone=phone, telegram_user_id=telegram_user_id, contact_id=contact_id)
        if contact is None:
            return {"ok": False, "error_code": "CONTACT_NOT_FOUND", "message": "Клиент не найден"}
        context = self._contact_to_context(contact)
        card_id = context.client_card_id or generate_card_id(context.contact_id)
        qr_payload = context.client_qr_payload or generate_qr_payload(card_id)
        return {
            "ok": True,
            "contact_id": context.contact_id,
            "full_name": context.full_name,
            "phone": context.phone,
            "company_name": context.company_name,
            "customer_type": context.customer_type,
            "client_card_id": card_id,
            "client_qr_payload": qr_payload,
            "approval_status": context.approval_status,
            "card_status": context.card_status,
            "allowed_price_type": context.allowed_price_type,
            "discount_percent": context.discount_percent,
            "card_label": "КАРТА ПОСТОЯННОГО ПОКУПАТЕЛЯ",
            "manual_entry_code": card_id,
        }

    def resolve_customer(self, card_id: str = "", qr_payload: str = "") -> Dict[str, Any]:
        filters: Dict[str, Any] = {}
        if card_id:
            filters[self.f["client_card_id"]] = card_id
        elif qr_payload:
            filters[self.f["client_qr_payload"]] = qr_payload
        else:
            return {"ok": False, "error_code": "INVALID_CARD_ID", "message": "Не указан номер карты или QR"}

        contacts = self.bitrix.list_contacts(filters, select=self._contact_select_fields())
        if not contacts:
            return {"ok": False, "error_code": "CONTACT_NOT_FOUND", "message": "Клиент не найден"}
        if len(contacts) > 1:
            return {"ok": False, "error_code": "DUPLICATE_CONTACT", "message": "Найдено несколько клиентов"}
        context = self._contact_to_context(contacts[0])
        return {
            "ok": True,
            "contact_id": context.contact_id,
            "full_name": context.full_name,
            "company_id": context.company_id,
            "company_name": context.company_name,
            "approval_status": context.approval_status,
            "card_status": context.card_status,
            "allowed_price_type": context.allowed_price_type,
            "discount_percent": context.discount_percent,
            "customer_type": context.customer_type,
        }

    def _find_contacts(self, normalized_phone: str, telegram_user_id: str) -> List[Dict[str, Any]]:
        contacts = self.bitrix.list_contacts(
            {self.f["phone_normalized"]: normalized_phone},
            select=self._contact_select_fields(),
        )
        if contacts or not telegram_user_id:
            return contacts
        return self.bitrix.list_contacts(
            {self.f["telegram_user_id"]: telegram_user_id},
            select=self._contact_select_fields(),
        )

    def _resolve_contact(
        self,
        phone: str = "",
        telegram_user_id: str = "",
        contact_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        if contact_id is not None:
            contacts = self.bitrix.list_contacts({"ID": contact_id}, select=self._contact_select_fields())
            return contacts[0] if contacts else None
        normalized_phone = normalize_phone(phone)
        contacts = self._find_contacts(normalized_phone, telegram_user_id) if (normalized_phone or telegram_user_id) else []
        if len(contacts) != 1:
            return None if not contacts else contacts[0]
        return contacts[0]

    def _resolve_company_id(self, company_name: str, inn: str, customer_type: str) -> Optional[int]:
        company_name = (company_name or "").strip()
        if not company_name:
            return None
        companies = self.bitrix.list_companies({"TITLE": company_name}, select=["ID", "TITLE"])
        if companies:
            return int(companies[0]["ID"])
        fields: Dict[str, Any] = {
            "TITLE": company_name,
            self.f["company_sync_source"]: "telegram",
        }
        if inn:
            fields[self.f["company_inn"]] = inn
        if customer_type:
            fields[self.f["company_type_b2b"]] = customer_type
        return self.bitrix.create_company(fields)

    def _build_registration_fields(
        self,
        payload: CustomerRegistrationPayload,
        normalized_phone: str,
        company_id: Optional[int],
    ) -> Dict[str, Any]:
        full_name = " ".join(part for part in [payload.first_name.strip(), payload.last_name.strip()] if part)
        now = current_iso()
        fields: Dict[str, Any] = {
            "NAME": payload.first_name.strip(),
            "LAST_NAME": payload.last_name.strip(),
            "PHONE": [{"VALUE": payload.phone.strip(), "VALUE_TYPE": "WORK"}],
            "COMMENTS": build_registration_comment(payload),
            "COMPANY_ID": company_id or "",
            self.f["phone_normalized"]: normalized_phone,
            self.f["telegram_user_id"]: payload.telegram_user_id.strip(),
            self.f["telegram_username"]: payload.telegram_username.strip(),
            self.f["telegram_source"]: (payload.source.strip() or "telegram-channel-schetchiki-yug"),
            self.f["customer_type"]: payload.customer_type.strip(),
            self.f["approval_status"]: "pending_review",
            self.f["allowed_price_type"]: "retail",
            self.f["card_status"]: "issued",
            self.f["last_sync_at"]: now,
            self.f["company_name_snapshot"]: payload.company_name.strip(),
        }
        if self.f.get("card_comment"):
            fields[self.f["card_comment"]] = "Заявка на карту и оптовый доступ из Telegram-канала Счетчики Юг"
        if payload.email.strip():
            fields["EMAIL"] = [{"VALUE": payload.email.strip(), "VALUE_TYPE": "WORK"}]
        if payload.city.strip():
            fields["CITY"] = payload.city.strip()
        return fields

    def _contact_select_fields(self) -> List[str]:
        return [
            "ID",
            "NAME",
            "LAST_NAME",
            "PHONE",
            "COMPANY_ID",
            "CITY",
            self.f["telegram_user_id"],
            self.f["telegram_username"],
            self.f["phone_normalized"],
            self.f["customer_type"],
            self.f["client_card_id"],
            self.f["client_qr_payload"],
            self.f["card_status"],
            self.f["approval_status"],
            self.f["allowed_price_type"],
            self.f["discount_percent"],
            self.f["last_sync_at"],
            self.f["company_name_snapshot"],
            "EMAIL",
        ]

    def _sync_registration_to_site(
        self,
        payload: CustomerRegistrationPayload,
        *,
        contact_id: int,
        company_id: Optional[int],
        card_id: str,
    ) -> Dict[str, Any]:
        if not self.config.site_wholesale_sync_api_url:
            return {"ok": False, "mode": "skipped", "reason": "SITE_WHOLESALE_SYNC_API_URL not configured"}

        body = {
            "first_name": payload.first_name.strip(),
            "last_name": payload.last_name.strip(),
            "phone": payload.phone.strip(),
            "email": payload.email.strip(),
            "city": payload.city.strip(),
            "customer_type": payload.customer_type.strip(),
            "company_name": payload.company_name.strip(),
            "inn": payload.inn.strip(),
            "telegram_user_id": payload.telegram_user_id.strip(),
            "telegram_username": payload.telegram_username.strip(),
            "contact_id": contact_id,
            "company_id": company_id,
            "client_card_id": card_id,
            "source": payload.source.strip() or "telegram",
        }
        try:
            request = Request(
                self.config.site_wholesale_sync_api_url,
                data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json; charset=utf-8", "Accept": "application/json"},
                method="POST",
            )
            with urlopen(request, timeout=20) as response:
                data = json.loads(response.read().decode("utf-8"))
            return {"ok": True, "mode": "api", "response": data}
        except Exception as exc:
            return {"ok": False, "mode": "api", "reason": str(exc)}

    def _contact_to_context(self, contact: Dict[str, Any]) -> CustomerContext:
        phone = extract_primary_phone(contact.get("PHONE", []))
        company_id = contact.get("COMPANY_ID")
        company_name = contact.get(self.f["company_name_snapshot"]) or None
        return CustomerContext(
            contact_id=int(contact["ID"]),
            company_id=int(company_id) if company_id not in (None, "", 0, "0") else None,
            full_name=" ".join(part for part in [contact.get("NAME", ""), contact.get("LAST_NAME", "")] if part).strip(),
            phone=phone,
            customer_type=(contact.get(self.f["customer_type"]) or "retail").strip() or "retail",
            approval_status=(contact.get(self.f["approval_status"]) or "new").strip() or "new",
            card_status=(contact.get(self.f["card_status"]) or "not_created").strip() or "not_created",
            allowed_price_type=(contact.get(self.f["allowed_price_type"]) or "retail").strip() or "retail",
            discount_percent=float(contact.get(self.f["discount_percent"]) or 0),
            client_card_id=(contact.get(self.f["client_card_id"]) or "").strip() or None,
            client_qr_payload=(contact.get(self.f["client_qr_payload"]) or "").strip() or None,
            telegram_user_id=(contact.get(self.f["telegram_user_id"]) or "").strip() or None,
            telegram_username=(contact.get(self.f["telegram_username"]) or "").strip() or None,
            company_name=company_name,
            last_sync_at=(contact.get(self.f["last_sync_at"]) or "").strip() or None,
            raw=contact,
        )


def normalize_phone(phone: str) -> str:
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if len(digits) != 11 or not digits.startswith("7"):
        return ""
    return "+" + digits


def extract_primary_phone(phone_field: Any) -> str:
    if isinstance(phone_field, list) and phone_field:
        first = phone_field[0]
        if isinstance(first, dict):
            return str(first.get("VALUE", "")).strip()
    return ""


def generate_card_id(contact_id: int) -> str:
    return f"SY-{contact_id:06d}"


def generate_qr_payload(card_id: str) -> str:
    return f"LOYALTY:{card_id}"


def build_registration_comment(payload: CustomerRegistrationPayload) -> str:
    lines = [
        "Регистрация карты клиента из Telegram Mini App.",
        "Источник: Telegram-канал Счетчики Юг.",
        "Сценарий: заявка на оптовый доступ.",
    ]
    if payload.customer_type.strip():
        lines.append(f"Тип клиента: {payload.customer_type.strip()}.")
    if payload.company_name.strip():
        lines.append(f"Компания: {payload.company_name.strip()}.")
    if payload.comment.strip():
        lines.append(payload.comment.strip())
    return "\n".join(lines)


def calculate_customer_state(context: CustomerContext) -> str:
    if context.approval_status == "rejected":
        return "rejected"
    if context.card_status in {"archived", "blocked"}:
        return "archived"
    if (
        context.approval_status == "approved"
        and context.card_status == "active"
        and context.allowed_price_type == "wholesale"
    ):
        return "approved_wholesale"
    if context.approval_status in {"pending_review", "new"}:
        return "pending_review"
    return "registration_submitted"


def current_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
