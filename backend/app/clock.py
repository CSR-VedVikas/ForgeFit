"""The user's calendar.

Rows are stamped in naive UTC. "Today", "this week" and "which day was this
set" are questions about the *user's* calendar, which is not the server's:
the API used to answer them with date.today(), so a meal logged at 00:30 in
India (19:00 UTC the day before) landed on yesterday's totals, streaks and
weekly challenge. Every such question now goes through a UserClock.

The browser sends its IANA zone in X-Timezone on every request. A header
rather than a stored profile field means the answer follows the user when
they travel, and needs no migration. Anything missing or unrecognised falls
back to UTC, which is exactly the old behaviour on a UTC server.
"""

from datetime import date, datetime, time, timedelta, timezone
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Depends, Header

UTC = timezone.utc


class UserClock:
    def __init__(self, tz: ZoneInfo | timezone = UTC):
        self.tz = tz

    @property
    def name(self) -> str:
        return getattr(self.tz, "key", "UTC")

    def today(self) -> date:
        return datetime.now(self.tz).date()

    def local_date(self, stamp: datetime) -> date:
        """The user's calendar date for a stored naive-UTC timestamp."""
        return stamp.replace(tzinfo=UTC).astimezone(self.tz).date()

    def day_bounds(self, day: date) -> tuple[datetime, datetime]:
        """[start, end) of the user's day, as naive UTC to compare with rows.

        End is the next local midnight, not start + 24h: on a DST change the
        local day is 23 or 25 hours long."""
        start = datetime.combine(day, time.min, tzinfo=self.tz)
        end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=self.tz)
        return _naive_utc(start), _naive_utc(end)

    def week_start(self, day: date | None = None) -> date:
        """Monday of the user's week."""
        day = day or self.today()
        return day - timedelta(days=day.weekday())

    def week_bounds(self, monday: date | None = None) -> tuple[datetime, datetime]:
        monday = monday or self.week_start()
        start, _ = self.day_bounds(monday)
        end, _ = self.day_bounds(monday + timedelta(days=7))
        return start, end


def _naive_utc(dt: datetime) -> datetime:
    return dt.astimezone(UTC).replace(tzinfo=None)


def to_naive_utc(dt: datetime | None) -> datetime | None:
    """Normalise a client-supplied timestamp for storage. JS toISOString()
    sends an aware UTC value; the columns are naive UTC, and letting the
    driver decide what an aware value means differs between SQLite and
    Postgres."""
    if dt is None or dt.tzinfo is None:
        return dt
    return _naive_utc(dt)


def resolve(name: str | None) -> UserClock:
    if not name or len(name) > 64:
        return UserClock()
    try:
        return UserClock(ZoneInfo(name))
    except (ZoneInfoNotFoundError, ValueError):
        # ValueError: zoneinfo refuses keys that look like paths.
        return UserClock()


def get_user_clock(x_timezone: Annotated[str | None, Header()] = None) -> UserClock:
    return resolve(x_timezone)


Clock = Annotated[UserClock, Depends(get_user_clock)]
