from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import quote
from urllib.request import Request, urlopen

from ..config import AppConfig


def _walk_catalog(nodes: Iterable[Dict[str, Any]], category_path: Optional[List[str]] = None) -> Iterable[Dict[str, Any]]:
    category_path = list(category_path or [])
    for node in nodes:
        next_path = category_path + [node.get("title", "")]
        for product in node.get("products", []) or []:
            enriched = dict(product)
            enriched["_category_path"] = [part for part in next_path if part]
            yield enriched
        subs = node.get("subs", []) or []
        if subs:
            yield from _walk_catalog(subs, next_path)


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
            xml_id = product.get("xml_id") or product.get("xmlId") or product.get("code") or product.get("id")
            product_id = product.get("id")
            if not xml_id and not product_id:
                continue
            retail_price = _to_number(product.get("retail") or product.get("price"))
            wholesale_price = _to_number(product.get("wholesale"))
            category = " / ".join(product.get("_category_path") or []) or None
            fallback_id = str(xml_id or product_id)
            item = {
                "xml_id": str(xml_id or product_id),
                "name": product.get("name"),
                "price": retail_price,
                "old_price": retail_price if wholesale_price is not None and retail_price is not None and wholesale_price < retail_price else None,
                "promo_price": wholesale_price if wholesale_price is not None and retail_price is not None and wholesale_price < retail_price else None,
                "stock": _to_number(product.get("quantity")),
                "url": product.get("url") or self._fallback_url(product_id or fallback_id, product.get("name")),
                "image": product.get("image"),
                "sku": product.get("sku") or str(product_id) if product_id else None,
                "category": product.get("category") or category,
                "active": (product.get("available") or "Y") == "Y",
            }
            index[str(fallback_id)] = item
            if product_id is not None:
                index[str(product_id)] = item
        return index

    def _fallback_url(self, product_id: str, product_name: Any) -> str:
        base = self.config.site_lookup_url.split("/api/", 1)[0].rstrip("/")
        slug = quote(str(product_name or product_id))
        return f"{base}/search/?q={slug}&product_id={quote(str(product_id))}"

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
