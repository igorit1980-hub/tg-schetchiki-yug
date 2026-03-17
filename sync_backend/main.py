from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from sync_backend.clients.bitrix24 import Bitrix24Client
from sync_backend.clients.site_catalog import SiteCatalogClient
from sync_backend.config import load_config
from sync_backend.logging_utils import configure_logging, log_errors, log_stats
from sync_backend.services.builder import build_storefront
from sync_backend.services.publisher import publish_json


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _entity_diagnostics(bitrix_client: Bitrix24Client, entity) -> dict:
    filtered_items = bitrix_client.fetch_all_items(entity)
    category_items = bitrix_client.fetch_items(entity, stage_id=None)
    stage_counts = Counter(str(item.get("stageId") or "EMPTY_STAGE") for item in category_items)
    missing_xml = sum(1 for item in category_items if not item.get("xmlId"))
    missing_dates = sum(1 for item in category_items if not item.get("begindate") or not item.get("closedate"))
    samples = [
        {
            "id": item.get("id"),
            "title": item.get("title"),
            "xmlId": item.get("xmlId"),
            "stageId": item.get("stageId"),
            "begindate": item.get("begindate"),
            "closedate": item.get("closedate"),
            "updatedTime": item.get("updatedTime"),
        }
        for item in category_items[:5]
    ]
    return {
        "entity": entity.name,
        "entity_type_id": entity.entity_type_id,
        "category_id": entity.category_id,
        "active_stage_id": entity.active_stage_id,
        "active_stage_count": len(filtered_items),
        "category_total_count": len(category_items),
        "stage_counts": dict(sorted(stage_counts.items())),
        "missing_xml_id_count": missing_xml,
        "missing_date_range_count": missing_dates,
        "sample_items": samples,
    }


def _write_diagnostics(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _maybe_apply_empty_fallback(config, storefront: dict) -> tuple[dict, dict]:
    counts = {
        "popular_products": len(storefront.get("popular_products") or []),
        "promotions": len(storefront.get("promotions") or []),
    }
    fallback_meta = {
        "used": False,
        "reason": "",
        "path": str(config.empty_storefront_fallback_path),
    }
    if counts["popular_products"] > 0 or counts["promotions"] > 0:
        return storefront, fallback_meta
    if not config.empty_storefront_fallback_path.exists():
        fallback_meta["reason"] = "fallback_file_missing"
        return storefront, fallback_meta

    fallback_payload = _load_json(config.empty_storefront_fallback_path)
    fallback_counts = {
        "popular_products": len(fallback_payload.get("popular_products") or []),
        "promotions": len(fallback_payload.get("promotions") or []),
    }
    if fallback_counts["popular_products"] == 0 and fallback_counts["promotions"] == 0:
        fallback_meta["reason"] = "fallback_file_empty"
        return storefront, fallback_meta

    fallback_payload["fallback_mode"] = {
        "active": True,
        "source": str(config.empty_storefront_fallback_path),
        "reason": "smart_process_empty",
    }
    fallback_meta["used"] = True
    fallback_meta["reason"] = "smart_process_empty"
    return fallback_payload, fallback_meta


def run() -> int:
    logger = configure_logging()
    config = load_config()

    if not config.bitrix_enabled:
        logger.error("sync_failed reason=MISSING_BITRIX_WEBHOOK")
        return 1

    logger.info("sync_started output_path=%s", config.output_path)

    bitrix_client = Bitrix24Client(config)
    site_client = SiteCatalogClient(config)

    try:
        popular_diag = _entity_diagnostics(bitrix_client, config.popular_products)
        promotions_diag = _entity_diagnostics(bitrix_client, config.promotions)
        popular_items = bitrix_client.fetch_all_items(config.popular_products)
        promotion_items = bitrix_client.fetch_all_items(config.promotions)
    except Exception as exc:
        logger.exception("sync_failed reason=BITRIX_API_ERROR error=%s", exc)
        return 1

    result = build_storefront(
        config=config,
        popular_items=popular_items,
        promotion_items=promotion_items,
        site_lookup=site_client.lookup,
    )

    storefront_to_publish, fallback_meta = _maybe_apply_empty_fallback(config, result.storefront)

    log_stats(logger, result.stats)
    log_errors(logger, result.errors)

    diagnostics_payload = {
        "generated_at": result.storefront["generated_at"],
        "output_path": str(config.output_path),
        "entities": {
            "popular_products": popular_diag,
            "promotions": promotions_diag,
        },
        "storefront_counts": {
            "popular_products": len(storefront_to_publish["popular_products"]),
            "promotions": len(storefront_to_publish["promotions"]),
        },
        "fallback": fallback_meta,
        "error_codes": [err.code for err in result.errors],
    }

    logger.info(
        "bitrix_diagnostics popular_active=%s popular_total=%s promotions_active=%s promotions_total=%s diagnostics_path=%s",
        popular_diag["active_stage_count"],
        popular_diag["category_total_count"],
        promotions_diag["active_stage_count"],
        promotions_diag["category_total_count"],
        config.diagnostics_path,
    )
    logger.info(
        "storefront_fallback used=%s reason=%s path=%s",
        fallback_meta["used"],
        fallback_meta["reason"] or "none",
        fallback_meta["path"],
    )

    try:
        publish_json(storefront_to_publish, config.output_path)
        _write_diagnostics(config.diagnostics_path, diagnostics_payload)
    except Exception as exc:
        logger.exception("sync_failed reason=JSON_PUBLISH_ERROR error=%s", exc)
        return 1

    logger.info(
        "sync_completed output_path=%s popular_count=%s promotion_count=%s",
        config.output_path,
        len(storefront_to_publish["popular_products"]),
        len(storefront_to_publish["promotions"]),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
