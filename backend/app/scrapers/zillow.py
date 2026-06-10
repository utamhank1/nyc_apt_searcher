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

    async def scrape_single_listing(self, url: str) -> RawListing | None:
        """Scrape a single Zillow listing detail page."""
        context = None
        try:
            context = await self.new_context()
            page = await context.new_page()

            if not await self.safe_goto(page, "https://www.zillow.com"):
                return None
            if not await self.safe_goto(page, url, wait_until="networkidle"):
                return None

            await page.wait_for_timeout(5000)

            # Try to extract from embedded JSON first
            data = {}
            next_data = await page.query_selector("script#__NEXT_DATA__")
            if next_data:
                try:
                    text = await next_data.inner_text()
                    parsed = json.loads(text)
                    data = self._find_property_in_json(parsed) or {}
                except Exception:
                    pass

            if not data:
                scripts = await page.query_selector_all("script[type='application/json']")
                for script in scripts:
                    try:
                        text = await script.inner_text()
                        if "zpid" in text or "bedrooms" in text:
                            parsed = json.loads(text)
                            data = self._find_property_in_json(parsed) or {}
                            if data:
                                break
                    except Exception:
                        continue

            zpid_match = re.search(r"/(\d+)_zpid", url)
            source_id = zpid_match.group(1) if zpid_match else url.split("/")[-1]

            price = data.get("price") or data.get("unformattedPrice")
            if isinstance(price, str):
                m = re.search(r"[\d,]+", price)
                price = int(m.group().replace(",", "")) if m else None

            address_data = data.get("address") or data.get("streetAddress") or ""
            if isinstance(address_data, dict):
                address = f"{address_data.get('streetAddress', '')}, {address_data.get('city', '')}"
            else:
                address = str(address_data) if address_data else None

            if not address:
                addr_el = await page.query_selector("h1, [data-testid='bdp-address']")
                if addr_el:
                    address = (await addr_el.inner_text()).strip()

            beds = data.get("bedrooms") or data.get("beds")
            baths = data.get("bathrooms") or data.get("baths")
            sqft = data.get("livingArea") or data.get("area")

            amenities = []
            for key in ("amenityFeatures", "amenities", "buildingAmenities", "unitAmenities"):
                raw_amenities = data.get(key, [])
                if isinstance(raw_amenities, list):
                    for a in raw_amenities:
                        if isinstance(a, str):
                            amenities.append(a)
                        elif isinstance(a, dict):
                            amenities.append(a.get("name", a.get("text", str(a))))

            broker_name = None
            broker_phone = None
            agent = data.get("attributionInfo") or data.get("listingAgent") or {}
            if isinstance(agent, dict):
                broker_name = agent.get("agentName") or agent.get("brokerName")
                broker_phone = agent.get("agentPhoneNumber") or agent.get("brokerPhoneNumber")

            open_house_dates = []
            for oh in data.get("openHouses", data.get("openHouseSchedule", [])):
                if isinstance(oh, dict):
                    open_house_dates.append({
                        "date": oh.get("date", oh.get("startDate", "")),
                        "start_time": oh.get("startTime", ""),
                        "end_time": oh.get("endTime", ""),
                    })

            available_date = data.get("dateAvailable") or data.get("availabilityDate")
            description = data.get("description") or data.get("homeDescription")

            if not price:
                price_el = await page.query_selector("[data-testid='price'], [class*='price']")
                if price_el:
                    text = await price_el.inner_text()
                    m = re.search(r"\$?([\d,]+)", text)
                    if m:
                        price = int(m.group(1).replace(",", ""))

            logger.info("Scraped single Zillow listing", source_id=source_id, price=price)
            return RawListing(
                source="zillow",
                source_id=str(source_id),
                url=url,
                title=address or f"Zillow #{source_id}",
                price=price,
                beds=int(beds) if beds else None,
                baths=float(baths) if baths else None,
                sqft=int(sqft) if sqft else None,
                address=address,
                amenities=amenities,
                broker_name=broker_name,
                broker_phone=broker_phone,
                description=description[:5000] if description else None,
                available_date=available_date,
                open_house_dates=open_house_dates,
            )
        except Exception as e:
            logger.error("Failed to scrape single Zillow listing", url=url, error=str(e))
            return None
        finally:
            if context:
                await context.close()

    def _find_property_in_json(self, data, depth=0) -> dict | None:
        """Find the property detail object in Zillow's nested JSON."""
        if depth > 10:
            return None
        if isinstance(data, dict):
            if "zpid" in data and ("price" in data or "bedrooms" in data or "address" in data):
                return data
            if "property" in data and isinstance(data["property"], dict):
                return data["property"]
            for v in data.values():
                result = self._find_property_in_json(v, depth + 1)
                if result:
                    return result
        if isinstance(data, list):
            for item in data:
                result = self._find_property_in_json(item, depth + 1)
                if result:
                    return result
        return None

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
