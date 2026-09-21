from enum import StrEnum


class OutcomeStatus(StrEnum):
    """Whether a student continued or left between two academic periods.

    CONTINUED
        Student was enrolled in period T and is enrolled in period T+1
        after T+1 has been officially closed/certified.

    DROPPED_OUT
        Student was enrolled in period T and is NOT enrolled in period T+1
        after T+1 has been officially closed/certified. The student did not
        complete the program through any recognized exit path.

    PENDING
        Period T+1 has not yet been officially closed. We cannot determine
        the outcome until the institution certifies the period.

    UNKNOWN
        Data is incomplete, contradictory, or the enrollment record for
        either period cannot be reliably interpreted.
    """

    CONTINUED = "continued"
    DROPPED_OUT = "dropped_out"
    PENDING = "pending"
    UNKNOWN = "unknown"
