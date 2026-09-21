"""Observation contracts: grades, attendance, financial status.

These are the primary data signals for risk prediction. Each observation
includes DataAvailability to track when the data was captured vs. when
it became available for use.
"""

from enum import StrEnum

from pydantic import Field

from leo_risk.contracts.base import DataAvailability


class GradeObservation(DataAvailability):
    """A grade observation for a course enrollment.

    Tracks individual grade events (midterm, final, assignments)
    rather than just the final grade. This enables temporal features
    like "grade trajectory" and "recent performance drop".
    """

    observation_id: str = Field(..., min_length=1)
    student_id: str = Field(..., min_length=1)
    course_enrollment_id: str = Field(..., min_length=1)
    period_id: str = Field(..., min_length=1)

    grade_type: str = Field(
        ...,
        description="Type of grade: 'midterm', 'final', 'assignment', 'quiz', "
        "'project', 'lab', 'participation', etc.",
    )
    score: float | None = Field(
        default=None,
        description="Numeric score. Null if not yet graded.",
    )
    max_score: float | None = Field(
        default=None,
        gt=0,
        description="Maximum possible score.",
    )
    percentage: float | None = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Percentage grade (0-100). Useful for cross-scale comparison.",
    )
    letter_grade: str | None = Field(
        default=None,
        description="Letter grade if applicable (e.g., 'A', 'B+', 'F').",
    )
    passed: bool | None = Field(default=None)
    comments: str = Field(default="")


class AttendanceStatus(StrEnum):
    PRESENT = "present"
    ABSENT = "absent"
    TARDY = "tardy"
    EXCUSED = "excused"
    NOT_RECORDED = "not_recorded"


class AttendanceObservation(DataAvailability):
    """An attendance observation for a course session.

    Aggregated attendance metrics (e.g., 'attendance_rate_30d')
    should be computed as features, not stored here. This is the
    raw event-level data.
    """

    observation_id: str = Field(..., min_length=1)
    student_id: str = Field(..., min_length=1)
    course_enrollment_id: str = Field(..., min_length=1)
    period_id: str = Field(..., min_length=1)

    session_date: str = Field(..., description="Date of the session (ISO 8601).")
    session_type: str = Field(
        default="class",
        description="Type of session: 'class', 'lab', 'exam', 'tutorial', etc.",
    )
    status: AttendanceStatus

    minutes_late: int | None = Field(
        default=None,
        ge=0,
        description="Minutes late if status is TARDY. Null otherwise.",
    )
    minutes_duration: int | None = Field(
        default=None,
        ge=0,
        description="Duration of the session in minutes.",
    )


class FinancialStatus(StrEnum):
    CURRENT = "current"
    OVERDUE = "overdue"
    PARTIAL_PAYMENT = "partial_payment"
    WAIVED = "waived"
    SCHOLARSHIP = "scholarship"
    ICETEX = "icetex"
    PENDING = "pending"
    UNKNOWN = "unknown"


class FinancialStatusRecord(DataAvailability):
    """Financial status of a student for a specific period.

    Tracks tuition payment status, scholarships, and financial aid.
    Financial distress is a strong predictor of dropout.
    """

    observation_id: str = Field(..., min_length=1)
    student_id: str = Field(..., min_length=1)
    period_id: str = Field(..., min_length=1)

    status: FinancialStatus
    amount_due: float | None = Field(
        default=None,
        ge=0,
        description="Total amount due for the period.",
    )
    amount_paid: float | None = Field(
        default=None,
        ge=0,
        description="Amount already paid.",
    )
    currency: str = Field(
        default="USD",
        min_length=3,
        max_length=3,
        description="ISO 4217 currency code.",
    )
    payment_deadline: str | None = Field(
        default=None,
        description="Payment deadline (ISO 8601 date).",
    )
    scholarship_type: str | None = Field(
        default=None,
        description="Type of scholarship or financial aid if applicable.",
    )
    has_outstanding_debt: bool = Field(
        default=False,
        description="Whether the student has debt from previous periods.",
    )
    consecutive_overdue_periods: int = Field(
        default=0,
        ge=0,
        description="Number of consecutive periods with overdue payments. "
        "High values are strong dropout signals.",
    )
