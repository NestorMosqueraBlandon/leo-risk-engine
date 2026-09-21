from datetime import datetime, timezone
from typing import Self

from pydantic import BaseModel, Field, model_validator

from leo_risk.domain.academic_calendar import AcademicCalendar
from leo_risk.domain.censorship import CensorshipType
from leo_risk.domain.enums import OutcomeStatus
from leo_risk.domain.exit_reason import ExitReason, NON_DROPOUT_REASONS


class StudentOutcome(BaseModel):
    """Represents the enrollment outcome of a student between two periods.

    The reference_period (T) is the period where the student was enrolled.
    The observation_period (T+1) is the next period whose closure we are
    checking to determine if the student continued.

    The outcome can only be determined after observation_period has been
    officially closed by the institution.
    """

    student_id: str = Field(..., min_length=1, description="Unique student identifier")
    institution_id: str = Field(..., min_length=1, description="Unique institution identifier")
    program_id: str = Field(..., min_length=1, description="Academic program identifier")

    reference_period: str = Field(
        ..., min_length=1, description="Period T where student was enrolled"
    )
    observation_period: str = Field(
        ..., min_length=1, description="Period T+1 to check for continuation"
    )

    status: OutcomeStatus
    exit_reason: ExitReason = ExitReason.NONE
    censorship_type: CensorshipType

    calendar_type: AcademicCalendar
    periods_elapsed: int = Field(
        default=1,
        ge=0,
        description="Number of periods between reference and observation. "
        "Greater than 1 for gap analysis (e.g., student skipped a period).",
    )

    data_source: str = Field(
        default="institution",
        description="Origin of the enrollment data (institution, manual, api).",
    )
    confidence_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence in the outcome assignment. 1.0 = certain, "
        "0.0 = no confidence. Useful when data is partial.",
    )

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def validate_consistency(self) -> Self:
        status = self.status
        exit_reason = self.exit_reason
        censorship = self.censorship_type

        # CONTINUED must have exit_reason NONE
        if status == OutcomeStatus.CONTINUED and exit_reason != ExitReason.NONE:
            msg = "CONTINUED status requires exit_reason=NONE"
            raise ValueError(msg)

        # DROPPED_OUT must have an exit_reason
        if status == OutcomeStatus.DROPPED_OUT and exit_reason == ExitReason.NONE:
            msg = "DROPPED_OUT status requires a specific exit_reason"
            raise ValueError(msg)

        # Non-dropout exit reasons cannot be DROPPED_OUT
        if status == OutcomeStatus.DROPPED_OUT and exit_reason in NON_DROPOUT_REASONS:
            msg = f"exit_reason={exit_reason.value} is incompatible with DROPPED_OUT"
            raise ValueError(msg)

        # PENDING and UNKNOWN cannot have dropout exit reasons
        if status in (OutcomeStatus.PENDING, OutcomeStatus.UNKNOWN):
            if exit_reason not in (ExitReason.NONE, ExitReason.NOT_REPORTED):
                msg = (
                    f"status={status.value} cannot have exit_reason={exit_reason.value}. "
                    "Only NONE or NOT_REPORTED allowed for pending/unknown outcomes."
                )
                raise ValueError(msg)

        # Censorship mapping validation
        if status == OutcomeStatus.DROPPED_OUT and censorship == CensorshipType.RIGHT_CENSORED:
            msg = "DROPPED_OUT cannot be RIGHT_CENSORED (event was observed)"
            raise ValueError(msg)

        if status == OutcomeStatus.CONTINUED and censorship == CensorshipType.OBSERVED:
            msg = "CONTINUED cannot be OBSERVED (dropout was not observed)"
            raise ValueError(msg)

        if status in (OutcomeStatus.PENDING, OutcomeStatus.UNKNOWN):
            if censorship != CensorshipType.NOT_CENSORABLE:
                msg = f"status={status.value} must have censorship_type=NOT_CENSORABLE"
                raise ValueError(msg)

        # Period validation
        if self.reference_period == self.observation_period:
            msg = "reference_period and observation_period must be different"
            raise ValueError(msg)

        return self

    @property
    def is_dropout(self) -> bool:
        return self.status == OutcomeStatus.DROPPED_OUT

    @property
    def is_censored(self) -> bool:
        return self.censorship_type in (
            CensorshipType.RIGHT_CENSORED,
            CensorshipType.LEFT_CENSORED,
            CensorshipType.INTERVAL_CENSORED,
        )

    @property
    def is_usable_for_survival(self) -> bool:
        return self.censorship_type != CensorshipType.NOT_CENSORABLE
