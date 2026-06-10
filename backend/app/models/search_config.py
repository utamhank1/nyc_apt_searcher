from datetime import datetime

from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON
from app.core.database import Base


class SearchConfig(Base):
    __tablename__ = "search_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=False, index=True)

    boroughs = Column(JSON, default=list)
    neighborhoods = Column(JSON, default=list)
    max_price = Column(Integer, default=3500)
    min_price = Column(Integer, default=0)
    min_beds = Column(Integer, default=1)
    min_baths = Column(Integer, default=1)
    must_have_amenities = Column(JSON, default=list)
    preferred_amenities = Column(JSON, default=list)
    work_address = Column(String(500), default="")
    lead_score_threshold = Column(Integer, default=70)
    sources_enabled = Column(JSON, default=lambda: {"streeteasy": True, "zillow": True})

    move_in_mode = Column(String(20), default="")
    move_in_date = Column(String(20), default="")
    move_in_range_start = Column(String(20), default="")
    move_in_range_end = Column(String(20), default="")
    move_in_only = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_criteria_dict(self) -> dict:
        return {
            "boroughs": self.boroughs or [],
            "neighborhoods": self.neighborhoods or [],
            "max_price": self.max_price,
            "min_price": self.min_price,
            "min_beds": self.min_beds,
            "min_baths": self.min_baths,
            "must_have_amenities": self.must_have_amenities or [],
            "preferred_amenities": self.preferred_amenities or [],
            "work_address": self.work_address or "",
            "lead_score_threshold": self.lead_score_threshold,
            "sources_enabled": self.sources_enabled or {},
            "move_in_mode": self.move_in_mode or "",
            "move_in_date": self.move_in_date or "",
            "move_in_range_start": self.move_in_range_start or "",
            "move_in_range_end": self.move_in_range_end or "",
            "move_in_only": self.move_in_only or False,
        }

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "is_active": self.is_active,
            **self.to_criteria_dict(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
