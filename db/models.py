from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(100), nullable=True)
    first_name = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    subscriptions = relationship(
        "Subscription", back_populates="user", cascade="all, delete-orphan"
    )
    notification_logs = relationship(
        "NotificationLog", back_populates="user", cascade="all, delete-orphan"
    )


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(String(20), nullable=False, index=True)
    section_no = Column(String(10), nullable=False, index=True)
    course_name = Column(String(255), nullable=True)
    sub_type = Column(String(20), default="SEAT", nullable=False, index=True)  # 'SEAT' or 'CHANGE'
    is_active = Column(Boolean, default=True, nullable=False)
    notified_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    user = relationship("User", back_populates="subscriptions")

    __table_args__ = (
        UniqueConstraint("user_id", "course_id", "section_no", "sub_type", name="uq_user_course_section_type"),
    )


class SectionCache(Base):
    """
    Stores last known state of monitored sections to detect state transitions (FULL -> AVAILABLE)
    or detail changes (Instructor, Room, Schedule, Seats).
    """
    __tablename__ = "section_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    course_id = Column(String(20), nullable=False, index=True)
    section_no = Column(String(10), nullable=False, index=True)
    course_name = Column(String(255), nullable=True)
    instructor = Column(String(100), nullable=True)
    capacity = Column(Integer, default=0)
    enrolled = Column(Integer, default=0)
    available_seats = Column(Integer, default=0)
    days = Column(String(50), nullable=True)
    time_from = Column(String(20), nullable=True)
    time_to = Column(String(20), nullable=True)
    room = Column(String(50), nullable=True)
    notes = Column(String(255), nullable=True)
    is_full = Column(Boolean, default=True)
    last_checked_at = Column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        UniqueConstraint("course_id", "section_no", name="uq_cache_course_section"),
    )


class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(String(20), nullable=False)
    section_no = Column(String(10), nullable=False)
    available_seats = Column(Integer, nullable=False)
    sent_at = Column(DateTime(timezone=True), default=utcnow)

    user = relationship("User", back_populates="notification_logs")
