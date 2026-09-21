"""Enrollment and course contracts.

These define the relationships between students, periods, programs,
and courses. They are the structural backbone of the academic model.
"""

from enum import StrEnum

from pydantic import Field

from leo_risk.contracts.base import CanonicalBase, DataAvailability


class EnrollmentStatus(StrEnum):
    ENROLLED = "enrolled"
    COMPLETED = "completed"
    WITHDRAWN = "withdrawn"
    DROPPED = "dropped"
    FAILED = "failed"
    INCOMPLETE = "incomplete"
    TRANSFERRED = "transferred"
    UNKNOWN = "unknown"


class Enrollment(CanonicalBase, DataAvailability):
    """A student's enrollment in a program for a specific period.

    This is the primary record for determining continuation/dropout.
    One enrollment per student per program per period.
    """

    enrollment_id: str = Field(..., min_length=1)
    student_id: str = Field(..., min_length=1)
    institution_id: str = Field(..., min_length=1)
    program_id: str = Field(..., min_length=1)
    period_id: str = Field(..., min_length=1)

    status: EnrollmentStatus
    is_active: bool = Field(
        default=True,
        description="Whether the enrollment is currently active. "
        "A student with is_active=True in T+1 continued.",
    )

    # Academic standing
    semester_index: int | None = Field(
        default=None,
        ge=1,
        description="Which semester/trimester of the program this is "
        "(e.g., 3rd semester of a 10-semester program).",
    )
    accumulated_credits: float | None = Field(
        default=None,
        ge=0,
        description="Credits completed up to this period.",
    )
    term_gpa: float | None = Field(
        default=None,
        ge=0.0,
        le=5.0,
        description="GPA for this specific period (0.0 - 5.0 scale).",
    )
    cumulative_gpa: float | None = Field(
        default=None,
        ge=0.0,
        le=5.0,
        description="Cumulative GPA up to this period.",
    )

    # Reason for non-continuation (if applicable)
    exit_reason: str | None = Field(
        default=None,
        description="Raw exit reason from source system. "
        "Normalized via LabelContract.resolve_exit_reason().",
    )
    exit_date: str | None = Field(
        default=None,
        description="Date when the student exited (ISO 8601). Null if still enrolled.",
    )


class Course(CanonicalBase):
    """A course offering within a specific period.

    Represents the course itself, not a student's enrollment in it.
    """

    course_id: str = Field(..., min_length=1)
    institution_id: str = Field(..., min_length=1)
    program_id: str = Field(..., min_length=1)
    period_id: str = Field(..., min_length=1)

    code: str = Field(..., min_length=1, description="Course code (e.g., 'MATH101').")
    name: str = Field(..., min_length=1)
    credits: float = Field(default=0.0, ge=0, description="Credit value of the course.")
    section: str = Field(default="", description="Section identifier if multiple sections.")
    instructor_id: str | None = Field(default=None)

    # Prerequisites and structure
    required: bool = Field(
        default=True,
        description="Whether this is a required or elective course.",
    )
    prerequisite_ids: list[str] = Field(
        default_factory=list,
        description="IDs of prerequisite courses.",
    )


class CourseEnrollment(CanonicalBase, DataAvailability):
    """A student's enrollment in a specific course within a period.

    Links a Student to a Course. One record per student per course per period.
    """

    course_enrollment_id: str = Field(..., min_length=1)
    student_id: str = Field(..., min_length=1)
    course_id: str = Field(..., min_length=1)
    period_id: str = Field(..., min_length=1)
    enrollment_id: str = Field(
        ...,
        description="Reference to the parent Enrollment record.",
    )

    status: EnrollmentStatus
    is_active: bool = Field(default=True)

    # Final results (populated after period closes)
    final_grade: float | None = Field(
        default=None,
        description="Final numeric grade for the course. Null if period not closed.",
    )
    grade_scale: str = Field(
        default="0-5",
        description="Grade scale used (e.g., '0-5', '0-100', 'A-F', 'pass-fail').",
    )
    passed: bool | None = Field(
        default=None,
        description="Whether the student passed. Null if not yet determined.",
    )
    withdraw_date: str | None = Field(
        default=None,
        description="Date the student withdrew from the course, if applicable.",
    )
