from __future__ import annotations

import json
import logging
from typing import Any, Dict
from urllib.error import URLError
from urllib.request import urlopen

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from telegram_bot.config import load_bot_config


logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
LOGGER = logging.getLogger("schetchiki_yug_bot")

CALLBACK_PROMOTIONS = "promotions"
CALLBACK_BESTSELLERS = "bestsellers"
CALLBACK_WHOLESALE = "wholesale"
CALLBACK_HELP = "help"


def _main_keyboard(config) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text="Открыть Mini App",
                    web_app=WebAppInfo(url=config.miniapp_url),
                )
            ],
            [
                InlineKeyboardButton(text="Акции", callback_data=CALLBACK_PROMOTIONS),
                InlineKeyboardButton(text="Хиты", callback_data=CALLBACK_BESTSELLERS),
            ],
            [
                InlineKeyboardButton(text="Опт", callback_data=CALLBACK_WHOLESALE),
                InlineKeyboardButton(text="Помощь", callback_data=CALLBACK_HELP),
            ],
            [
                InlineKeyboardButton(text="Канал", url=config.channel_url),
                InlineKeyboardButton(text="Менеджер", url=f"https://t.me/{config.manager_username}"),
            ],
        ]
    )


def _fetch_storefront_summary(config) -> Dict[str, Any]:
    url = f"{config.backend_base_url}/api/telegram/storefront"
    try:
        with urlopen(url, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, ValueError) as exc:
        LOGGER.warning("storefront_fetch_failed url=%s error=%s", url, exc)
        return {}


def _welcome_text(config) -> str:
    storefront = _fetch_storefront_summary(config)
    popular_count = len(storefront.get("popular_products") or [])
    promotions_count = len(storefront.get("promotions") or [])
    fallback_mode = (storefront.get("fallback_mode") or {}).get("active")

    lines = [
        "Добро пожаловать в каталог «Счетчики Юг».",
        "",
        "Здесь можно быстро открыть Mini App, посмотреть акции, перейти к хитовому ассортименту и связаться с менеджером.",
    ]
    if popular_count or promotions_count:
        lines.extend(
            [
                "",
                f"Сейчас в витрине: {popular_count} хитов и {promotions_count} акций.",
            ]
        )
        if fallback_mode:
            lines.append("Сейчас включен временный fallback-режим витрины.")
    lines.extend(
        [
            "",
            "Выберите нужный раздел ниже.",
        ]
    )
    return "\n".join(lines)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = context.application.bot_data["config"]
    await update.effective_chat.send_message(
        text=_welcome_text(config),
        reply_markup=_main_keyboard(config),
    )


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start(update, context)


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    config = context.application.bot_data["config"]

    if query.data == CALLBACK_PROMOTIONS:
        await query.message.reply_text(
            "\n".join(
                [
                    "🔥 Акции",
                    "",
                    "Здесь собраны актуальные предложения и промо-позиции.",
                    "Для цены, резерва или быстрого расчета напишите менеджеру.",
                ]
            ),
            reply_markup=_main_keyboard(config),
        )
        return

    if query.data == CALLBACK_BESTSELLERS:
        await query.message.reply_text(
            "\n".join(
                [
                    "⭐ Хиты продаж",
                    "",
                    "Показываем востребованные позиции для монтажников, УК и объектов.",
                    "Полный список и карточки товаров открываются в Mini App.",
                ]
            ),
            reply_markup=_main_keyboard(config),
        )
        return

    if query.data == CALLBACK_WHOLESALE:
        await query.message.reply_text(
            "\n".join(
                [
                    "📦 Оптовый заказ",
                    "",
                    "Подготовим подбор, расчет и комплектацию под объект.",
                    f"Для расчета и условий опта напишите менеджеру: @{config.manager_username}",
                ]
            ),
            reply_markup=_main_keyboard(config),
        )
        return

    await query.message.reply_text(
        "\n".join(
            [
                "📘 Как пользоваться",
                "",
                "1. Нажмите «Открыть Mini App».",
                "2. Перейдите в нужный раздел каталога.",
                "3. Для наличия, цены или расчета напишите менеджеру.",
            ]
        ),
        reply_markup=_main_keyboard(config),
    )


def run() -> int:
    config = load_bot_config()
    if not config.token:
        raise SystemExit(
            "TELEGRAM_BOT_TOKEN is not configured. Add it to .env before starting the bot."
        )

    application = Application.builder().token(config.token).build()
    application.bot_data["config"] = config
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", menu))
    application.add_handler(CallbackQueryHandler(on_callback))
    LOGGER.info("telegram_bot_started channel=%s miniapp=%s", config.channel_url, config.miniapp_url)
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
