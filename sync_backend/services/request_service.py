from __future__ import annotations

from typing import Any, Dict, Optional

from ..clients.bitrix24 import Bitrix24Client
from ..config import AppConfig
from ..models import TelegramRequestPayload
from .customer_service import normalize_phone


class RequestService:
    def __init__(self, config: AppConfig, bitrix_client: Bitrix24Client) -> None:
        self.config = config
        self.bitrix = bitrix_client
        self.f = config.customer_fields

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

        normalized_phone = normalize_phone(payload.phone)
        contact_id = self._resolve_contact_id(normalized_phone, payload.telegram_user_id.strip())

        fields = self._build_crm_fields(payload, normalized_phone, contact_id)
        mode = self.config.crm_request_mode.lower()

        if mode == "deal":
            entity_id = self.bitrix.create_deal(fields)
            entity_type = "deal"
        else:
            entity_id = self.bitrix.create_lead(fields)
            entity_type = "lead"

        return {
            "ok": True,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "contact_id": contact_id,
            "request_type": request_type,
            "message": "Обращение отправлено в Bitrix24",
        }

    def _resolve_contact_id(self, normalized_phone: str, telegram_user_id: str) -> Optional[int]:
        contacts = []
        if normalized_phone:
            contacts = self.bitrix.list_contacts(
                {self.f["phone_normalized"]: normalized_phone},
                select=["ID"],
            )
        if not contacts and telegram_user_id:
            contacts = self.bitrix.list_contacts(
                {self.f["telegram_user_id"]: telegram_user_id},
                select=["ID"],
            )
        if not contacts:
            return None
        return int(contacts[0]["ID"])

    def _build_crm_fields(
        self,
        payload: TelegramRequestPayload,
        normalized_phone: str,
        contact_id: Optional[int],
    ) -> Dict[str, Any]:
        full_name = " ".join(part for part in [payload.first_name.strip(), payload.last_name.strip()] if part).strip()
        title_parts = [self.config.crm_request_title_prefix, payload.request_type.strip() or "request"]
        if payload.product_name.strip():
            title_parts.append(payload.product_name.strip())
        title = " | ".join(title_parts)

        comment_lines = [
            f"Источник: {payload.source.strip() or 'telegram'}",
            f"Тип обращения: {payload.request_type.strip() or '-'}",
            f"Сообщение: {payload.message.strip() or '-'}",
            f"XML ID товара: {payload.product_xml_id.strip() or '-'}",
            f"Товар: {payload.product_name.strip() or '-'}",
            f"Количество: {payload.quantity.strip() or '-'}",
            f"Telegram user id: {payload.telegram_user_id.strip() or '-'}",
            f"Telegram username: @{payload.telegram_username.strip()}" if payload.telegram_username.strip() else "Telegram username: -",
            f"Telegram chat id: {payload.telegram_chat_id.strip() or '-'}",
            f"Компания: {payload.company_name.strip() or '-'}",
            f"Город: {payload.city.strip() or '-'}",
        ]

        fields: Dict[str, Any] = {
            "TITLE": title,
            "COMMENTS": "\n".join(comment_lines),
            "NAME": payload.first_name.strip(),
            "LAST_NAME": payload.last_name.strip(),
            "SOURCE_DESCRIPTION": "Telegram Mini App / Telegram Bot",
        }

        if payload.phone.strip():
            fields["PHONE"] = [{"VALUE": payload.phone.strip(), "VALUE_TYPE": "WORK"}]
        if full_name:
            fields["TITLE"] = title
        if payload.company_name.strip():
            fields["COMPANY_TITLE"] = payload.company_name.strip()
        if payload.city.strip():
            fields["ADDRESS_CITY"] = payload.city.strip()
        if contact_id is not None:
            fields["CONTACT_ID"] = contact_id

        return fields
