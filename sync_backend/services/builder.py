from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..config import AppConfig
from ..models import SyncError, SyncResult, SyncStats


def build_storefront(
    config: AppConfig,
    popular_items: List[Dict[str, Any]],
    promotion_items: List[Dict[str, Any]],
    site_lookup,
) -> SyncResult:
    stats = SyncStats()
    errors: List[SyncError] = []
    now = datetime.now().astimezone()

    stats.popular_fetched = len(popular_items)
    stats.promotions_fetched = len(promotion_items)

    filtered_popular = _filter_items(popular_items, config.popular_products, now, errors, "popular")
    filtered_promotions = _filter_items(promotion_items, config.promotions, now, errors, "promotion")
    stats.popular_after_filter = len(filtered_popular)
    stats.promotions_after_filter = len(filtered_promotions)

    deduped_popular = _dedupe_by_xml_id(filtered_popular, errors)
    deduped_promotions = _dedupe_by_xml_id(filtered_promotions, errors)
    stats.popular_after_dedupe = len(deduped_popular)
    stats.promotions_after_dedupe = len(deduped_promotions)

    popular_products = []
    promotions = []

    for item in deduped_popular:
        enriched = _join_site_item(item, site_lookup, errors, require_promo=False)
        if not enriched:
            stats.skipped_items += 1
            continue
        stats.joined_products += 1
        popular_products.append(
            {
                "id": item["id"],
                "xml_id": item["xmlId"],
                "title": item["title"],
                "short_text": item.get("sourceDescription") or "",
                "date_from": item["begindate"],
                "date_to": item["closedate"],
                "manager_id": item.get("assignedById"),
                "updated_at": item["updatedTime"],
                "product_name": enriched["name"],
                "price": enriched["price"],
                "old_price": enriched.get("old_price"),
                "stock": enriched.get("stock"),
                "url": enriched["url"],
                "image": enriched.get("image"),
                "sku": enriched.get("sku"),
                "category": enriched.get("category"),
            }
        )

    for item in deduped_promotions:
        enriched = _join_site_item(item, site_lookup, errors, require_promo=True)
        if not enriched:
            stats.skipped_items += 1
            continue
        stats.joined_products += 1
        promotions.append(
            {
                "id": item["id"],
                "xml_id": item["xmlId"],
                "promo_title": item["title"],
                "promo_text": item.get("sourceDescription") or "",
                "date_from": item["begindate"],
                "date_to": item["closedate"],
                "manager_id": item.get("assignedById"),
                "updated_at": item["updatedTime"],
                "product_name": enriched["name"],
                "price": enriched["promo_price"],
                "old_price": enriched["old_price"],
                "stock": enriched.get("stock"),
                "url": enriched["url"],
                "image": enriched.get("image"),
                "sku": enriched.get("sku"),
                "category": enriched.get("category"),
            }
        )

    popular_products.sort(key=lambda item: (item["updated_at"], item["id"]), reverse=True)
    promotions.sort(key=lambda item: (item["updated_at"], item["id"]), reverse=True)

    storefront = {
        "generated_at": now.isoformat(),
        "timezone": config.timezone,
        "popular_products": popular_products,
        "promotions": promotions,
    }
    return SyncResult(storefront=storefront, stats=stats, errors=errors)


def _filter_items(items, entity_config, now, errors, label):
    result = []
    for item in items:
        xml_id = item.get("xmlId")
        if not xml_id:
            errors.append(SyncError(code="EMPTY_XML_ID", message=f"{label} item has empty xmlId", payload=item))
            continue
        if not item.get("begindate") or not item.get("closedate"):
            errors.append(SyncError(code="OUT_OF_DATE_RANGE", message=f"{label} item has empty date range", xml_id=xml_id, payload=item))
            continue
        date_from = _parse_datetime(item.get("begindate"))
        date_to = _parse_datetime(item.get("closedate"))
        if not date_from or not date_to or date_to < date_from:
            errors.append(SyncError(code="INVALID_DATE_RANGE", message=f"{label} item has invalid date range", xml_id=xml_id, payload=item))
            continue
        if not (date_from <= now <= date_to):
            errors.append(SyncError(code="OUT_OF_DATE_RANGE", message=f"{label} item is outside active date range", xml_id=xml_id, payload=item))
            continue
        result.append(item)
    return result


def _dedupe_by_xml_id(items, errors):
    deduped = {}
    for item in sorted(items, key=lambda row: (row.get("updatedTime") or "", row.get("id") or 0), reverse=True):
        xml_id = item["xmlId"]
        if xml_id in deduped:
            errors.append(SyncError(code="DUPLICATE_BITRIX_XML_ID", message="duplicate active Bitrix24 item by xmlId", xml_id=xml_id, payload=item))
            continue
        deduped[xml_id] = item
    return list(deduped.values())


def _join_site_item(item, site_lookup, errors, require_promo: bool):
    xml_id = item["xmlId"]
    site_item = site_lookup(xml_id)
    if not site_item:
        errors.append(SyncError(code="NOT_FOUND_ON_SITE_BY_XML_ID", message="site item not found by xml_id", xml_id=xml_id, payload=item))
        return None
    if not site_item.get("active", False):
        errors.append(SyncError(code="SITE_ITEM_INACTIVE", message="site item inactive", xml_id=xml_id, payload=site_item))
        return None
    if not site_item.get("name") or site_item.get("price") is None or not site_item.get("url"):
        errors.append(SyncError(code="MISSING_REQUIRED_SITE_FIELDS", message="site item missing required fields", xml_id=xml_id, payload=site_item))
        return None
    if require_promo:
        if site_item.get("promo_price") is None:
            errors.append(SyncError(code="MISSING_PROMO_PRICE", message="promotion missing promo_price", xml_id=xml_id, payload=site_item))
            return None
        if site_item.get("old_price") is None:
            errors.append(SyncError(code="MISSING_OLD_PRICE_FOR_PROMO", message="promotion missing old_price", xml_id=xml_id, payload=site_item))
            return None
        if float(site_item["old_price"]) <= float(site_item["promo_price"]):
            errors.append(SyncError(code="INVALID_PROMO_PRICE", message="promotion old_price must be greater than promo_price", xml_id=xml_id, payload=site_item))
            return None
    return site_item


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
