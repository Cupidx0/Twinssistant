from datetime import datetime, timedelta

try:
    import holidays as holidays_lib
except ImportError:
    holidays_lib = None


def get_easter_date(year):
    """Return Easter Sunday for the given year using the Gregorian algorithm."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return datetime(year, month, day).date()

def get_nth_weekday(year, month, weekday, occurrence):
    """Return the nth weekday in a month, where Monday is 0."""
    current = datetime(year, month, 1).date()
    while current.weekday() != weekday:
        current += timedelta(days=1)
    return current + timedelta(weeks=occurrence - 1)

def get_last_weekday(year, month, weekday):
    """Return the last weekday in a month, where Monday is 0."""
    if month == 12:
        current = datetime(year + 1, 1, 1).date() - timedelta(days=1)
    else:
        current = datetime(year, month + 1, 1).date() - timedelta(days=1)
    while current.weekday() != weekday:
        current -= timedelta(days=1)
    return current

def get_substitute_holiday(actual_date):
    """Shift weekend public holidays to the next working day."""
    if actual_date.weekday() == 5:
        return actual_date + timedelta(days=2)
    if actual_date.weekday() == 6:
        return actual_date + timedelta(days=1)
    return actual_date

def get_uk_holidays(year):
    """Return a mapping of UK holiday dates to holiday names."""
    if holidays_lib is not None:
        try:
            return {
                holiday_date: holiday_name
                for holiday_date, holiday_name in holidays_lib.country_holidays("GB", years=year).items()
            }
        except Exception:
            pass

    easter_sunday = get_easter_date(year)
    easter_monday = easter_sunday + timedelta(days=1)
    good_friday = easter_sunday - timedelta(days=2)

    new_year = datetime(year, 1, 1).date()
    christmas = datetime(year, 12, 25).date()
    boxing_day = datetime(year, 12, 26).date()

    holiday_map = {
        get_substitute_holiday(new_year): "New Year's Day",
        datetime(year, 2, 14).date(): "Valentine's Day",
        datetime(year, 3, 17).date(): "St Patrick's Day",
        datetime(year, 10, 31).date(): "Halloween",
        datetime(year, 11, 5).date(): "Bonfire Night",
        datetime(year, 12, 24).date(): "Christmas Eve",
        get_substitute_holiday(christmas): "Christmas Day",
        get_substitute_holiday(boxing_day): "Boxing Day",
        good_friday: "Good Friday",
        easter_sunday: "Easter",
        easter_monday: "Easter Monday",
        get_nth_weekday(year, 5, 0, 1): "Early May Bank Holiday",
        get_last_weekday(year, 5, 0): "Spring Bank Holiday",
        get_last_weekday(year, 8, 0): "Summer Bank Holiday",
    }

    if get_substitute_holiday(christmas) == get_substitute_holiday(boxing_day):
        holiday_map[christmas + timedelta(days=2)] = "Boxing Day"

    return holiday_map

def get_current_label(current_date):
    """Return today's holiday if it is exact, otherwise return the meteorological season."""
    holiday = get_uk_holidays(current_date.year).get(current_date)
    if holiday:
        return holiday

    month = current_date.month
    if month in (3, 4, 5):
        return "Spring"
    if month in (6, 7, 8):
        return "Summer"
    if month in (9, 10, 11):
        return "Autumn"
    return "Winter"
