from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..config import AppConfig, EntityConfig


class Bitrix24UnavailableError(RuntimeError):
    pass


class Bitrix24Client:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def fetch_all_items(self, entity: EntityConfig) -> List[Dict[str, Any]]:
        return self.fetch_items(entity, stage_id=entity.active_stage_id)

    def fetch_items(
        self,
        entity: EntityConfig,
        stage_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        start = 0
        while True:
            params: Dict[str, Any] = {
                "entityTypeId": entity.entity_type_id,
                "filter[categoryId]": entity.category_id,
                "start": start,
            }
            if stage_id:
                params["filter[stageId]"] = stage_id
            data = self._call(
                "crm.item.list",
                params,
            )
            chunk = data.get("result", {}).get("items", [])
            items.extend(chunk)
            next_start = data.get("next")
            if next_start is None:
                break
            start = int(next_start)
        return items

    def list_contacts(
        self,
        filters: Dict[str, Any],
        select: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        return self._fetch_paginated("crm.contact.list", filters, select)

    def list_companies(
        self,
        filters: Dict[str, Any],
        select: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        return self._fetch_paginated("crm.company.list", filters, select)

    def create_contact(self, fields: Dict[str, Any]) -> int:
        data = self._call("crm.contact.add", _flatten_fields(fields))
        return int(data["result"])

    def update_contact(self, contact_id: int, fields: Dict[str, Any]) -> bool:
        data = self._call("crm.contact.update", {"id": contact_id, **_flatten_fields(fields)})
        return bool(data["result"])

    def create_company(self, fields: Dict[str, Any]) -> int:
        data = self._call("crm.company.add", _flatten_fields(fields))
        return int(data["result"])

    def update_company(self, company_id: int, fields: Dict[str, Any]) -> bool:
        data = self._call("crm.company.update", {"id": company_id, **_flatten_fields(fields)})
        return bool(data["result"])

    def create_lead(self, fields: Dict[str, Any]) -> int:
        data = self._call("crm.lead.add", _flatten_fields(fields))
        return int(data["result"])

    def create_deal(self, fields: Dict[str, Any]) -> int:
        data = self._call("crm.deal.add", _flatten_fields(fields))
        return int(data["result"])

    def _fetch_paginated(
        self,
        method: str,
        filters: Dict[str, Any],
        select: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        start = 0
        while True:
            params: Dict[str, Any] = {"start": start}
            for key, value in filters.items():
                params[f"filter[{key}]"] = value
            if select:
                for index, field_name in enumerate(select):
                    params[f"select[{index}]"] = field_name
            data = self._call(method, params)
            chunk = data.get("result", [])
            if isinstance(chunk, dict):
                chunk = chunk.get("items", [])
            items.extend(chunk)
            next_start = data.get("next")
            if next_start is None:
                break
            start = int(next_start)
        return items

    def _call(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if not self.config.bitrix_enabled or not self.config.bitrix_webhook:
            raise RuntimeError("BITRIX24_WEBHOOK is not configured")
        url = f"{self.config.bitrix_webhook}{method}.json"
        encoded = urlencode(params, doseq=True).encode("utf-8")
        request = Request(
            url,
            data=encoded,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
            },
        )
        try:
            with urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code in {429, 500, 502, 503, 504}:
                raise Bitrix24UnavailableError(
                    f"Bitrix24 временно недоступен ({exc.code}) во время {method}"
                ) from exc
            error_body = ""
            try:
                error_body = exc.read().decode("utf-8")
            except Exception:
                error_body = ""
            raise RuntimeError(
                f"Bitrix24 request failed ({exc.code}) during {method}: {error_body or exc.reason}"
            ) from exc
        except URLError as exc:
            raise Bitrix24UnavailableError(
                f"Bitrix24 недоступен во время {method}: {exc.reason}"
            ) from exc


def _flatten_fields(fields: Dict[str, Any]) -> Dict[str, Any]:
    params: Dict[str, Any] = {}
    for key, value in fields.items():
        _flatten_value(params, f"fields[{key}]", value)
    return params


def _flatten_value(target: Dict[str, Any], prefix: str, value: Any) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            _flatten_value(target, f"{prefix}[{key}]", nested)
        return
    if isinstance(value, list):
        for index, nested in enumerate(value):
            _flatten_value(target, f"{prefix}[{index}]", nested)
        return
    target[prefix] = value
