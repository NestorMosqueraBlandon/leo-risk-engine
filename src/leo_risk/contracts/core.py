"""Core academic entities: Student, Institution, AcademicPeriod, AcademicProgram.

These are the foundational building blocks. They are institution-agnostic
and contain no country-specific fields (no SNIES, no estrato, no SPADIES).
Country-specific data goes into metadata or adapters.
"""

from enum import StrEnum

from pydantic import Field

from leo_risk.contracts.base import CanonicalBase


class StudentStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    GRADUATED = "graduated"
    WITHDRAWN = "withdrawn"
    SUSPENDED = "suspended"
    TRANSFERRED = "transferred"
    DECEASED = "deceased"
    UNKNOWN = "unknown"


class Gender(StrEnum):
    MALE = "male"
    FEMALE = "female"
    NON_BINARY = "non_binary"
    NOT_REPORTED = "not_reported"
    OTHER = "other"


class Student(CanonicalBase):
    """A student across all periods and programs.

    The student_id is the canonical internal ID. The external_ids
    dict maps source system IDs to this canonical ID.
    """

    student_id: str = Field(..., min_length=1, description="Canonical internal student ID.")
    institution_id: str = Field(..., min_length=1)
    status: StudentStatus = StudentStatus.UNKNOWN

    # Demographics (optional, institution-provided)
    date_of_birth: str | None = Field(
        default=None,
        description="ISO 8601 date (YYYY-MM-DD). Optional. "
        "Used for age features, not for identification.",
    )
    gender: Gender = Gender.NOT_REPORTED

    # Cross-system identity
    external_ids: dict[str, str] = Field(
        default_factory=dict,
        description="Map of source_system -> external ID. "
        "Example: {'sis_colombia': '12345', 'lms_canvas': 'user-67890'}.",
    )

    # Metadata
    enrollment_date: str | None = Field(
        default=None,
        description="When the student first enrolled at the institution (ISO 8601 date).",
    )


class Institution(CanonicalBase):
    """An educational institution.

    Contains only universal fields. Country-specific identifiers
    (e.g., SNIES code for Colombia, OPEID for US) go in metadata.
    """

    institution_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    country_code: str = Field(
        ...,
        min_length=2,
        max_length=2,
        description="ISO 3166-1 alpha-2 country code (e.g., 'CO', 'US', 'MX').",
    )
    metadata: dict[str, str] = Field(
        default_factory=dict,
        description="Extensible key-value pairs for institution-specific data. "
        "Examples: {'snies': '12345', 'opeid': '001234'}",
    )


class AcademicPeriod(CanonicalBase):
    """A defined academic time window (semester, trimester, quarter, etc.).

    The period_id is the canonical internal ID. The code field holds
    the institution's own period identifier.
    """

    period_id: str = Field(..., min_length=1)
    institution_id: str = Field(..., min_length=1)
    code: str = Field(
        ...,
        min_length=1,
        description="Institution's own period code (e.g., '2024-1', '2024-S1', '2024-T1').",
    )
    name: str = Field(
        default="",
        description="Human-readable period name (e.g., 'Fall 2024', 'Primer Semestre 2024').",
    )
    calendar_type: str = Field(
        ...,
        description="Calendar type: 'semester', 'trimester', 'quarter', "
        "'quadrimester', 'annual', 'custom'.",
    )
    start_date: str = Field(..., description="Period start date (ISO 8601).")
    end_date: str = Field(..., description="Period end date (ISO 8601).")
    is_closed: bool = Field(
        default=False,
        description="Whether this period has been officially closed/certified. "
        "Outcomes can only be determined for closed periods.",
    )
    closed_at: str | None = Field(
        default=None,
        description="When the period was closed (ISO 8601 datetime). Null if still open.",
    )


class AcademicProgram(CanonicalBase):
    """An academic program (degree, diploma, certificate).

    A student can be enrolled in a program, and enroll in courses
    that belong to that program.
    """

    program_id: str = Field(..., min_length=1)
    institution_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    code: str = Field(
        default="",
        description="Institution's own program code.",
    )
    level: str = Field(
        default="",
        description="Program level: 'undergraduate', 'graduate', 'doctorate', "
        "'technical', 'professional', 'certificate', etc.",
    )
    total_credits: float | None = Field(
        default=None,
        ge=0,
        description="Total credits required for graduation. Null if not credit-based.",
    )
    total_periods: int | None = Field(
        default=None,
        ge=0,
        description="Expected duration in academic periods. Null if variable.",
    )
