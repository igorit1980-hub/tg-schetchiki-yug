from __future__ import annotations

import json
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from sync_backend.clients.bitrix24 import Bitrix24Client
from sync_backend.clients.site_catalog import SiteCatalogClient
from sync_backend.config import load_config
from sync_backend.logging_utils import configure_logging, log_errors, log_stats
from sync_backend.services.builder import build_storefront
from sync_backend.services.publisher import publish_json


def run() -> int:
    logger = configure_logging()
    config = load_config()

    logger.info("sync_started output_path=%s", config.output_path)

    bitrix_client = Bitrix24Client(config)
    site_client = SiteCatalogClient(config)

    try:
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

    log_stats(logger, result.stats)
    log_errors(logger, result.errors)

    try:
        publish_json(result.storefront, config.output_path)
    except Exception as exc:
        logger.exception("sync_failed reason=JSON_PUBLISH_ERROR error=%s", exc)
        return 1

    logger.info(
        "sync_completed output_path=%s popular_count=%s promotion_count=%s",
        config.output_path,
        len(result.storefront["popular_products"]),
        len(result.storefront["promotions"]),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
