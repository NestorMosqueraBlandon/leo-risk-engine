from pydantic import BaseModel, Field

from leo_risk.domain.enums import OutcomeStatus
from leo_risk.domain.exit_reason import ExitReason


class LabelRule(BaseModel):
    """A single rule for assigning an outcome status."""

    description: str
    required_status: OutcomeStatus
    allowed_exit_reasons: frozenset[ExitReason] = Field(
        default_factory=frozenset,
        description="Exit reasons that satisfy this rule. Empty means any.",
    )
    requires_period_closed: bool = Field(
        default=True,
        description="Whether the observation period must be closed to apply this rule.",
    )
    minimum_data_fields: frozenset[str] = Field(
        default_factory=frozenset,
        description="Required data fields to apply this rule (e.g., enrollment_record, grades).",
    )


class LabelContract(BaseModel):
    """Formal contract defining how labels are assigned.

    The contract specifies:
    1. Which outcome statuses are valid
    2. What data is required for each status
    3. Rules for handling incomplete data
    4. Rules for handling special exit paths

    This contract is versioned. Changes to the contract require
    a new LabelVersion.
    """

    version: str = Field(..., description="Label version this contract belongs to")
    description: str

    rules: list[LabelRule] = Field(default_factory=list)

    # Data minimums
    require_enrollment_record: bool = Field(
        default=True,
        description="Must have enrollment record in both periods to assign CONTINUED or DROPPED_OUT.",
    )
    require_period_certification: bool = Field(
        default=True,
        description="Must have official period closure to assign CONTINUED or DROPPED_OUT.",
    )

    # Fallback behavior
    default_on_missing_data: OutcomeStatus = Field(
        default=OutcomeStatus.UNKNOWN,
        description="Status to assign when required data is missing.",
    )
    default_on_unclosed_period: OutcomeStatus = Field(
        default=OutcomeStatus.PENDING,
        description="Status to assign when observation period is not yet closed.",
    )

    # Exit path handling
    treat_graduation_as_dropout: bool = Field(
        default=False,
        description="Whether graduation counts as dropout (usually False).",
    )
    treat_transfer_as_dropout: bool = Field(
        default=False,
        description="Whether transfer counts as dropout (depends on policy).",
    )
    treat_authorized_leave_as_dropout: bool = Field(
        default=False,
        description="Whether authorized leave counts as dropout (usually False).",
    )

    def resolve_exit_reason(self, raw_reason: str | None) -> ExitReason:
        """Map a raw exit reason string from the data source to an ExitReason.

        Handles variations in naming across different institution systems.
        """
        if raw_reason is None:
            return ExitReason.NOT_REPORTED

        normalized = raw_reason.strip().lower()

        mapping: dict[str, ExitReason] = {
            # Graduation
            "graduado": ExitReason.GRADUATED,
            "graduated": ExitReason.GRADUATED,
            "completed": ExitReason.GRADUATED,
            "egresado": ExitReason.GRADUATED,
            # Transfer
            "transferencia": ExitReason.TRANSFERRED,
            "transferred": ExitReason.TRANSFERRED,
            "transfer": ExitReason.TRANSFERRED,
            "traslado": ExitReason.TRANSFERRED,
            # Authorized leave
            "permiso": ExitReason.AUTHORIZED_LEAVE,
            "authorized_leave": ExitReason.AUTHORIZED_LEAVE,
            "leave_of_absence": ExitReason.AUTHORIZED_LEAVE,
            " pausa autorizada": ExitReason.AUTHORIZED_LEAVE,
            "suspension": ExitReason.AUTHORIZED_LEAVE,
            # Voluntary withdrawal
            "retiro_voluntario": ExitReason.VOLUNTARY_WITHDRAWAL,
            "voluntary_withdrawal": ExitReason.VOLUNTARY_WITHDRAWAL,
            "withdrawal": ExitReason.VOLUNTARY_WITHDRAWAL,
            "renuncia": ExitReason.VOLUNTARY_WITHDRAWAL,
            # Academic
            "cancelacion_academica": ExitReason.ACADEMIC_DISMISSMENT,
            "academic_dismissal": ExitReason.ACADEMIC_DISMISSMENT,
            "academic_dismissment": ExitReason.ACADEMIC_DISMISSMENT,
            "desercion_academica": ExitReason.ACADEMIC_DISMISSMENT,
            # Administrative
            "administrativo": ExitReason.ADMINISTRATIVE,
            "administrative": ExitReason.ADMINISTRATIVE,
            "disciplinario": ExitReason.ADMINISTRATIVE,
            "financiero": ExitReason.ADMINISTRATIVE,
            # Deceased
            "fallecido": ExitReason.DECEASED,
            "deceased": ExitReason.DECEASED,
            "fallecimiento": ExitReason.DECEASED,
        }

        return mapping.get(normalized, ExitReason.NOT_REPORTED)

    def is_dropout_exit(self, reason: ExitReason) -> bool:
        """Determine if an exit reason counts as dropout per this contract."""
        if reason == ExitReason.GRADUATED:
            return self.treat_graduation_as_dropout
        if reason == ExitReason.TRANSFERRED:
            return self.treat_transfer_as_dropout
        if reason == ExitReason.AUTHORIZED_LEAVE:
            return self.treat_authorized_leave_as_dropout
        return reason in (
            ExitReason.VOLUNTARY_WITHDRAWAL,
            ExitReason.ACADEMIC_DISMISSMENT,
            ExitReason.ADMINISTRATIVE,
            ExitReason.NOT_REPORTED,
        )
