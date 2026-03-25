from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
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
        self.field_aliases: Dict[str, List[str]] = {
            "telegram_user_id": ["UF_CRM_TG_USER_ID"],
            "telegram_username": ["UF_CRM_TG_USERNAME"],
            "telegram_source": ["UF_CRM_TG_SOURCE", "UF_CRM_CLIENT_SOURCE"],
            "phone_normalized": ["UF_CRM_PHONE_NORMALIZED"],
            "customer_type": ["UF_CRM_CUSTOMER_TYPE"],
            "client_card_id": ["UF_CRM_CLIENT_CARD_ID", "UF_CRM_CLIENT_CARD_NO"],
            "client_qr_payload": ["UF_CRM_CLIENT_QR_PAYLOAD", "UF_CRM_CLIENT_CARD_QR"],
            "card_status": ["UF_CRM_CARD_STATUS", "UF_CRM_CLIENT_CARD_STATUS"],
            "approval_status": ["UF_CRM_APPROVAL_STATUS"],
            "allowed_price_type": ["UF_CRM_ALLOWED_PRICE_TYPE"],
            "discount_percent": ["UF_CRM_DISCOUNT_PERCENT", "UF_CRM_CLIENT_DISCOUNT"],
            "approved_at": ["UF_CRM_APPROVED_AT"],
            "rejected_at": ["UF_CRM_REJECTED_AT"],
            "last_sync_at": ["UF_CRM_LAST_SYNC_AT", "UF_CRM_CLIENT_CARD_REGISTERED_AT"],
            "company_name_snapshot": ["UF_CRM_COMPANY_NAME_SNAPSHOT"],
            "card_comment": ["UF_CRM_CARD_COMMENT"],
        }
        self.field_name_to_logical: Dict[str, str] = {}
        for logical_key, targets in self.field_aliases.items():
            for field_name in [logical_key, *targets]:
                self.field_name_to_logical[field_name] = logical_key
        self._supported_contact_fields: Optional[set[str]] = None

    def _field_targets(self, key: str) -> List[str]:
        targets = [key]
        for alias in self.field_aliases.get(key, []):
            if alias not in targets:
                targets.append(alias)
        return targets

    def _contact_field_value(self, contact: Dict[str, Any], key: str, default: Any = "") -> Any:
        for field in self._field_targets(key):
            value = contact.get(field)
            if value not in (None, "", [], {}):
                return value
        return default

    def _shadow_field_value(self, shadow: Optional[Dict[str, Any]], key: str, default: Any = "") -> Any:
        if not shadow:
            return default
        for field in self._field_targets(key):
            value = shadow.get(field)
            if value not in (None, "", [], {}):
                return value
        return default

    def _best_supported_field(self, key: str) -> Optional[str]:
        supported = self._contact_fields()
        for field_name in self._field_targets(key):
            if field_name in supported:
                return field_name
        return None

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

        contacts = self._find_contacts(normalized_phone, payload.telegram_user_id, payload.phone)
        if len(contacts) > 1:
            return {
                "ok": False,
                "action": "conflict",
                "error_code": "DUPLICATE_CONTACT",
                "message": "Найдено несколько контактов, нужна ручная проверка",
            }

        company_id = None
        fields = self._build_registration_fields(payload, normalized_phone)

        action = "created"
        if contacts:
            contact_id = int(contacts[0]["ID"])
            self.bitrix.update_contact(contact_id, fields)
            action = "updated"
        else:
            contact_id = self.bitrix.create_contact(fields)

        card_id = generate_card_id(contact_id)
        qr_payload = generate_qr_payload(card_id)
        contact_update_fields = self._supported_custom_fields(
            {
                self.f["client_card_id"]: card_id,
                self.f["client_qr_payload"]: qr_payload,
                self.f["card_status"]: "active",
                self.f["approval_status"]: "approved",
                self.f["allowed_price_type"]: "wholesale",
                self.f["discount_percent"]: 0,
                self.f["approved_at"]: current_iso(),
                self.f["last_sync_at"]: current_iso(),
            }
        )
        if contact_update_fields:
            self.bitrix.update_contact(contact_id, contact_update_fields)

        shadow_record = self._save_shadow_state(
            {
                "contact_id": contact_id,
                "phone": payload.phone.strip(),
                "phone_normalized": normalized_phone,
                "telegram_user_id": payload.telegram_user_id.strip(),
                "telegram_username": payload.telegram_username.strip(),
                "first_name": payload.first_name.strip(),
                "last_name": payload.last_name.strip(),
                "full_name": " ".join(part for part in [payload.first_name.strip(), payload.last_name.strip()] if part).strip(),
                "email": payload.email.strip(),
                "city": payload.city.strip(),
                "customer_type": payload.customer_type.strip() or "retail",
                "client_card_id": card_id,
                "client_qr_payload": qr_payload,
                "approval_status": "approved",
                "card_status": "active",
                "allowed_price_type": "wholesale",
                "discount_percent": 0,
                "company_name": None,
                "last_sync_at": current_iso(),
                "site_sync": None,
            }
        )

        site_sync = self._sync_registration_to_site(payload, contact_id=contact_id, company_id=company_id, card_id=card_id)
        shadow_record["site_sync"] = site_sync
        shadow_record["last_sync_at"] = current_iso()
        self._save_shadow_state(shadow_record)
        context = self.get_customer_context(contact_id=contact_id)
        if site_sync.get("ok"):
            message = "Карта создана и активирована. Оптовые цены открыты"
        else:
            message = "Карта создана и активирована в CRM. Сайт будет синхронизирован после выкладки endpoint"
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
            "message": message,
        }

    def get_customer_context(
        self,
        phone: str = "",
        telegram_user_id: str = "",
        contact_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        contact = self._resolve_contact(phone=phone, telegram_user_id=telegram_user_id, contact_id=contact_id)
        if contact is None:
            shadow = self._get_shadow_state(phone=phone, telegram_user_id=telegram_user_id, contact_id=contact_id)
            if shadow is not None:
                context = self._shadow_to_context(shadow)
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
                    and context.card_status == "active"
                    and context.approval_status != "rejected",
                    "can_use_loyalty_card": context.card_status == "active",
                    "last_sync_at": context.last_sync_at,
                }
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
            and context.card_status == "active"
            and context.approval_status != "rejected",
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
            shadow = self._get_shadow_state(phone=phone, telegram_user_id=telegram_user_id, contact_id=contact_id)
            if shadow is None:
                return {"ok": False, "error_code": "CONTACT_NOT_FOUND", "message": "Клиент не найден"}
            context = self._shadow_to_context(shadow)
        else:
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
        card_field = self._best_supported_field("client_card_id")
        qr_field = self._best_supported_field("client_qr_payload")
        if card_id and card_field:
            filters[card_field] = card_id
        elif qr_payload and qr_field:
            filters[qr_field] = qr_payload
        else:
            return {"ok": False, "error_code": "INVALID_CARD_ID", "message": "Не указан номер карты или QR"}

        if (card_id and not card_field) or (qr_payload and not qr_field):
            shadow = self._get_shadow_state(card_id=card_id, qr_payload=qr_payload)
            if shadow is None:
                return {"ok": False, "error_code": "CONTACT_NOT_FOUND", "message": "Клиент не найден"}
            context = self._shadow_to_context(shadow)
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

    def _find_contacts(self, normalized_phone: str, telegram_user_id: str, raw_phone: str = "") -> List[Dict[str, Any]]:
        contacts: List[Dict[str, Any]] = []
        if normalized_phone:
            phone_field = self._best_supported_field("phone_normalized")
            if phone_field:
                contacts = self.bitrix.list_contacts(
                    {phone_field: normalized_phone},
                    select=self._contact_select_fields(),
                )
            elif raw_phone.strip():
                contacts = self.bitrix.list_contacts(
                    {"PHONE": raw_phone.strip()},
                    select=self._contact_select_fields(),
                )
                contacts = [item for item in contacts if normalize_phone(extract_primary_phone(item.get("PHONE", []))) == normalized_phone]
        if contacts or not telegram_user_id:
            return self._dedupe_contacts(contacts)
        telegram_field = self._best_supported_field("telegram_user_id")
        if telegram_field:
            return self._dedupe_contacts(
                self.bitrix.list_contacts(
                    {telegram_field: telegram_user_id},
                    select=self._contact_select_fields(),
                )
            )
        shadow = self._get_shadow_state(telegram_user_id=telegram_user_id)
        if shadow and shadow.get("contact_id"):
            contact = self._resolve_contact(contact_id=int(shadow["contact_id"]))
            return [contact] if contact else []
        return []

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
        contacts = self._find_contacts(normalized_phone, telegram_user_id, phone) if (normalized_phone or telegram_user_id) else []
        if len(contacts) != 1:
            return None if not contacts else contacts[0]
        return contacts[0]

    def _build_registration_fields(
        self,
        payload: CustomerRegistrationPayload,
        normalized_phone: str,
    ) -> Dict[str, Any]:
        now = current_iso()
        fields: Dict[str, Any] = {
            "NAME": payload.first_name.strip(),
            "LAST_NAME": payload.last_name.strip(),
            "PHONE": [{"VALUE": payload.phone.strip(), "VALUE_TYPE": "WORK"}],
            "COMMENTS": build_registration_comment(payload),
            "SOURCE_DESCRIPTION": f"Telegram Mini App / Счетчики Юг / {payload.customer_type.strip() or 'client'}",
        }
        fields.update(
            self._supported_custom_fields(
                {
                    self.f["phone_normalized"]: normalized_phone,
                    self.f["telegram_user_id"]: payload.telegram_user_id.strip(),
                    self.f["telegram_username"]: payload.telegram_username.strip(),
                    self.f["telegram_source"]: (payload.source.strip() or "telegram-channel-schetchiki-yug"),
                    self.f["customer_type"]: payload.customer_type.strip(),
                    self.f["approval_status"]: "approved",
                    self.f["allowed_price_type"]: "wholesale",
                    self.f["card_status"]: "active",
                    self.f["discount_percent"]: 0,
                    self.f["approved_at"]: now,
                    self.f["last_sync_at"]: now,
                }
            )
        )
        if self.f.get("card_comment"):
            fields.update(
                self._supported_custom_fields(
                    {self.f["card_comment"]: "Заявка на карту и оптовый доступ из Telegram-канала Счетчики Юг"}
                )
            )
        if payload.email.strip():
            fields["EMAIL"] = [{"VALUE": payload.email.strip(), "VALUE_TYPE": "WORK"}]
        if payload.city.strip():
            fields["CITY"] = payload.city.strip()
        return fields

    def _contact_select_fields(self) -> List[str]:
        fields = [
            "ID",
            "NAME",
            "LAST_NAME",
            "PHONE",
            "COMPANY_ID",
            "CITY",
            "EMAIL",
        ]
        logical_fields = [
            "telegram_user_id",
            "telegram_username",
            "phone_normalized",
            "customer_type",
            "client_card_id",
            "client_qr_payload",
            "card_status",
            "approval_status",
            "allowed_price_type",
            "discount_percent",
            "approved_at",
            "rejected_at",
            "last_sync_at",
            "company_name_snapshot",
            "card_comment",
        ]
        for logical_key in logical_fields:
            for field in self._field_targets(logical_key):
                if field not in fields:
                    fields.append(field)
        return fields

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
            "telegram_user_id": payload.telegram_user_id.strip(),
            "telegram_username": payload.telegram_username.strip(),
            "contact_id": contact_id,
            "company_id": company_id,
            "client_card_id": card_id,
            "client_qr_payload": generate_qr_payload(card_id),
            "approval_status": "approved",
            "card_status": "active",
            "allowed_price_type": "wholesale",
            "source": payload.source.strip() or "telegram",
            "comment": payload.comment.strip(),
        }
        try:
            headers = {
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "application/json",
            }
            if self.config.site_wholesale_sync_api_token:
                headers["X-Api-Key"] = self.config.site_wholesale_sync_api_token
            request = Request(
                self.config.site_wholesale_sync_api_url,
                data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urlopen(request, timeout=20) as response:
                data = json.loads(response.read().decode("utf-8"))
            if isinstance(data, dict) and data.get("ok") is False:
                return {"ok": False, "mode": "api", "response": data, "reason": data.get("message") or data.get("error")}
            return {"ok": True, "mode": "api", "response": data}
        except Exception as exc:
            return {"ok": False, "mode": "api", "reason": str(exc)}

    def _contact_to_context(self, contact: Dict[str, Any]) -> CustomerContext:
        phone = extract_primary_phone(contact.get("PHONE", []))
        company_id = contact.get("COMPANY_ID")
        company_name = self._contact_field_value(contact, "company_name_snapshot") or None
        shadow = self._get_shadow_state(
            phone=phone,
            telegram_user_id=str(self._contact_field_value(contact, "telegram_user_id") or "").strip(),
            contact_id=int(contact["ID"]),
        )
        return CustomerContext(
            contact_id=int(contact["ID"]),
            company_id=int(company_id) if company_id not in (None, "", 0, "0") else None,
            full_name=" ".join(part for part in [contact.get("NAME", ""), contact.get("LAST_NAME", "")] if part).strip(),
            phone=phone or ((shadow or {}).get("phone") or ""),
            customer_type=str(self._contact_field_value(contact, "customer_type") or self._shadow_field_value(shadow, "customer_type") or "retail").strip() or "retail",
            approval_status=str(self._contact_field_value(contact, "approval_status") or self._shadow_field_value(shadow, "approval_status") or "new").strip() or "new",
            card_status=str(self._contact_field_value(contact, "card_status") or self._shadow_field_value(shadow, "card_status") or "not_created").strip() or "not_created",
            allowed_price_type=str(self._contact_field_value(contact, "allowed_price_type") or self._shadow_field_value(shadow, "allowed_price_type") or "retail").strip() or "retail",
            discount_percent=float(self._contact_field_value(contact, "discount_percent", self._shadow_field_value(shadow, "discount_percent", 0)) or 0),
            client_card_id=str(self._contact_field_value(contact, "client_card_id") or self._shadow_field_value(shadow, "client_card_id") or "").strip() or None,
            client_qr_payload=str(self._contact_field_value(contact, "client_qr_payload") or self._shadow_field_value(shadow, "client_qr_payload") or "").strip() or None,
            telegram_user_id=str(self._contact_field_value(contact, "telegram_user_id") or self._shadow_field_value(shadow, "telegram_user_id") or "").strip() or None,
            telegram_username=str(self._contact_field_value(contact, "telegram_username") or self._shadow_field_value(shadow, "telegram_username") or "").strip() or None,
            company_name=company_name or (shadow or {}).get("company_name"),
            last_sync_at=str(self._contact_field_value(contact, "last_sync_at") or self._shadow_field_value(shadow, "last_sync_at") or "").strip() or None,
            raw=contact,
        )

    def _shadow_state_path(self) -> Path:
        return self.config.customer_state_path

    def _load_shadow_state(self) -> List[Dict[str, Any]]:
        path = self._shadow_state_path()
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
        records = payload.get("records") if isinstance(payload, dict) else payload
        return records if isinstance(records, list) else []

    def _write_shadow_state(self, records: List[Dict[str, Any]]) -> None:
        path = self._shadow_state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"records": records}, ensure_ascii=False, indent=2), encoding="utf-8")

    def _save_shadow_state(self, record: Dict[str, Any]) -> Dict[str, Any]:
        records = self._load_shadow_state()
        updated = False
        for index, existing in enumerate(records):
            if self._same_shadow_record(existing, record):
                merged = dict(existing)
                merged.update({key: value for key, value in record.items() if value not in (None, "")})
                records[index] = merged
                record = merged
                updated = True
                break
        if not updated:
            records.append(record)
        self._write_shadow_state(records)
        return record

    def _same_shadow_record(self, left: Dict[str, Any], right: Dict[str, Any]) -> bool:
        for key in ("contact_id", "phone_normalized", "telegram_user_id", "client_card_id", "client_qr_payload"):
            if left.get(key) and right.get(key) and left.get(key) == right.get(key):
                return True
        return False

    def _get_shadow_state(
        self,
        *,
        phone: str = "",
        telegram_user_id: str = "",
        contact_id: Optional[int] = None,
        card_id: str = "",
        qr_payload: str = "",
    ) -> Optional[Dict[str, Any]]:
        normalized_phone = normalize_phone(phone)
        for record in self._load_shadow_state():
            if contact_id is not None and str(record.get("contact_id") or "") == str(contact_id):
                return record
            if normalized_phone and record.get("phone_normalized") == normalized_phone:
                return record
            if telegram_user_id and record.get("telegram_user_id") == telegram_user_id:
                return record
            if card_id and record.get("client_card_id") == card_id:
                return record
            if qr_payload and record.get("client_qr_payload") == qr_payload:
                return record
        return None

    def _shadow_to_context(self, shadow: Dict[str, Any]) -> CustomerContext:
        return CustomerContext(
            contact_id=int(shadow.get("contact_id") or 0),
            company_id=None,
            full_name=shadow.get("full_name") or " ".join(
                part for part in [shadow.get("first_name", ""), shadow.get("last_name", "")] if part
            ).strip(),
            phone=shadow.get("phone") or "",
            customer_type=self._shadow_field_value(shadow, "customer_type") or "retail",
            approval_status=self._shadow_field_value(shadow, "approval_status") or "new",
            card_status=self._shadow_field_value(shadow, "card_status") or "not_created",
            allowed_price_type=self._shadow_field_value(shadow, "allowed_price_type") or "retail",
            discount_percent=float(self._shadow_field_value(shadow, "discount_percent") or 0),
            client_card_id=self._shadow_field_value(shadow, "client_card_id") or None,
            client_qr_payload=self._shadow_field_value(shadow, "client_qr_payload") or None,
            telegram_user_id=self._shadow_field_value(shadow, "telegram_user_id") or None,
            telegram_username=self._shadow_field_value(shadow, "telegram_username") or None,
            company_name=self._shadow_field_value(shadow, "company_name_snapshot") or self._shadow_field_value(shadow, "company_name") or None,
            last_sync_at=self._shadow_field_value(shadow, "last_sync_at") or None,
            raw=shadow,
        )

    def _contact_fields(self) -> set[str]:
        if self._supported_contact_fields is None:
            try:
                self._supported_contact_fields = set((self.bitrix._call("crm.contact.fields", {}).get("result") or {}).keys())
            except Exception:
                self._supported_contact_fields = set()
        return self._supported_contact_fields

    def _supports_all(self, field_codes: List[str]) -> bool:
        supported = self._contact_fields()
        return all(code in supported for code in field_codes if code)

    def _supported_custom_fields(self, fields: Dict[str, Any]) -> Dict[str, Any]:
        supported = self._contact_fields()
        result: Dict[str, Any] = {}
        for key, value in fields.items():
            if key in supported:
                result[key] = value
            logical_key = self.field_name_to_logical.get(key)
            if not logical_key:
                continue
            for alias_key in self._field_targets(logical_key):
                if alias_key in supported:
                    result[alias_key] = value
        return result

    @staticmethod
    def _dedupe_contacts(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen: set[str] = set()
        result: List[Dict[str, Any]] = []
        for item in items:
            item_id = str(item.get("ID") or "")
            if not item_id or item_id in seen:
                continue
            seen.add(item_id)
            result.append(item)
        return result


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
    if payload.comment.strip():
        lines.append(payload.comment.strip())
    return "\n".join(lines)


def calculate_customer_state(context: CustomerContext) -> str:
    if context.approval_status == "rejected":
        return "rejected"
    if context.card_status in {"archived", "blocked"}:
        return "archived"
    if context.card_status == "active" and context.allowed_price_type == "wholesale":
        return "approved_wholesale"
    if context.approval_status in {"pending_review", "new"}:
        return "pending_review"
    return "registration_submitted"


def current_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
