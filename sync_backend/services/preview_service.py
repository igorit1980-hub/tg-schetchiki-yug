from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import AppConfig
from ..models import CustomerRegistrationPayload, TelegramRequestPayload
from .customer_service import (
    calculate_customer_state,
    current_iso,
    generate_card_id,
    generate_qr_payload,
    normalize_phone,
)


class PreviewService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.state_path = config.output_path.parent / "preview_state.json"

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

        state = self._load_state()
        contact = self._find_contact(state["contacts"], normalized_phone, payload.telegram_user_id)
        action = "updated" if contact else "created"

        if not contact:
            contact = {
                "id": state["next_contact_id"],
                "approval_status": "pending_review",
                "card_status": "not_created",
                "allowed_price_type": "retail",
                "discount_percent": 0,
                "client_card_id": "",
                "client_qr_payload": "",
                "company_id": None,
            }
            state["next_contact_id"] += 1
            state["contacts"].append(contact)

        contact.update(
            {
                "first_name": payload.first_name.strip(),
                "last_name": payload.last_name.strip(),
                "phone": payload.phone.strip(),
                "phone_normalized": normalized_phone,
                "city": payload.city.strip(),
                "customer_type": payload.customer_type.strip(),
                "company_name": payload.company_name.strip(),
                "inn": payload.inn.strip(),
                "comment": payload.comment.strip(),
                "telegram_user_id": payload.telegram_user_id.strip(),
                "telegram_username": payload.telegram_username.strip(),
                "telegram_chat_id": payload.telegram_chat_id.strip(),
                "source": payload.source.strip() or "telegram",
                "last_sync_at": current_iso(),
            }
        )

        self._save_state(state)
        context = self.get_customer_context(contact_id=contact["id"])
        return {
            "ok": True,
            "action": action,
            "contact_id": contact["id"],
            "company_id": contact.get("company_id"),
            "customer_state": context["customer_state"],
            "approval_status": context["approval_status"],
            "card_status": context["card_status"],
            "allowed_price_type": context["allowed_price_type"],
            "message": "Заявка принята в локальном preview и ожидает подтверждения менеджером",
        }

    def get_customer_context(
        self,
        phone: str = "",
        telegram_user_id: str = "",
        contact_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        state = self._load_state()
        contact = self._resolve_contact(state["contacts"], phone=phone, telegram_user_id=telegram_user_id, contact_id=contact_id)
        if contact is None:
            return {
                "ok": True,
                "customer_state": "guest",
                "can_view_wholesale_prices": False,
                "can_use_loyalty_card": False,
            }

        return self._context_response(contact)

    def get_customer_card(
        self,
        phone: str = "",
        telegram_user_id: str = "",
        contact_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        state = self._load_state()
        contact = self._resolve_contact(state["contacts"], phone=phone, telegram_user_id=telegram_user_id, contact_id=contact_id)
        if contact is None:
            return {"ok": False, "error_code": "CONTACT_NOT_FOUND", "message": "Клиент не найден"}

        card_id = contact.get("client_card_id") or generate_card_id(int(contact["id"]))
        qr_payload = contact.get("client_qr_payload") or generate_qr_payload(card_id)
        return {
            "ok": True,
            "contact_id": int(contact["id"]),
            "full_name": " ".join(part for part in [contact.get("first_name", ""), contact.get("last_name", "")] if part).strip(),
            "phone": contact.get("phone") or "",
            "company_name": contact.get("company_name") or None,
            "customer_type": contact.get("customer_type") or "retail",
            "client_card_id": card_id,
            "client_qr_payload": qr_payload,
            "approval_status": contact.get("approval_status") or "new",
            "card_status": contact.get("card_status") or "not_created",
            "allowed_price_type": contact.get("allowed_price_type") or "retail",
            "discount_percent": float(contact.get("discount_percent") or 0),
            "card_label": "КАРТА ПОСТОЯННОГО ПОКУПАТЕЛЯ",
            "manual_entry_code": card_id,
        }

    def resolve_customer(self, card_id: str = "", qr_payload: str = "") -> Dict[str, Any]:
        state = self._load_state()
        for contact in state["contacts"]:
            current_card_id = contact.get("client_card_id") or generate_card_id(int(contact["id"]))
            current_qr_payload = contact.get("client_qr_payload") or generate_qr_payload(current_card_id)
            if (card_id and current_card_id == card_id) or (qr_payload and current_qr_payload == qr_payload):
                return {
                    "ok": True,
                    "contact_id": int(contact["id"]),
                    "full_name": " ".join(part for part in [contact.get("first_name", ""), contact.get("last_name", "")] if part).strip(),
                    "company_id": contact.get("company_id"),
                    "company_name": contact.get("company_name") or None,
                    "approval_status": contact.get("approval_status") or "new",
                    "card_status": contact.get("card_status") or "not_created",
                    "allowed_price_type": contact.get("allowed_price_type") or "retail",
                    "discount_percent": float(contact.get("discount_percent") or 0),
                    "customer_type": contact.get("customer_type") or "retail",
                }
        return {"ok": False, "error_code": "CONTACT_NOT_FOUND", "message": "Клиент не найден"}

    def submit_request(self, payload: TelegramRequestPayload) -> Dict[str, Any]:
        request_type = (payload.request_type or "").strip().lower()
        if not request_type:
            return {"ok": False, "error_code": "MISSING_REQUEST_TYPE", "message": "Не указан тип обращения"}
        if not payload.message.strip() and not payload.product_xml_id.strip() and not payload.product_name.strip():
            return {
                "ok": False,
                "error_code": "EMPTY_REQUEST",
                "message": "Нужно передать сообщение, товар или XML ID",
            }

        state = self._load_state()
        normalized_phone = normalize_phone(payload.phone)
        contact = self._find_contact(state["contacts"], normalized_phone, payload.telegram_user_id.strip())
        request_id = state["next_request_id"]
        state["next_request_id"] += 1
        state["requests"].append(
            {
                "id": request_id,
                "request_type": request_type,
                "message": payload.message.strip(),
                "product_xml_id": payload.product_xml_id.strip(),
                "product_name": payload.product_name.strip(),
                "quantity": payload.quantity.strip(),
                "first_name": payload.first_name.strip(),
                "last_name": payload.last_name.strip(),
                "phone": payload.phone.strip(),
                "company_name": payload.company_name.strip(),
                "city": payload.city.strip(),
                "telegram_user_id": payload.telegram_user_id.strip(),
                "telegram_username": payload.telegram_username.strip(),
                "telegram_chat_id": payload.telegram_chat_id.strip(),
                "source": payload.source.strip() or "telegram",
                "contact_id": int(contact["id"]) if contact else None,
                "created_at": current_iso(),
            }
        )
        self._save_state(state)
        return {
            "ok": True,
            "entity_type": "preview_request",
            "entity_id": request_id,
            "contact_id": int(contact["id"]) if contact else None,
            "request_type": request_type,
            "message": "Обращение сохранено в локальном preview",
        }

    def _context_response(self, contact: Dict[str, Any]) -> Dict[str, Any]:
        customer_state = calculate_customer_state(
            _PreviewContext(
                approval_status=contact.get("approval_status") or "new",
                card_status=contact.get("card_status") or "not_created",
                allowed_price_type=contact.get("allowed_price_type") or "retail",
            )
        )
        return {
            "ok": True,
            "contact_id": int(contact["id"]),
            "company_id": contact.get("company_id"),
            "customer_state": customer_state,
            "approval_status": contact.get("approval_status") or "new",
            "card_status": contact.get("card_status") or "not_created",
            "allowed_price_type": contact.get("allowed_price_type") or "retail",
            "discount_percent": float(contact.get("discount_percent") or 0),
            "can_view_wholesale_prices": (contact.get("approval_status") == "approved")
            and (contact.get("card_status") == "active")
            and (contact.get("allowed_price_type") == "wholesale"),
            "can_use_loyalty_card": contact.get("card_status") == "active",
            "last_sync_at": contact.get("last_sync_at") or None,
        }

    def _load_state(self) -> Dict[str, Any]:
        if not self.state_path.exists():
            return {"next_contact_id": 100001, "next_request_id": 500001, "contacts": [], "requests": []}
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def _save_state(self, state: Dict[str, Any]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    def _find_contact(
        self,
        contacts: List[Dict[str, Any]],
        normalized_phone: str,
        telegram_user_id: str,
    ) -> Optional[Dict[str, Any]]:
        if normalized_phone:
            for contact in contacts:
                if contact.get("phone_normalized") == normalized_phone:
                    return contact
        if telegram_user_id:
            for contact in contacts:
                if contact.get("telegram_user_id") == telegram_user_id:
                    return contact
        return None

    def _resolve_contact(
        self,
        contacts: List[Dict[str, Any]],
        phone: str = "",
        telegram_user_id: str = "",
        contact_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        if contact_id is not None:
            for contact in contacts:
                if int(contact["id"]) == int(contact_id):
                    return contact
            return None
        return self._find_contact(contacts, normalize_phone(phone), telegram_user_id.strip())


class _PreviewContext:
    def __init__(self, approval_status: str, card_status: str, allowed_price_type: str) -> None:
        self.approval_status = approval_status
        self.card_status = card_status
        self.allowed_price_type = allowed_price_type
