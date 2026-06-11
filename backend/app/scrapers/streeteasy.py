import json
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
    "Nolita": "nolita",
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
            parts.append(f"beds:{beds}")

        neighborhoods = criteria.get("neighborhoods", [])
        area_slugs = []
        for n in neighborhoods:
            slug = NEIGHBORHOOD_SLUGS.get(n)
            if slug:
                area_slugs.append(slug)

        if area_slugs:
            parts.append(f"area:{','.join(area_slugs)}")

        if criteria.get("move_in_date"):
            parts.append(f"availability:{criteria['move_in_date']}")

        filter_str = "%7C".join(parts) if parts else ""
        base = "https://streeteasy.com/for-rent/nyc"
        return f"{base}/{filter_str}" if filter_str else base

    async def scrape(self, criteria: dict) -> list[RawListing]:
        listings = []
        context = None
        try:
            context = await self.new_context()
            page = await context.new_page()

            search_url = self._build_url(criteria)
            logger.info("Scraping StreetEasy", url=search_url)

            if not await self.safe_goto(page, search_url):
                logger.error("Failed to load StreetEasy search", url=search_url)
                return []

            # Wait for content to render
            await page.wait_for_timeout(5000)

            # Try to extract from embedded JSON first (most reliable)
            listings = await self._extract_from_page_json(page)
            if listings:
                logger.info(f"StreetEasy: extracted {len(listings)} listings from JSON")
                return listings

            # Fallback: try DOM selectors
            card_selectors = [
                "[data-testid='listing-card']",
                "li[class*='listingCard']",
                ".listingCard",
                ".searchCardList--listItem",
                "article[class*='listing']",
                "[class*='SearchCardList'] > li",
                "[class*='searchCard']",
                "a[href*='/rental/']",
            ]

            cards = []
            for selector in card_selectors:
                cards = await page.query_selector_all(selector)
                if cards:
                    logger.info(f"Found {len(cards)} cards with selector: {selector}")
                    break

            if not cards:
                # Log page info for debugging
                title = await page.title()
                url = page.url
                content_len = len(await page.content())
                logger.warning(
                    "No listing cards found on StreetEasy",
                    page_title=title,
                    final_url=url,
                    content_length=content_len,
                )
                # Try to get all links as last resort
                all_links = await page.query_selector_all("a[href*='/rental/']")
                if all_links:
                    logger.info(f"Found {len(all_links)} rental links as fallback")
                    cards = all_links
                else:
                    return []

            for card in cards[:20]:
                try:
                    listing = await self._parse_card(card, page)
                    if listing:
                        listings.append(listing)
                except Exception as e:
                    logger.debug("Failed to parse StreetEasy card", error=str(e))

            logger.info(f"Scraped {len(listings)} listings from StreetEasy")

        except Exception as e:
            logger.error("StreetEasy scraper error", error=str(e))
        finally:
            if context:
                await context.close()

        return listings

    async def _extract_from_page_json(self, page: Page) -> list[RawListing]:
        """Try to extract listing data from StreetEasy's embedded JSON."""
        listings = []
        try:
            # Look for __NEXT_DATA__ or inline JSON
            next_data = await page.query_selector("script#__NEXT_DATA__")
            if next_data:
                text = await next_data.inner_text()
                data = json.loads(text)
                results = self._find_listings_in_json(data)
                for r in results:
                    listing = self._json_to_raw_listing(r)
                    if listing:
                        listings.append(listing)
                if listings:
                    return listings

            # Try application/json script tags
            scripts = await page.query_selector_all("script[type='application/json']")
            for script in scripts:
                try:
                    text = await script.inner_text()
                    if "rental" in text.lower() or "listing" in text.lower():
                        data = json.loads(text)
                        results = self._find_listings_in_json(data)
                        for r in results:
                            listing = self._json_to_raw_listing(r)
                            if listing:
                                listings.append(listing)
                        if listings:
                            return listings
                except Exception:
                    continue

            # Try extracting from inline scripts
            all_scripts = await page.query_selector_all("script:not([src])")
            for script in all_scripts[:10]:
                try:
                    text = await script.inner_text()
                    if "searchResults" in text or "listings" in text:
                        json_match = re.search(r'(\{.+?"listings?".+?\})', text, re.S)
                        if json_match:
                            data = json.loads(json_match.group(1))
                            results = self._find_listings_in_json(data)
                            for r in results:
                                listing = self._json_to_raw_listing(r)
                                if listing:
                                    listings.append(listing)
                            if listings:
                                return listings
                except Exception:
                    continue

        except Exception as e:
            logger.debug("JSON extraction failed", error=str(e))

        return listings

    def _find_listings_in_json(self, data, depth=0) -> list[dict]:
        if depth > 10:
            return []
        if isinstance(data, dict):
            for key in ("listings", "searchResults", "results", "listResults"):
                if key in data and isinstance(data[key], list):
                    return data[key]
            for v in data.values():
                results = self._find_listings_in_json(v, depth + 1)
                if results:
                    return results
        if isinstance(data, list) and len(data) > 2:
            if all(isinstance(item, dict) for item in data[:3]):
                if any("price" in item or "id" in item for item in data[:3]):
                    return data
        if isinstance(data, list):
            for item in data:
                results = self._find_listings_in_json(item, depth + 1)
                if results:
                    return results
        return []

    def _json_to_raw_listing(self, data: dict) -> RawListing | None:
        try:
            listing_id = str(data.get("id") or data.get("listingId") or data.get("rental_id", ""))
            if not listing_id:
                return None

            url = data.get("url") or data.get("detailUrl") or ""
            if url and not url.startswith("http"):
                url = f"https://streeteasy.com{url}"
            if not url:
                url = f"https://streeteasy.com/rental/{listing_id}"

            price = data.get("price") or data.get("rent")
            if isinstance(price, str):
                m = re.search(r"[\d,]+", price)
                price = int(m.group().replace(",", "")) if m else None

            address = data.get("address") or data.get("streetAddress") or data.get("title", "")
            neighborhood = data.get("neighborhood") or data.get("area", "")
            beds = data.get("bedrooms") or data.get("beds")
            baths = data.get("bathrooms") or data.get("baths")
            sqft = data.get("sqft") or data.get("area_sqft")

            return RawListing(
                source="streeteasy",
                source_id=listing_id,
                url=url,
                title=address or f"StreetEasy #{listing_id}",
                price=int(price) if price else None,
                beds=int(beds) if beds else None,
                baths=float(baths) if baths else None,
                sqft=int(sqft) if sqft else None,
                address=address if isinstance(address, str) else str(address),
                neighborhood=neighborhood if isinstance(neighborhood, str) else None,
            )
        except Exception:
            return None

    async def scrape_single_listing(self, url: str) -> RawListing | None:
        """Scrape a single StreetEasy listing detail page."""
        context = None
        try:
            context = await self.new_context()
            page = await context.new_page()

            if not await self.safe_goto(page, url):
                return None

            await page.wait_for_timeout(3000)

            source_id_match = re.search(r"/(\d+)(?:\?|$)", url)
            source_id = source_id_match.group(1) if source_id_match else url.split("/")[-1]

            price = None
            for sel in ["[data-testid='price']", "[class*='price']", "[class*='Price']", "h3"]:
                el = await page.query_selector(sel)
                if el:
                    text = await el.inner_text()
                    match = re.search(r"\$?([\d,]+)", text)
                    if match:
                        price = int(match.group(1).replace(",", ""))
                        break

            address = None
            for sel in ["[data-testid='address']", "h1", "[class*='addr']", "[class*='Address']"]:
                el = await page.query_selector(sel)
                if el:
                    address = (await el.inner_text()).strip()
                    if address:
                        break

            beds, baths, sqft = None, None, None
            detail_text = await page.inner_text("body")
            beds_match = re.search(r"(\d+)\s*(?:bed|br|bedroom)", detail_text, re.I)
            baths_match = re.search(r"([\d.]+)\s*(?:bath|ba)", detail_text, re.I)
            sqft_match = re.search(r"([\d,]+)\s*(?:sq\.?\s*ft|sqft|sf)", detail_text, re.I)
            if beds_match:
                beds = int(beds_match.group(1))
            if baths_match:
                baths = float(baths_match.group(1))
            if sqft_match:
                sqft = int(sqft_match.group(1).replace(",", ""))

            amenities = []
            for sel in ["[class*='amenities'] li", "[class*='Amenities'] li", "[data-testid='amenities'] li"]:
                els = await page.query_selector_all(sel)
                if els:
                    for el in els:
                        text = (await el.inner_text()).strip()
                        if text:
                            amenities.append(text)
                    break

            broker_name, broker_email, broker_phone = None, None, None
            for sel in ["[class*='agent'] [class*='name']", "[class*='broker'] [class*='name']", "[class*='Agent'] a"]:
                el = await page.query_selector(sel)
                if el:
                    broker_name = (await el.inner_text()).strip()
                    break

            email_link = await page.query_selector("a[href^='mailto:']")
            if email_link:
                href = await email_link.get_attribute("href")
                if href:
                    broker_email = href.replace("mailto:", "").split("?")[0]

            phone_link = await page.query_selector("a[href^='tel:']")
            if phone_link:
                href = await phone_link.get_attribute("href")
                if href:
                    broker_phone = href.replace("tel:", "")

            description = None
            for sel in ["[class*='description']", "[data-testid='description']", "[class*='Description']"]:
                el = await page.query_selector(sel)
                if el:
                    description = (await el.inner_text()).strip()
                    break

            available_date = None
            avail_match = re.search(r"(?:available|move.?in|avail)\s*(?:on|from|:)?\s*(\w+ \d+,?\s*\d{4}|\d{1,2}/\d{1,2}/\d{2,4}|immediately|now)", detail_text, re.I)
            if avail_match:
                available_date = avail_match.group(1).strip()

            neighborhood = None
            for sel in ["[class*='neighborhood']", "[class*='Neighborhood']", "[class*='area']"]:
                el = await page.query_selector(sel)
                if el:
                    neighborhood = (await el.inner_text()).strip()
                    break

            logger.info("Scraped single StreetEasy listing", source_id=source_id, price=price)
            return RawListing(
                source="streeteasy",
                source_id=str(source_id),
                url=url,
                title=address or f"StreetEasy #{source_id}",
                price=price,
                beds=beds,
                baths=baths,
                sqft=sqft,
                address=address,
                neighborhood=neighborhood,
                amenities=amenities,
                broker_name=broker_name,
                broker_email=broker_email,
                broker_phone=broker_phone,
                description=description,
                available_date=available_date,
            )
        except Exception as e:
            logger.error("Failed to scrape single StreetEasy listing", url=url, error=str(e))
            return None
        finally:
            if context:
                await context.close()

    async def _parse_card(self, card, page: Page) -> RawListing | None:
        try:
            # Extract listing URL
            if await card.get_attribute("href"):
                href = await card.get_attribute("href")
            else:
                link = await card.query_selector("a[href*='/rental/']")
                if not link:
                    link = await card.query_selector("a")
                if not link:
                    return None
                href = await link.get_attribute("href")

            if not href:
                return None
            url = f"https://streeteasy.com{href}" if href.startswith("/") else href

            source_id_match = re.search(r"/(\d+)(?:\?|$)", href)
            source_id = source_id_match.group(1) if source_id_match else href

            # Extract price
            price = None
            card_text = await card.inner_text()
            price_match = re.search(r"\$\s*([\d,]+)", card_text)
            if price_match:
                price = int(price_match.group(1).replace(",", ""))

            # Extract beds/baths/sqft from card text
            beds, baths, sqft = None, None, None
            beds_match = re.search(r"(\d+)\s*(?:bed|br|bd)", card_text, re.I)
            baths_match = re.search(r"([\d.]+)\s*(?:bath|ba)", card_text, re.I)
            sqft_match = re.search(r"([\d,]+)\s*(?:sq\.?\s*ft|sqft|sf)", card_text, re.I)
            if beds_match:
                beds = int(beds_match.group(1))
            if baths_match:
                baths = float(baths_match.group(1))
            if sqft_match:
                sqft = int(sqft_match.group(1).replace(",", ""))

            # Extract address from card text (first line usually)
            lines = [l.strip() for l in card_text.split("\n") if l.strip()]
            address = lines[0] if lines else None

            # Get neighborhood from card
            neighborhood = None
            for line in lines:
                if any(n in line for n in ["Village", "Heights", "Hill", "Park", "Side", "Town"]):
                    neighborhood = line
                    break

            title = f"${price:,}/mo" if price else (address or "StreetEasy listing")

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
