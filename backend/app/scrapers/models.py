from dataclasses import dataclass, field


@dataclass
class RawListing:
    source: str
    source_id: str
    url: str
    title: str = ""
    price: int | None = None
    beds: int | None = None
    baths: float | None = None
    sqft: int | None = None
    address: str | None = None
    neighborhood: str | None = None
    borough: str | None = None
    amenities: list[str] = field(default_factory=list)
    images: list[str] = field(default_factory=list)
    broker_name: str | None = None
    broker_email: str | None = None
    broker_phone: str | None = None
    description: str | None = None
    open_house_dates: list[dict] = field(default_factory=list)
