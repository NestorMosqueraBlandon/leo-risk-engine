"""RiskInput — the canonical entry contract for Leo Risk Engine.

RiskInput represents everything the engine can know about a student
at a exact moment in time (`as_of`). It is the stable boundary between
external data producers and the internal feature pipeline.

Design principles:
  - Institution-agnostic (no SNIES, SAT, estrato in core fields)
  - PII-free (no names, emails, phones, document numbers)
  - Point-in-time correct (all observations must satisfy available_at <= as_of)
  - Versioned (schema_version tracks breaking changes)
  - Deterministic serialization (for hashing and audit)
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from leo_risk.contracts.enrollment import Course, CourseEnrollment, Enrollment
from leo_risk.contracts.interventions import Intervention
from leo_risk.contracts.observations import (
    AttendanceObservation,
    FinancialStatusRecord,
    GradeObservation,
)
from leo_risk.contracts.support import EngagementEvent, StudentSupport

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SourceStatus(StrEnum):
    """Whether a data source is available for this student/institution."""

    AVAILABLE = "available"
    NOT_PROVIDED = "not_provided"
    NOT_INTEGRATED = "not_integrated"
    EMPTY = "empty"


class EducationLevel(StrEnum):
    """Universal education levels."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    TECHNICAL = "technical"
    UNDERGRADUATE = "undergraduate"
    GRADUATE = "graduate"
    DOCTORATE = "doctorate"
    PROFESSIONAL = "professional"
    CERTIFICATE = "certificate"
    CUSTOM = "custom"


# ---------------------------------------------------------------------------
# Sub-block models
# ---------------------------------------------------------------------------

class AcademicBlock(BaseModel):
    """Academic data observable at `as_of`.

    Contains canonical enrollment and course data. No derived features.
    """

    enrollments: list[Enrollment] = Field(
        default_factory=list,
        description="Enrollment records across periods.",
    )
    course_enrollments: list[CourseEnrollment] = Field(
        default_factory=list,
        description="Course-level enrollment records.",
    )
    courses: list[Course] = Field(
        default_factory=list,
        description="Course catalog entries for the relevant periods.",
    )
    grade_observations: list[GradeObservation] = Field(
        default_factory=list,
        description="Individual grade observations.",
    )


class AttendanceBlock(BaseModel):
    """Attendance observations at `as_of`.

    Raw event-level data. Aggregated metrics are computed by the feature pipeline.
    """

    observations: list[AttendanceObservation] = Field(
        default_factory=list,
        description="Individual attendance observations.",
    )


class FinancialBlock(BaseModel):
    """Financial status at `as_of`.

    Entirely optional. Some institutions don't track financial data
    or it's not relevant to the prediction.
    """

    records: list[FinancialStatusRecord] = Field(
        default_factory=list,
        description="Financial status records.",
    )


class EngagementBlock(BaseModel):
    """Engagement events at `as_of`.

    Contains raw interaction events from LMS, portals, etc.
    """

    events: list[EngagementEvent] = Field(
        default_factory=list,
        description="Engagement events.",
    )


class SupportsBlock(BaseModel):
    """Support service records at `as_of`."""

    records: list[StudentSupport] = Field(
        default_factory=list,
        description="Support service interactions.",
    )


class InterventionsBlock(BaseModel):
    """Intervention history at `as_of`."""

    records: list[Intervention] = Field(
        default_factory=list,
        description="Known interventions.",
    )


class InstitutionalContext(BaseModel):
    """Context that changes the meaning of other data.

    Uses universal concepts from the canonical model.
    Country-specific context goes in extensions.
    """

    period_id: str | None = Field(
        default=None,
        description="Current academic period ID.",
    )
    period_code: str | None = Field(
        default=None,
        description="Institution's own period code.",
    )
    period_start_date: str | None = Field(
        default=None,
        description="Start date of the current period (ISO 8601).",
    )
    period_end_date: str | None = Field(
        default=None,
        description="Expected end date of the current period (ISO 8601).",
    )
    period_is_closed: bool = Field(
        default=False,
        description="Whether the current period has been officially closed.",
    )
    calendar_type: str = Field(
        default="",
        description="Calendar type: 'semester', 'trimester', 'quarter', etc.",
    )
    program_id: str | None = Field(default=None)
    program_name: str | None = Field(default=None)
    program_level: EducationLevel | None = Field(
        default=None,
        description="Education level of the program.",
    )
    modality: str = Field(
        default="",
        description="Delivery modality: 'in_person', 'online', 'hybrid', etc.",
    )
    credit_system: str = Field(
        default="",
        description="Credit system type: 'semester_credits', 'quarter_credits', "
        "'ects', 'custom', etc.",
    )
    periods_completed: int | None = Field(
        default=None,
        ge=0,
        description="Number of academic periods the student has completed.",
    )
    total_periods: int | None = Field(
        default=None,
        ge=0,
        description="Total periods required for program completion.",
    )
    period_position_ratio: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Position within the current period (0.0 = start, 1.0 = end).",
    )


class SourceAvailability(BaseModel):
    """Explicit record of what data sources are available.

    Distinguishes between:
      - AVAILABLE: source is integrated and has data
      - NOT_PROVIDED: source exists but the institution didn't send data
      - NOT_INTEGRATED: source is not connected
      - EMPTY: source is connected but has no data for this student
    """

    source_id: str = Field(
        ...,
        min_length=1,
        description="Source identifier (e.g., 'academic', 'attendance', 'financial', "
        "'engagement', 'lms', 'support', 'interventions').",
    )
    status: SourceStatus
    last_available_at: datetime | None = Field(
        default=None,
        description="When data from this source was last updated.",
    )
    record_count: int | None = Field(
        default=None,
        ge=0,
        description="Number of records from this source (if known).",
    )


# ---------------------------------------------------------------------------
# RiskInput
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "1.0.0"


class RiskInput(BaseModel):
    """Canonical entry contract for Leo Risk Engine.

    Represents everything the engine can know about a student at a
    specific point in time. External systems must normalize their data
    to this contract before it enters the engine.

    The engine does NOT depend on leoApi or any specific SIS. Any
    producer capable of generating a valid RiskInput can use the engine.
    """

    schema_version: str = Field(
        default=SCHEMA_VERSION,
        pattern=r"^\d+\.\d+\.\d+$",
        description="Schema version. Increment major for breaking changes, "
        "minor for backward-compatible additions.",
    )

    # --- Point-in-time anchor ---
    as_of: datetime = Field(
        ...,
        description="The exact moment up to which information may be used. "
        "No observation with available_at > as_of is permitted.",
    )

    # --- Identity (opaque IDs) ---
    student_id: str = Field(..., min_length=1)
    institution_id: str = Field(..., min_length=1)
    academic_program_id: str | None = Field(
        default=None,
        description="Program the student is enrolled in.",
    )
    academic_period_id: str | None = Field(
        default=None,
        description="Current academic period.",
    )

    # --- Data blocks ---
    academic: AcademicBlock = Field(default_factory=AcademicBlock)
    attendance: AttendanceBlock = Field(default_factory=AttendanceBlock)
    financial: FinancialBlock | None = Field(
        default=None,
        description="Financial data. None if not available from this institution.",
    )
    engagement: EngagementBlock | None = Field(
        default=None,
        description="Engagement events. None if not available.",
    )
    supports: SupportsBlock | None = Field(
        default=None,
        description="Support services. None if not available.",
    )
    interventions: InterventionsBlock | None = Field(
        default=None,
        description="Intervention history. None if not available.",
    )
    institutional_context: InstitutionalContext = Field(
        default_factory=InstitutionalContext,
    )

    # --- Source tracking ---
    available_sources: list[SourceAvailability] = Field(
        default_factory=list,
        description="Which data sources are available for this student. "
        "Critical for missing data policy.",
    )

    # --- Extensions ---
    extensions: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Namespaced extensions for country/institution-specific data. "
        "Keys must be namespaced (e.g., 'co.education', 'us.collegeboard'). "
        "Values are validated dictionaries.",
    )

    @model_validator(mode="after")
    def validate_point_in_time(self) -> "RiskInput":
        """Reject any observation with available_at > as_of."""
        as_of = self.as_of
        violations: list[dict[str, Any]] = []

        def _check(obj: Any, path: str) -> None:
            if hasattr(obj, "available_at") and hasattr(obj, "observed_at") and obj.available_at > as_of:
                violations.append({
                    "field": path,
                    "available_at": obj.available_at.isoformat(),
                    "as_of": as_of.isoformat(),
                })
            if isinstance(obj, BaseModel):
                for field_name in obj.model_fields:
                    field_val = getattr(obj, field_name, None)
                    if field_val is None:
                        continue
                    if isinstance(field_val, list):
                        for i, item in enumerate(field_val):
                            _check(item, f"{path}.{field_name}[{i}]")
                    elif isinstance(field_val, BaseModel):
                        _check(field_val, f"{path}.{field_name}")

        _check(self.academic, "academic")
        _check(self.attendance, "attendance")
        if self.financial:
            _check(self.financial, "financial")
        if self.engagement:
            _check(self.engagement, "engagement")
        if self.supports:
            _check(self.supports, "supports")
        if self.interventions:
            _check(self.interventions, "interventions")

        if violations:
            msg = "Future data detected: the following observations have "
            "available_at > as_of, which would cause data leakage.\n"
            for v in violations:
                msg += (
                    f"  - {v['field']}: available_at={v['available_at']}, "
                    f"as_of={v['as_of']}\n"
                )
            raise ValueError(msg)

        return self

    def to_canonical_dict(self) -> dict[str, Any]:
        """Produce a deterministic dictionary for hashing.

        Sorts all lists by (available_at, observed_at) and removes
        auto-generated timestamps (created_at, updated_at) that would
        differ between equivalent instances.
        """
        data = self.model_dump(mode="json")

        def _clean_item(item: dict[str, Any]) -> dict[str, Any]:
            """Remove auto-generated timestamps that break determinism."""
            return {k: v for k, v in item.items() if k not in ("created_at", "updated_at")}

        def _clean_list(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
            cleaned = [_clean_item(x) for x in items]
            return sorted(
                cleaned,
                key=lambda x: (
                    x.get("available_at", ""),
                    x.get("observed_at", ""),
                ),
            )

        # Sort temporal collections in all blocks
        for block_key in ("academic", "attendance"):
            block = data.get(block_key, {})
            if isinstance(block, dict):
                for list_key in ("enrollments", "course_enrollments", "courses",
                                 "grade_observations", "observations"):
                    if list_key in block and isinstance(block[list_key], list):
                        block[list_key] = _clean_list(block[list_key])

        for optional_block in ("financial", "engagement", "supports", "interventions"):
            block = data.get(optional_block)
            if isinstance(block, dict):
                for list_key in block:
                    if isinstance(block[list_key], list):
                        block[list_key] = _clean_list(block[list_key])

        return data

    def compute_hash(self) -> str:
        """Compute a deterministic SHA-256 hash of this RiskInput."""
        import hashlib
        import json

        canonical = self.to_canonical_dict()
        payload = json.dumps(canonical, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
