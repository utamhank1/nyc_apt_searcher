import re

import structlog
from playwright.async_api import Page

from app.scrapers.base import BaseScraper
from app.scrapers.models import RawListing

logger = structlog.get_logger()

NEIGHBORHOOD_SLUGS = {
    "East Village": "east-village",
    "West Village": "west-village",
    "Lower East Side": "lower-east-side",
    "Greenwich Village": "greenwich-village",
    "SoHo": "soho",
    "NoHo": "noho",
    "Tribeca": "tribeca",
    "Chelsea": "chelsea",
    "Hell's Kitchen": "hells-kitchen",
    "Midtown East": "midtown-east",
    "Midtown West": "midtown-west",
    "Murray Hill": "murray-hill",
    "Gramercy Park": "gramercy-park",
    "Flatiron": "flatiron",
    "Upper East Side": "upper-east-side",
    "Upper West Side": "upper-west-side",
    "Kips Bay": "kips-bay",
    "Financial District": "financial-district",
    "Harlem": "harlem",
    "East Harlem": "east-harlem",
    "Williamsburg": "williamsburg",
    "Greenpoint": "greenpoint",
    "Bushwick": "bushwick",
    "Bed-Stuy": "bed-stuy",
    "Crown Heights": "crown-heights",
    "Park Slope": "park-slope",
    "Cobble Hill": "cobble-hill",
    "DUMBO": "dumbo",
    "Downtown Brooklyn": "downtown-brooklyn",
    "Fort Greene": "fort-greene",
    "Prospect Heights": "prospect-heights",
    "Brooklyn Heights": "brooklyn-heights",
    "Boerum Hill": "boerum-hill",
    "Carroll Gardens": "carroll-gardens",
    "Astoria": "astoria",
    "Long Island City": "long-island-city",
}


class StreetEasyScraper(BaseScraper):
    @property
    def source_name(self) -> str:
        return "streeteasy"

    def _build_url(self, criteria: dict) -> str:
        parts = []
        if criteria.get("max_price"):
            parts.append(f"price:-{criteria['max_price']}")
        if criteria.get("min_price"):
            parts.append(f"price:{criteria['min_price']}-")
        if criteria.get("min_beds"):
            beds = criteria["min_beds"]
            parts.append(f"beds>={beds}")

        neighborhoods = criteria.get("neighborhoods", [])
        area_slugs = []
        for n in neighborhoods:
            slug = NEIGHBORHOOD_SLUGS.get(n)
            if slug:
                area_slugs.append(slug)

        if area_slugs:
            parts.append(f"area:{','.join(area_slugs)}")

        filter_str = "%7C".join(parts) if parts else ""
        base = "https://streeteasy.com/for-rent/nyc"
        return f"{base}/{filter_str}" if filter_str else base

    async def scrape(self, criteria: dict) -> list[RawListing]:
        listings = []
        context = None
        try:
            context = await self.new_context()
            page = await context.new_page()

            # Navigate to homepage first to appear more natural
            if not await self.safe_goto(page, "https://streeteasy.com"):
                logger.error("Failed to load StreetEasy homepage")
                return []

            search_url = self._build_url(criteria)
            logger.info("Scraping StreetEasy", url=search_url)

            if not await self.safe_goto(page, search_url):
                logger.error("Failed to load StreetEasy search", url=search_url)
                return []

            await page.wait_for_timeout(3000)

            # Try multiple selectors for listing cards
            card_selectors = [
                "[data-testid='listing-card']",
                ".listingCard",
                ".searchCardList--listItem",
                "article[class*='listing']",
                "[class*='SearchCardList'] > li",
            ]

            cards = []
            for selector in card_selectors:
                cards = await page.query_selector_all(selector)
                if cards:
                    logger.info(f"Found {len(cards)} cards with selector: {selector}")
                    break

            if not cards:
                logger.warning("No listing cards found on StreetEasy")
                content = await page.content()
                logger.debug("Page content length", length=len(content))
                return []

            for card in cards[:20]:
                try:
                    listing = await self._parse_card(card, page)
                    if listing:
                        listings.append(listing)
                except Exception as e:
                    logger.warning("Failed to parse StreetEasy card", error=str(e))

            logger.info(f"Scraped {len(listings)} listings from StreetEasy")

        except Exception as e:
            logger.error("StreetEasy scraper error", error=str(e))
        finally:
            if context:
                await context.close()

        return listings

    async def _parse_card(self, card, page: Page) -> RawListing | None:
        try:
            # Extract listing URL
            link = await card.query_selector("a[href*='/rental/']")
            if not link:
                link = await card.query_selector("a")
            if not link:
                return None

            href = await link.get_attribute("href")
            if not href:
                return None
            url = f"https://streeteasy.com{href}" if href.startswith("/") else href

            # Extract source_id from URL
            source_id_match = re.search(r"/(\d+)$", href)
            source_id = source_id_match.group(1) if source_id_match else href

            # Extract price
            price = None
            price_el = await card.query_selector("[class*='price'], [class*='Price']")
            if price_el:
                price_text = await price_el.inner_text()
                price_match = re.search(r"\$?([\d,]+)", price_text)
                if price_match:
                    price = int(price_match.group(1).replace(",", ""))

            # Extract address
            address = None
            addr_el = await card.query_selector("[class*='address'], [class*='Address']")
            if addr_el:
                address = (await addr_el.inner_text()).strip()

            # Extract details (beds, baths, sqft)
            beds, baths, sqft = None, None, None
            detail_el = await card.query_selector("[class*='detail'], [class*='Detail']")
            if detail_el:
                detail_text = await detail_el.inner_text()
                beds_match = re.search(r"(\d+)\s*(?:bed|br|bedroom)", detail_text, re.I)
                baths_match = re.search(r"([\d.]+)\s*(?:bath|ba)", detail_text, re.I)
                sqft_match = re.search(r"([\d,]+)\s*(?:sq\.?\s*ft|sqft|sf)", detail_text, re.I)
                if beds_match:
                    beds = int(beds_match.group(1))
                if baths_match:
                    baths = float(baths_match.group(1))
                if sqft_match:
                    sqft = int(sqft_match.group(1).replace(",", ""))

            # Extract neighborhood
            neighborhood = None
            area_el = await card.query_selector("[class*='neighborhood'], [class*='area']")
            if area_el:
                neighborhood = (await area_el.inner_text()).strip()

            # Get title from card text
            title_text = await card.inner_text()
            title = title_text.split("\n")[0][:200] if title_text else ""

            return RawListing(
                source="streeteasy",
                source_id=str(source_id),
                url=url,
                title=title,
                price=price,
                beds=beds,
                baths=baths,
                sqft=sqft,
                address=address,
                neighborhood=neighborhood,
            )
        except Exception as e:
            logger.debug("Card parse error", error=str(e))
            return None
