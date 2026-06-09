import structlog
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from app.core.config import settings

logger = structlog.get_logger()

_telegram_app: Application | None = None


async def create_telegram_app() -> Application | None:
    global _telegram_app
    if not settings.telegram_bot_token:
        return None

    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("start", _handle_start))
    app.add_handler(CallbackQueryHandler(_handle_callback))

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)

    _telegram_app = app
    return app


async def _handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        f"🏠 NYC Apartment Searcher connected!\n\n"
        f"Your chat ID: `{chat_id}`\n\n"
        f"Add this to your settings to receive alerts here.",
        parse_mode="Markdown",
    )


async def _handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if not data or "|" not in data:
        return

    action, listing_id_str = data.split("|", 1)

    try:
        listing_id = int(listing_id_str)
    except ValueError:
        return

    from app.core.database import async_session_factory
    from sqlalchemy import select
    from app.models.listing import Listing

    async with async_session_factory() as db:
        result = await db.execute(select(Listing).where(Listing.id == listing_id))
        listing = result.scalar_one_or_none()
        if not listing:
            await query.edit_message_reply_markup(reply_markup=None)
            return

        from app.services.lead_flow_service import process_yes_response, process_no_response
        if action == "tour":
            await process_yes_response(listing, db)
            await query.edit_message_text(
                query.message.text + "\n\n✅ Tour requested! Broker email sent.",
            )
        elif action == "pass":
            await process_no_response(listing, db)
            await query.edit_message_text(
                query.message.text + "\n\n❌ Passed on this one.",
            )


async def send_telegram_alert(listing: dict) -> bool:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.warning("Telegram not configured, skipping alert")
        return False

    global _telegram_app
    if not _telegram_app:
        return False

    commute = f"🚇 {listing['commute_minutes']} min commute\n" if listing.get("commute_minutes") else ""
    amenities = ", ".join(listing.get("amenities", [])[:5])
    amenities_line = f"✅ {amenities}\n" if amenities else ""
    score = listing.get("match_score", 0)
    sqft = f" · {listing['sqft']:,} sqft" if listing.get("sqft") else ""

    message = (
        f"🔥 *Hot apartment lead!*\n\n"
        f"📍 {listing.get('address', 'Address unavailable')}\n"
        f"   {listing.get('neighborhood', '')}, {listing.get('borough', '')}\n"
        f"💰 ${listing.get('price', '?'):,}/mo · {listing.get('beds', '?')}BR/{listing.get('baths', '?')}BA{sqft}\n"
        f"{commute}"
        f"{amenities_line}"
        f"⭐ Score: {score}/100\n\n"
        f"[View Listing →]({listing.get('url', '#')})\n\n"
        f"Would you like to tour it?"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Tour it!", callback_data=f"tour|{listing['id']}"),
            InlineKeyboardButton("❌ Pass", callback_data=f"pass|{listing['id']}"),
        ]
    ])

    try:
        await _telegram_app.bot.send_message(
            chat_id=settings.telegram_chat_id,
            text=message,
            parse_mode="Markdown",
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )
        logger.info("Telegram alert sent", listing_id=listing["id"])
        return True
    except Exception as e:
        logger.error("Failed to send Telegram alert", error=str(e))
        return False
