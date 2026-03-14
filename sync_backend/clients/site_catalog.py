from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import quote
from urllib.request import Request, urlopen

from ..config import AppConfig


def _walk_catalog(nodes: Iterable[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
    for node in nodes:
        for product in node.get("products", []) or []:
            yield product
        subs = node.get("subs", []) or []
        if subs:
            yield from _walk_catalog(subs)


class SiteCatalogClient:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._fallback_index = self._build_fallback_index(config.local_catalog_path)

    def _build_fallback_index(self, path: Path) -> Dict[str, Dict[str, Any]]:
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        index: Dict[str, Dict[str, Any]] = {}
        for product in _walk_catalog(data):
            xml_id = product.get("xml_id") or product.get("xmlId") or product.get("code")
            if not xml_id:
                continue
            index[str(xml_id)] = {
                "xml_id": str(xml_id),
                "name": product.get("name"),
                "price": _to_number(product.get("retail")),
                "old_price": None,
                "promo_price": None,
                "stock": _to_number(product.get("quantity")),
                "url": product.get("url"),
                "image": product.get("image"),
                "sku": product.get("sku"),
                "category": product.get("category"),
                "active": True,
            }
        return index

    def lookup(self, xml_id: str) -> Optional[Dict[str, Any]]:
        http_item = self._lookup_http(xml_id)
        if http_item:
            return http_item
        return self._fallback_index.get(xml_id)

    def _lookup_http(self, xml_id: str) -> Optional[Dict[str, Any]]:
        url = self.config.site_lookup_url.replace("{xmlId}", quote(xml_id)).replace("{xml_id}", quote(xml_id))
        try:
            request = Request(url, headers={"Accept": "application/json"})
            with urlopen(request, timeout=20) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception:
            return None
        if not data.get("found"):
            return None
        return data.get("item")


def _to_number(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None
