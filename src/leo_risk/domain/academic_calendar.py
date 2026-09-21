from enum import StrEnum


class AcademicCalendar(StrEnum):
    """Type of academic period structure.

    Different institutions worldwide use different calendars.
    The calendar type affects how periods map to time and how
    we compute survival durations.

    SEMESTER
        2 periods per year (e.g., Spring/Fall, Feb-Jul/Aug-Dec).

    TRIMESTER
        3 periods per year (common in Latin America, some European
        systems).

    QUARTER
        4 periods per year (common in US community colleges).

    QUADRIMESTER
        4-month periods, typically 3 per year (common in some
        Latin American systems, e.g., Colombia: Feb-May,
        Jun-Aug, Sep-Dec).

    ANNUAL
        1 period per year (some professional programs).

    CUSTOM
        Institution-specific period structure that doesn't fit
        standard categories. Requires explicit period-to-month
        mapping.
    """

    SEMESTER = "semester"
    TRIMESTER = "trimester"
    QUARTER = "quarter"
    QUADRIMESTER = "quadrimester"
    ANNUAL = "annual"
    CUSTOM = "custom"
