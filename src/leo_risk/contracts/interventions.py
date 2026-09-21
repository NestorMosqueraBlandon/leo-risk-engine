"""Intervention contract.

Interventions are actions taken by advisors or the institution in
response to risk signals. Tracking interventions is critical for
understanding model impact and for causal inference.
"""

from enum import StrEnum

from pydantic import Field

from leo_risk.contracts.base import DataAvailability


class InterventionType(StrEnum):
    ADVISOR_OUTREACH = "advisor_outreach"
    EMAIL_CAMPAIGN = "email_campaign"
    PHONE_CALL = "phone_call"
    MEETING_SCHEDULED = "meeting_scheduled"
    TUTORING_REFERRAL = "tutoring_referral"
    FINANCIAL_AID_REVIEW = "financial_aid_review"
    ACADEMIC_PLAN = "academic_plan"
    PROBATION_WARNING = "probation_warning"
    PEER_SUPPORT = "peer_support"
    CUSTOM = "custom"


class InterventionOutcome(StrEnum):
    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"
    NO_RESPONSE = "no_response"
    DECLINED = "declined"
    DEFERRED = "deferred"
    UNKNOWN = "unknown"


class Intervention(DataAvailability):
    """An intervention action taken for a student.

    Interventions are the institutional response to risk predictions.
    They are essential for:
    1. Measuring model impact (did the intervention help?)
    2. Avoiding confounding (students who got help vs. those who didn't)
    3. Resource allocation (which interventions are most effective?)
    """

    intervention_id: str = Field(..., min_length=1)
    student_id: str = Field(..., min_length=1)
    period_id: str = Field(..., min_length=1)

    intervention_type: InterventionType
    triggered_by: str = Field(
        default="",
        description="What triggered this intervention: 'risk_score', 'manual', "
        "'policy', 'student_request', etc.",
    )

    # Execution
    advisor_id: str | None = Field(default=None)
    advisor_name: str = Field(default="")
    description: str = Field(default="")
    outcome: InterventionOutcome = InterventionOutcome.UNKNOWN

    # Timing
    scheduled_date: str | None = Field(default=None)
    completed_date: str | None = Field(default=None)

    # Context
    risk_score_at_intervention: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Risk score that triggered or was present at intervention time.",
    )
    notes: str = Field(default="")
    metadata: dict[str, str] = Field(default_factory=dict)
