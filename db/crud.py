from datetime import datetime, timezone
from typing import List, Optional, Tuple
from sqlalchemy import select, update, delete, distinct
from sqlalchemy.ext.asyncio import AsyncSession
from .models import User, Subscription, SectionCache, NotificationLog


def utcnow():
    return datetime.now(timezone.utc)


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
) -> User:
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    else:
        # Update username/first_name if changed
        if user.username != username or user.first_name != first_name:
            user.username = username
            user.first_name = first_name
            await session.commit()

    return user


async def add_subscription(
    session: AsyncSession,
    user_id: int,
    course_id: str,
    section_no: str,
    course_name: Optional[str] = None,
) -> Tuple[Subscription, bool]:
    """
    Returns (subscription, created_bool)
    """
    course_id = str(course_id).strip()
    section_no = str(section_no).strip()

    stmt = select(Subscription).where(
        Subscription.user_id == user_id,
        Subscription.course_id == course_id,
        Subscription.section_no == section_no,
    )
    result = await session.execute(stmt)
    sub = result.scalar_one_or_none()

    if sub:
        if not sub.is_active:
            sub.is_active = True
            sub.notified_at = None
            if course_name:
                sub.course_name = course_name
            await session.commit()
            await session.refresh(sub)
            return sub, True
        return sub, False

    sub = Subscription(
        user_id=user_id,
        course_id=course_id,
        section_no=section_no,
        course_name=course_name,
        is_active=True,
    )
    session.add(sub)
    await session.commit()
    await session.refresh(sub)
    return sub, True


async def remove_subscription(
    session: AsyncSession,
    user_id: int,
    course_id: str,
    section_no: str,
) -> bool:
    course_id = str(course_id).strip()
    section_no = str(section_no).strip()

    stmt = delete(Subscription).where(
        Subscription.user_id == user_id,
        Subscription.course_id == course_id,
        Subscription.section_no == section_no,
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount > 0


async def get_user_subscriptions(
    session: AsyncSession,
    user_id: int,
    active_only: bool = True,
) -> List[Subscription]:
    stmt = select(Subscription).where(Subscription.user_id == user_id)
    if active_only:
        stmt = stmt.where(Subscription.is_active.is_(True))
    stmt = stmt.order_by(Subscription.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_unique_active_sections(
    session: AsyncSession,
) -> List[Tuple[str, str]]:
    """
    Deduplication query: Returns distinct (course_id, section_no) pairs
    that have at least one active subscriber.
    """
    stmt = (
        select(distinct(Subscription.course_id), Subscription.section_no)
        .where(Subscription.is_active.is_(True))
    )
    result = await session.execute(stmt)
    return [(row[0], row[1]) for row in result.all()]


async def get_subscribers_for_section(
    session: AsyncSession,
    course_id: str,
    section_no: str,
) -> List[Tuple[Subscription, User]]:
    """
    Returns (Subscription, User) pairs for all active subscribers of a section.
    """
    stmt = (
        select(Subscription, User)
        .join(User, Subscription.user_id == User.id)
        .where(
            Subscription.course_id == str(course_id).strip(),
            Subscription.section_no == str(section_no).strip(),
            Subscription.is_active.is_(True),
        )
    )
    result = await session.execute(stmt)
    return list(result.all())


async def get_section_cache(
    session: AsyncSession,
    course_id: str,
    section_no: str,
) -> Optional[SectionCache]:
    stmt = select(SectionCache).where(
        SectionCache.course_id == str(course_id).strip(),
        SectionCache.section_no == str(section_no).strip(),
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def update_section_cache(
    session: AsyncSession,
    course_id: str,
    section_no: str,
    course_name: Optional[str],
    capacity: int,
    enrolled: int,
    available_seats: int,
    is_full: bool,
) -> SectionCache:
    course_id = str(course_id).strip()
    section_no = str(section_no).strip()

    cache = await get_section_cache(session, course_id, section_no)
    now = utcnow()

    if not cache:
        cache = SectionCache(
            course_id=course_id,
            section_no=section_no,
            course_name=course_name,
            capacity=capacity,
            enrolled=enrolled,
            available_seats=available_seats,
            is_full=is_full,
            last_checked_at=now,
        )
        session.add(cache)
    else:
        cache.course_name = course_name or cache.course_name
        cache.capacity = capacity
        cache.enrolled = enrolled
        cache.available_seats = available_seats
        cache.is_full = is_full
        cache.last_checked_at = now

    await session.commit()
    await session.refresh(cache)
    return cache


async def mark_subscription_notified(
    session: AsyncSession,
    subscription_id: int,
) -> None:
    stmt = (
        update(Subscription)
        .where(Subscription.id == subscription_id)
        .values(notified_at=utcnow())
    )
    await session.execute(stmt)
    await session.commit()


async def reset_subscription_notification(
    session: AsyncSession,
    course_id: str,
    section_no: str,
) -> None:
    """
    When a section becomes full again, reset notified_at so subscribers
    will receive an alert next time a seat opens.
    """
    stmt = (
        update(Subscription)
        .where(
            Subscription.course_id == str(course_id).strip(),
            Subscription.section_no == str(section_no).strip(),
        )
        .values(notified_at=None)
    )
    await session.execute(stmt)
    await session.commit()


async def log_notification(
    session: AsyncSession,
    user_id: int,
    course_id: str,
    section_no: str,
    available_seats: int,
) -> None:
    log_entry = NotificationLog(
        user_id=user_id,
        course_id=str(course_id).strip(),
        section_no=str(section_no).strip(),
        available_seats=available_seats,
        sent_at=utcnow(),
    )
    session.add(log_entry)
    await session.commit()
