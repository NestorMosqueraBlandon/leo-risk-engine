"""Base types and data availability pattern for all contracts.

Every observation used by ML must answer:
  "¿cuándo estuvo disponible esta información?"

The DataAvailability mixin enforces this by requiring:
  - observed_at:  when the real-world event happened
  - available_at: when this data entered the system (prevents leakage)
  - source_system: which SIS/provider produced this record
  - source_record_id: opaque ID in the source system
"""

from datetime import datetime, timezone
from typing import Annotated

from pydantic import BaseModel, Field


class DataAvailability(BaseModel):
    """Mixin for data lineage and leakage prevention.

    Every record that could be used as a feature MUST include this.
    The available_at timestamp is critical: features can only be used
    for predictions made AFTER this time.
    """

    observed_at: datetime = Field(
        ...,
        description="When the real-world event actually occurred.",
    )
    available_at: datetime = Field(
        ...,
        description="When this data became available in the system. "
        "Features derived from this record cannot be used for predictions "
        "made before this timestamp.",
    )
    source_system: str = Field(
        ...,
        min_length=1,
        description="Identifier of the source system (e.g., 'sis_colombia', 'lms_canvas', 'manual').",
    )
    source_record_id: str = Field(
        default="",
        description="Opaque record ID in the source system. Enables traceability.",
    )

    def is_available_before(self, cutoff: datetime) -> bool:
        """Check if this data was available before a given cutoff time."""
        return self.available_at <= cutoff


class CanonicalBase(BaseModel):
    """Base for all canonical domain objects."""

    model_config = {"strict": True, "validate_assignment": True}

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this canonical record was created.",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this canonical record was last updated.",
    )
