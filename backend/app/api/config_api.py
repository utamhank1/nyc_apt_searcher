import json

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter(tags=["config"])


class SearchConfig(BaseModel):
    boroughs: list[str] | None = None
    neighborhoods: list[str] | None = None
    max_price: int | None = None
    min_price: int | None = None
    min_beds: int | None = None
    min_baths: int | None = None
    must_have_amenities: list[str] | None = None
    preferred_amenities: list[str] | None = None
    work_address: str | None = None
    lead_score_threshold: int | None = None
    sources_enabled: dict[str, bool] | None = None
    search_partner_emails: list[str] | None = None
    user_name: str | None = None
    user_email: str | None = None
    user_phone: str | None = None
    use_custom_email_template: bool | None = None
    custom_email_subject: str | None = None
    custom_email_body: str | None = None


@router.get("/config")
async def get_config():
    return {
        "boroughs": settings.boroughs_list,
        "neighborhoods": settings.neighborhoods_list,
        "max_price": settings.max_price,
        "min_price": settings.min_price,
        "min_beds": settings.min_beds,
        "min_baths": settings.min_baths,
        "must_have_amenities": settings.must_have_amenities_list,
        "preferred_amenities": settings.preferred_amenities_list,
        "work_address": settings.work_address,
        "lead_score_threshold": settings.lead_score_threshold,
        "sources_enabled": settings.sources_enabled_dict,
        "search_partner_emails": settings.search_partner_emails_list,
        "user_name": settings.user_name,
        "user_email": settings.user_email,
        "user_phone": settings.user_phone,
        "use_custom_email_template": settings.use_custom_email_template,
        "custom_email_subject": settings.custom_email_subject,
        "custom_email_body": settings.custom_email_body,
    }


@router.put("/config")
async def update_config(config: SearchConfig):
    updated = {}
    if config.boroughs is not None:
        settings.boroughs = json.dumps(config.boroughs)
        updated["boroughs"] = config.boroughs
    if config.neighborhoods is not None:
        settings.neighborhoods = json.dumps(config.neighborhoods)
        updated["neighborhoods"] = config.neighborhoods
    if config.max_price is not None:
        settings.max_price = config.max_price
        updated["max_price"] = config.max_price
    if config.min_price is not None:
        settings.min_price = config.min_price
        updated["min_price"] = config.min_price
    if config.min_beds is not None:
        settings.min_beds = config.min_beds
        updated["min_beds"] = config.min_beds
    if config.min_baths is not None:
        settings.min_baths = config.min_baths
        updated["min_baths"] = config.min_baths
    if config.must_have_amenities is not None:
        settings.must_have_amenities = json.dumps(config.must_have_amenities)
        updated["must_have_amenities"] = config.must_have_amenities
    if config.preferred_amenities is not None:
        settings.preferred_amenities = json.dumps(config.preferred_amenities)
        updated["preferred_amenities"] = config.preferred_amenities
    if config.work_address is not None:
        settings.work_address = config.work_address
        updated["work_address"] = config.work_address
    if config.lead_score_threshold is not None:
        settings.lead_score_threshold = config.lead_score_threshold
        updated["lead_score_threshold"] = config.lead_score_threshold
    if config.sources_enabled is not None:
        settings.sources_enabled = json.dumps(config.sources_enabled)
        updated["sources_enabled"] = config.sources_enabled
    if config.search_partner_emails is not None:
        emails = config.search_partner_emails[:3]
        settings.search_partner_emails = json.dumps(emails)
        updated["search_partner_emails"] = emails
    if config.user_name is not None:
        settings.user_name = config.user_name
        updated["user_name"] = config.user_name
    if config.user_email is not None:
        settings.user_email = config.user_email
        updated["user_email"] = config.user_email
    if config.user_phone is not None:
        settings.user_phone = config.user_phone
        updated["user_phone"] = config.user_phone
    if config.use_custom_email_template is not None:
        settings.use_custom_email_template = config.use_custom_email_template
        updated["use_custom_email_template"] = config.use_custom_email_template
    if config.custom_email_subject is not None:
        settings.custom_email_subject = config.custom_email_subject
        updated["custom_email_subject"] = config.custom_email_subject
    if config.custom_email_body is not None:
        settings.custom_email_body = config.custom_email_body
        updated["custom_email_body"] = config.custom_email_body

    return {"ok": True, "updated": updated}
