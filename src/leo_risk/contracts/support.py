"""Engagement and support contracts.

These capture student interaction with institutional systems and
support services. Low engagement and lack of support are early
warning signals.
"""

from enum import StrEnum

from pydantic import Field

from leo_risk.contracts.base import DataAvailability


class EngagementEventType(StrEnum):
    LMS_LOGIN = "lms_login"
    LMS_ASSIGNMENT_SUBMIT = "lms_assignment_submit"
    LMS_FORUM_POST = "lms_forum_post"
    LMS_VIDEO_WATCH = "lms_video_watch"
    LMS_RESOURCE_ACCESS = "lms_resource_access"
    LIBRARY_ACCESS = "library_access"
    EMAIL_OPENED = "email_opened"
    EMAIL_CLICKED = "email_clicked"
    ADVISOR_MEETING = "advisor_meeting"
    TUTORING_SESSION = "tutoring_session"
    CUSTOM = "custom"


class EngagementEvent(DataAvailability):
    """A discrete engagement event.

    Events are raw observations. Engagement features (e.g.,
    'login_frequency_7d', 'assignment_submission_rate') should
    be computed from these events in the feature pipeline.
    """

    event_id: str = Field(..., min_length=1)
    student_id: str = Field(..., min_length=1)
    period_id: str = Field(..., min_length=1)

    event_type: EngagementEventType
    event_name: str = Field(
        default="",
        description="Human-readable event name for custom types.",
    )

    # Source
    platform: str = Field(
        default="",
        description="Platform where event occurred (e.g., 'canvas', 'moodle', 'blackboard').",
    )
    url: str | None = Field(default=None)
    duration_seconds: int | None = Field(
        default=None,
        ge=0,
        description="Duration of the event if applicable (e.g., video watch time).",
    )

    # Context
    course_id: str | None = Field(default=None)
    metadata: dict[str, str] = Field(
        default_factory=dict,
        description="Additional event-specific data.",
    )


class SupportType(StrEnum):
    ACADEMIC_ADVISOR = "academic_advisor"
    TUTORING = "tutoring"
    COUNSELING = "counseling"
    CAREER_SERVICES = "career_services"
    FINANCIAL_AID = "financial_aid"
    DISABILITY_SERVICES = "disability_services"
    PEER_MENTORING = "peer_mentoring"
    WORKSHOP = "workshop"
    CUSTOM = "custom"


class StudentSupport(DataAvailability):
    """A support service interaction or enrollment.

    Tracks whether the student is receiving support and what type.
    Students without support who show risk signals are higher priority.
    """

    support_id: str = Field(..., min_length=1)
    student_id: str = Field(..., min_length=1)
    period_id: str = Field(..., min_length=1)

    support_type: SupportType
    status: str = Field(
        default="active",
        description="Status: 'active', 'completed', 'pending', 'cancelled'.",
    )

    # Details
    provider_name: str = Field(default="", description="Name of the support provider.")
    provider_id: str | None = Field(default=None)
    sessions_completed: int = Field(default=0, ge=0)
    sessions_scheduled: int = Field(default=0, ge=0)
    start_date: str | None = Field(default=None)
    end_date: str | None = Field(default=None)

    notes: str = Field(default="")
