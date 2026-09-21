import pytest

from app.rate_limit import limiter


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """The limiter's in-memory storage outlives a single test. Register is
    capped at 10/minute, and most tests register a user, so any file with
    more than ten tests would start seeing 429s from its eleventh test on —
    a harness collision, not a product bug. Reset before each test so the
    limit is exercised only by tests that mean to."""
    limiter.reset()
    yield
