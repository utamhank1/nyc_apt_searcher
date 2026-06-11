import enum
from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, JSON, Enum, Text, UniqueConstraint
from app.core.database import Base


class ListingStatus(str, enum.Enum):
    NEW = "new"
    ALERTED = "alerted"
    PENDING = "pending"
    TOUR_SCHEDULED = "tour_scheduled"
    VISITED = "visited"
    APPLIED = "applied"
    PASSED = "passed"


class LeadResponse(str, enum.Enum):
    PENDING = "pending"
    YES = "yes"
    NO = "no"


class ListingSource(str, enum.Enum):
    STREETEASY = "streeteasy"
    ZILLOW = "zillow"
    REALTOR = "realtor"
    CRAIGSLIST = "craigslist"


class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_source_listing"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(20), nullable=False, index=True)
    source_id = Column(String(255), nullable=False)
    url = Column(Text, nullable=False)

    title = Column(String(500))
    price = Column(Integer, index=True)
    beds = Column(Integer, index=True)
    baths = Column(Float)
    sqft = Column(Integer)

    address = Column(String(500))
    neighborhood = Column(String(100), index=True)
    borough = Column(String(50), index=True)
    lat = Column(Float)
    lng = Column(Float)

    amenities = Column(JSON, default=list)
    images = Column(JSON, default=list)

    broker_name = Column(String(255))
    broker_email = Column(String(255))
    broker_phone = Column(String(50))

    open_house_dates = Column(JSON, default=list)
    description = Column(Text)

    commute_minutes = Column(Integer)
    match_score = Column(Float, index=True)

    status = Column(String(20), default=ListingStatus.NEW.value, index=True)
    lead_response = Column(String(10))
    lead_responded_at = Column(DateTime)
    notified = Column(Boolean, default=False)
    notified_hash = Column(String(64))

    is_active = Column(Boolean, default=True, index=True)
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    available_date = Column(String(20))

    is_favorite = Column(Boolean, default=False, index=True)

    search_config_id = Column(Integer, nullable=True)
    search_name = Column(String(100), nullable=True)

    broker_email_sent = Column(Boolean, default=False)
    broker_email_sent_at = Column(DateTime)
