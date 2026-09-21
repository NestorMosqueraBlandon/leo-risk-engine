from enum import StrEnum


class ExitReason(StrEnum):
    """Reason a student is no longer enrolled, if determinable.

    NONE
        The student did not leave. Used with OutcomeStatus.CONTINUED.

    GRADUATED
        Student completed all program requirements. This is NOT dropout.

    TRANSFERRED
        Student moved to another institution. May or may not count as
        dropout depending on institutional policy.

    AUTHORIZED_LEAVE
        Student obtained official leave (medical, military, personal).
        Temporarily not enrolled. May return.

    VOLUNTARY_WITHDRAWAL
        Student chose to leave without completing the program.

    ACADEMIC_DISMISSMENT
        Student was removed due to academic performance (GPA, failed courses).

    ADMINISTRATIVE
        Non-academic administrative removal (disciplinary, financial
        delinquency, expired documentation).

    NOT_REPORTED
        The institution did not report a reason. Cannot distinguish between
        voluntary withdrawal and other exit paths without additional data.

    DECEASED
        Student passed away. Rare but must be tracked separately.
    """

    NONE = "none"
    GRADUATED = "graduated"
    TRANSFERRED = "transferred"
    AUTHORIZED_LEAVE = "authorized_leave"
    VOLUNTARY_WITHDRAWAL = "voluntary_withdrawal"
    ACADEMIC_DISMISSMENT = "academic_dismissment"
    ADMINISTRATIVE = "administrative"
    NOT_REPORTED = "not_reported"
    DECEASED = "deceased"


# Exit paths that are NOT considered dropout
NON_DROPOUT_REASONS: frozenset[ExitReason] = frozenset(
    {ExitReason.NONE, ExitReason.GRADUATED, ExitReason.DECEASED}
)

# Exit paths where the student may return
POTENTIALLY_TEMPORARY: frozenset[ExitReason] = frozenset(
    {ExitReason.AUTHORIZED_LEAVE, ExitReason.TRANSFERRED}
)
