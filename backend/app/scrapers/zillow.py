import json
import re

import httpx
import structlog

from app.scrapers.base import BaseScraper
from app.scrapers.models import RawListing

logger = structlog.get_logger()

ZILLOW_GRAPHQL_URL = "https://www.zillow.com/async-create-search-page-state"

BOROUGH_REGION_IDS = {
    "Manhattan": "270915",
    "Brooklyn": "37607",
    "Queens": "270908",
    "Bronx": "17182",
    "Staten Island": "27252",
}


class ZillowScraper(BaseScraper):
    @property
    def source_name(self) -> str:
        return "zillow"

    async def scrape(self, criteria: dict) -> list[RawListing]:
        # Try the search results page approach with Playwright
        listings = await self._scrape_with_playwright(criteria)
        if listings:
            return listings

        logger.warning("Playwright scrape returned no results, site may have blocked us")
        return []

    async def _scrape_with_playwright(self, criteria: dict) -> list[RawListing]:
        listings = []
        context = None
        try:
            context = await self.new_context()
            page = await context.new_page()

            # Go to zillow homepage first
            if not await self.safe_goto(page, "https://www.zillow.com"):
                logger.error("Failed to load Zillow homepage")
                return []

            # Build search URL
            search_url = self._build_search_url(criteria)
            logger.info("Scraping Zillow", url=search_url)

            if not await self.safe_goto(page, search_url, wait_until="networkidle"):
                logger.error("Failed to load Zillow search", url=search_url)
                return []

            await page.wait_for_timeout(5000)

            # Try to find listing cards
            card_selectors = [
                "[data-test='property-card']",
                "article[data-test='property-card']",
                "[class*='ListItem']",
                "[class*='property-card']",
                "#grid-search-results li article",
                ".list-card",
            ]

            cards = []
            for selector in card_selectors:
                cards = await page.query_selector_all(selector)
                if cards:
                    logger.info(f"Found {len(cards)} Zillow cards with: {selector}")
                    break

            if not cards:
                # Try extracting from page's __NEXT_DATA__ or inline JSON
                listings = await self._extract_from_page_data(page)
                if listings:
                    return listings
                logger.warning("No Zillow listing cards found")
                return []

            for card in cards[:20]:
                try:
                    listing = await self._parse_card(card)
                    if listing:
                        listings.append(listing)
                except Exception as e:
                    logger.debug("Failed to parse Zillow card", error=str(e))

        except Exception as e:
            logger.error("Zillow scraper error", error=str(e))
        finally:
            if context:
                await context.close()

        logger.info(f"Scraped {len(listings)} listings from Zillow")
        return listings

    def _build_search_url(self, criteria: dict) -> str:
        base = "https://www.zillow.com/new-york-ny/rentals/"
        params = []

        if criteria.get("min_beds"):
            params.append(f"{criteria['min_beds']}-bedrooms")

        price_parts = []
        if criteria.get("min_price"):
            price_parts.append(str(criteria["min_price"]))
        if criteria.get("max_price"):
            if not price_parts:
                price_parts.append("0")
            price_parts.append(str(criteria["max_price"]))

        url = base
        if params:
            url += "/".join(params) + "/"

        filter_params = []
        if criteria.get("max_price"):
            filter_params.append(f"price-{criteria.get('min_price', 0)}-{criteria['max_price']}")

        if filter_params:
            url += "?" + "&".join(filter_params)

        return url

    async def _extract_from_page_data(self, page) -> list[RawListing]:
        """Try to extract listing data from Zillow's embedded JSON/script tags."""
        listings = []
        try:
            scripts = await page.query_selector_all("script[type='application/json']")
            for script in scripts:
                text = await script.inner_text()
                if "listResults" in text or "searchResults" in text:
                    data = json.loads(text)
                    results = self._find_results_in_json(data)
                    for r in results:
                        listing = self._json_to_raw_listing(r)
                        if listing:
                            listings.append(listing)
                    if listings:
                        return listings

            # Also try __NEXT_DATA__
            next_data = await page.query_selector("script#__NEXT_DATA__")
            if next_data:
                text = await next_data.inner_text()
                data = json.loads(text)
                results = self._find_results_in_json(data)
                for r in results:
                    listing = self._json_to_raw_listing(r)
                    if listing:
                        listings.append(listing)
        except Exception as e:
            logger.debug("Failed to extract from page data", error=str(e))

        return listings

    def _find_results_in_json(self, data, depth=0) -> list[dict]:
        if depth > 10:
            return []
        if isinstance(data, dict):
            if "listResults" in data:
                return data["listResults"]
            if "searchResults" in data and "listResults" in data["searchResults"]:
                return data["searchResults"]["listResults"]
            for v in data.values():
                results = self._find_results_in_json(v, depth + 1)
                if results:
                    return results
        if isinstance(data, list):
            for item in data:
                results = self._find_results_in_json(item, depth + 1)
                if results:
                    return results
        return []

    def _json_to_raw_listing(self, data: dict) -> RawListing | None:
        try:
            zpid = str(data.get("zpid") or data.get("id", ""))
            if not zpid:
                return None

            url = data.get("detailUrl", "")
            if url and not url.startswith("http"):
                url = f"https://www.zillow.com{url}"

            price = data.get("unformattedPrice") or data.get("price")
            if isinstance(price, str):
                price_match = re.search(r"[\d,]+", price)
                price = int(price_match.group().replace(",", "")) if price_match else None

            address_data = data.get("address") or data.get("addressStreet") or ""
            if isinstance(address_data, dict):
                address = f"{address_data.get('streetAddress', '')}, {address_data.get('city', '')}"
            else:
                address = str(address_data)

            beds = data.get("beds")
            baths = data.get("baths")
            sqft_raw = data.get("area") or data.get("livingArea")
            sqft = int(sqft_raw) if sqft_raw else None

            return RawListing(
                source="zillow",
                source_id=zpid,
                url=url,
                title=address or f"Zillow #{zpid}",
                price=price,
                beds=int(beds) if beds else None,
                baths=float(baths) if baths else None,
                sqft=sqft,
                address=address,
            )
        except Exception as e:
            logger.debug("Failed to parse Zillow JSON listing", error=str(e))
            return None

    async def _parse_card(self, card) -> RawListing | None:
        try:
            link = await card.query_selector("a[href*='/homedetails/'], a[href*='/b/']")
            if not link:
                link = await card.query_selector("a")
            if not link:
                return None

            href = await link.get_attribute("href")
            if not href:
                return None
            url = f"https://www.zillow.com{href}" if href.startswith("/") else href

            zpid_match = re.search(r"/(\d+)_zpid", href)
            source_id = zpid_match.group(1) if zpid_match else href

            price = None
            price_el = await card.query_selector("[data-test='property-card-price'], [class*='price']")
            if price_el:
                price_text = await price_el.inner_text()
                price_match = re.search(r"\$?([\d,]+)", price_text)
                if price_match:
                    price = int(price_match.group(1).replace(",", ""))

            address = None
            addr_el = await card.query_selector("address, [data-test='property-card-addr']")
            if addr_el:
                address = (await addr_el.inner_text()).strip()

            beds, baths, sqft = None, None, None
            details = await card.query_selector("[class*='details'], [class*='property-card-data']")
            if details:
                text = await details.inner_text()
                beds_match = re.search(r"(\d+)\s*(?:bd|bed|br)", text, re.I)
                baths_match = re.search(r"([\d.]+)\s*(?:ba|bath)", text, re.I)
                sqft_match = re.search(r"([\d,]+)\s*(?:sqft|sq)", text, re.I)
                if beds_match:
                    beds = int(beds_match.group(1))
                if baths_match:
                    baths = float(baths_match.group(1))
                if sqft_match:
                    sqft = int(sqft_match.group(1).replace(",", ""))

            return RawListing(
                source="zillow",
                source_id=str(source_id),
                url=url,
                title=address or f"Zillow listing",
                price=price,
                beds=beds,
                baths=baths,
                sqft=sqft,
                address=address,
            )
        except Exception as e:
            logger.debug("Zillow card parse error", error=str(e))
            return None
