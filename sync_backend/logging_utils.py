from __future__ import annotations

import json
import logging
from typing import Iterable

from .models import SyncError, SyncStats


def configure_logging() -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    return logging.getLogger("telegram_sync")


def log_stats(logger: logging.Logger, stats: SyncStats) -> None:
    logger.info(
        "sync_stats popular_fetched=%s promotions_fetched=%s popular_after_filter=%s promotions_after_filter=%s popular_after_dedupe=%s promotions_after_dedupe=%s joined_products=%s skipped_items=%s",
        stats.popular_fetched,
        stats.promotions_fetched,
        stats.popular_after_filter,
        stats.promotions_after_filter,
        stats.popular_after_dedupe,
        stats.promotions_after_dedupe,
        stats.joined_products,
        stats.skipped_items,
    )


def log_errors(logger: logging.Logger, errors: Iterable[SyncError]) -> None:
    for err in errors:
        logger.warning(
            "sync_error code=%s xml_id=%s message=%s payload=%s",
            err.code,
            err.xml_id,
            err.message,
            json.dumps(err.payload, ensure_ascii=False) if err.payload else "{}",
        )
