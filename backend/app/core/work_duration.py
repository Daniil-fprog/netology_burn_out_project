from decimal import Decimal

from app.core.enum import WorkUnit


CLOCK_HOURS_PER_TEACHING_HOUR = Decimal("0.75")


def to_clock_hours(duration: Decimal, unit: WorkUnit) -> Decimal:
    """Convert an input duration to the clock hours stored in the database."""
    if unit == WorkUnit.TEACHING_HOUR:
        return duration * CLOCK_HOURS_PER_TEACHING_HOUR
    return duration


def to_teaching_hours(clock_hours: Decimal) -> Decimal:
    """Convert stored clock hours back to teaching hours for compatible exports."""
    return clock_hours / CLOCK_HOURS_PER_TEACHING_HOUR
