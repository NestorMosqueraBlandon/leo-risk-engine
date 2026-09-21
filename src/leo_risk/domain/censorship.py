from enum import StrEnum


class CensorshipType(StrEnum):
    """Censorship classification for survival analysis.

    OBSERVED
        The event (dropout) was observed during the study period.
        We know exactly when it happened.

    RIGHT_CENSORED
        The student was still enrolled at the end of the study period,
        or the observation window ended before dropout could occur.
        We know they hadn't dropped out yet, but don't know what
        happens after.

    LEFT_CENSORED
        The student had already dropped out before observation began,
        but we don't know when. Rare in practice.

    INTERVAL_CENSORED
        We know the dropout occurred within a time interval but not
        the exact period. For example: "sometime between semester 3
        and semester 5".

    NOT_CENSORABLE
        The record cannot be used for survival analysis at all
        (e.g., OutcomeStatus.UNKNOWN or PENDING).
    """

    OBSERVED = "observed"
    RIGHT_CENSORED = "right_censored"
    LEFT_CENSORED = "left_censored"
    INTERVAL_CENSORED = "interval_censored"
    NOT_CENSORABLE = "not_censorable"
