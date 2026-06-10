import json
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _safe_json_list(val: str) -> list:
    """Parse a JSON list string, handling Railway's env var quoting quirks."""
    if not val or val.strip() == "":
        return []
    val = val.strip()
    try:
        result = json.loads(val)
        return result if isinstance(result, list) else []
    except json.JSONDecodeError:
        # Fallback: try comma-separated values
        return [v.strip().strip('"').strip("'") for v in val.split(",") if v.strip()]


def _safe_json_dict(val: str) -> dict:
    """Parse a JSON dict string, handling Railway's env var quoting quirks."""
    if not val or val.strip() == "":
        return {}
    val = val.strip()
    try:
        result = json.loads(val)
        return result if isinstance(result, dict) else {}
    except json.JSONDecodeError:
        return {}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    database_url: str = "sqlite+aiosqlite:///./apt_searcher.db"

    # API auth
    api_key: str = "change-me-in-production"

    # Search criteria (defaults, overridden via Settings UI / PUT /config)
    boroughs: str = '["Manhattan","Brooklyn"]'
    neighborhoods: str = '["East Village","West Village","Lower East Side","Williamsburg","Greenpoint"]'
    max_price: int = 3000
    min_price: int = 0
    min_beds: int = 1
    min_baths: int = 1
    must_have_amenities: str = '[]'
    preferred_amenities: str = '[]'
    work_address: str = ""
    lead_score_threshold: int = 70
    sources_enabled: str = '{"streeteasy": true, "zillow": true}'

    # Move-in date filter
    move_in_mode: str = ""  # "", "immediately", "date", "range"
    move_in_date: str = ""  # ISO date for "date" mode
    move_in_range_start: str = ""  # ISO date for "range" mode
    move_in_range_end: str = ""
    move_in_only: bool = False  # hard filter toggle

    # Search partners (up to 3)
    search_partner_emails: str = '[]'

    # User info (for broker emails)
    user_name: str = ""
    user_email: str = ""
    user_phone: str = ""

    # Custom email template
    use_custom_email_template: bool = False
    custom_email_subject: str = "Inquiry about {{address}} - {{source}}"
    custom_email_body: str = (
        "Hi {{broker_name}},\n\n"
        "I came across your listing at {{address}} "
        "({{beds}}BR/{{baths}}BA, {{price}}/mo) and "
        "I'm very interested in scheduling a viewing.\n\n"
        "Could you share available times this week?\n\n"
        "Best regards,\n"
        "{{your_name}}\n"
        "{{your_phone}}"
    )

    # Resend (email)
    resend_api_key: str = ""
    resend_from_email: str = "alerts@yourdomain.com"
    alert_to_email: str = ""

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Google Maps
    google_maps_api_key: str = ""

    # Scraper settings
    scrape_interval_hours: int = 6

    @property
    def boroughs_list(self) -> list[str]:
        return _safe_json_list(self.boroughs)

    @property
    def neighborhoods_list(self) -> list[str]:
        return _safe_json_list(self.neighborhoods)

    @property
    def must_have_amenities_list(self) -> list[str]:
        return _safe_json_list(self.must_have_amenities)

    @property
    def preferred_amenities_list(self) -> list[str]:
        return _safe_json_list(self.preferred_amenities)

    @property
    def sources_enabled_dict(self) -> dict[str, bool]:
        return _safe_json_dict(self.sources_enabled)

    @property
    def search_partner_emails_list(self) -> list[str]:
        return _safe_json_list(self.search_partner_emails)


settings = Settings()
