import calendar
from datetime import date


def add_months(d: date, n: int, anchor_day: int | None = None) -> date:
    month = d.month - 1 + n
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(anchor_day or d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)
