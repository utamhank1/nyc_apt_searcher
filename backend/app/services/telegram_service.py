import structlog
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

from app.core.config import settings

logger = structlog.get_logger()

_bot: Bot | None = None


async def create_telegram_bot() -> Bot | None:
    """Create a simple outbound-only Telegram bot. No polling."""
    global _bot
    if not settings.telegram_bot_token:
        return None

    _bot = Bot(token=settings.telegram_bot_token)
    logger.info("Telegram bot ready (outbound only)")
    return _bot


async def send_telegram_alert(listing: dict) -> bool:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.warning("Telegram not configured, skipping alert")
        return False

    global _bot
    if not _bot:
        _bot = Bot(token=settings.telegram_bot_token)

    commute = f"🚇 {listing['commute_minutes']} min commute\n" if listing.get("commute_minutes") else ""
    avail = listing.get("available_date")
    available = f"📅 Available: {'Immediately' if avail and avail.lower() in ('immediately', 'now') else avail}\n" if avail else ""
    amenities = ", ".join(listing.get("amenities", [])[:5])
    amenities_line = f"✅ {amenities}\n" if amenities else ""
    score = listing.get("match_score", 0)
    sqft = f" · {listing['sqft']:,} sqft" if listing.get("sqft") else ""

    search = listing.get("search_name")
    search_line = f"🔎 Search: {search}\n" if search else ""

    message = (
        f"🔥 *Hot apartment lead!*\n\n"
        f"{search_line}"
        f"📍 {listing.get('address', 'Address unavailable')}\n"
        f"   {listing.get('neighborhood', '')}, {listing.get('borough', '')}\n"
        f"💰 ${listing.get('price', '?'):,}/mo · {listing.get('beds', '?')}BR/{listing.get('baths', '?')}BA{sqft}\n"
        f"{commute}"
        f"{available}"
        f"{amenities_line}"
        f"⭐ Score: {score}/100\n\n"
        f"[View Listing →]({listing.get('url', '#')})\n\n"
        f"Would you like to tour it?"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Tour it!", url=listing.get("url", "#")),
            InlineKeyboardButton("❌ Pass", url=listing.get("url", "#")),
        ]
    ])

    try:
        await _bot.send_message(
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
