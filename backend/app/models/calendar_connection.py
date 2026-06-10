from datetime import datetime

from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.core.database import Base


class CalendarConnection(Base):
    __tablename__ = "calendar_connections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_email = Column(String(255), unique=True, index=True, nullable=False)
    refresh_token = Column(String(500), nullable=False)
    is_main_user = Column(Boolean, default=False)
    connected_at = Column(DateTime, default=datetime.utcnow)
