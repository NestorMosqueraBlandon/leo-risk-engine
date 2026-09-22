import pytest
from pydantic import ValidationError

from leo_risk.domain.academic_calendar import AcademicCalendar
from leo_risk.domain.censorship import CensorshipType
from leo_risk.domain.entities.student_outcome import StudentOutcome
from leo_risk.domain.enums import OutcomeStatus
from leo_risk.domain.exit_reason import NON_DROPOUT_REASONS, POTENTIALLY_TEMPORARY, ExitReason
from leo_risk.domain.label_contract import LabelContract
from leo_risk.domain.label_version import LabelVersion

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_outcome(**overrides) -> StudentOutcome:
    defaults = dict(
        student_id="S001",
        institution_id="INST01",
        program_id="PROG01",
        reference_period="2024-1",
        observation_period="2024-2",
        status=OutcomeStatus.CONTINUED,
        exit_reason=ExitReason.NONE,
        censorship_type=CensorshipType.RIGHT_CENSORED,
        calendar_type=AcademicCalendar.SEMESTER,
    )
    defaults.update(overrides)
    return StudentOutcome(**defaults)


@pytest.fixture
def continued_outcome() -> StudentOutcome:
    return _make_outcome()


@pytest.fixture
def dropout_outcome() -> StudentOutcome:
    return _make_outcome(
        status=OutcomeStatus.DROPPED_OUT,
        exit_reason=ExitReason.VOLUNTARY_WITHDRAWAL,
        censorship_type=CensorshipType.OBSERVED,
    )


@pytest.fixture
def pending_outcome() -> StudentOutcome:
    return _make_outcome(
        status=OutcomeStatus.PENDING,
        censorship_type=CensorshipType.NOT_CENSORABLE,
    )


@pytest.fixture
def unknown_outcome() -> StudentOutcome:
    return _make_outcome(
        status=OutcomeStatus.UNKNOWN,
        exit_reason=ExitReason.NOT_REPORTED,
        censorship_type=CensorshipType.NOT_CENSORABLE,
    )


# ---------------------------------------------------------------------------
# OutcomeStatus enum tests
# ---------------------------------------------------------------------------

class TestOutcomeStatus:
    def test_all_statuses_exist(self) -> None:
        assert len(OutcomeStatus) == 4

    def test_values_are_strings(self) -> None:
        assert OutcomeStatus.CONTINUED == "continued"
        assert OutcomeStatus.DROPPED_OUT == "dropped_out"
        assert OutcomeStatus.PENDING == "pending"
        assert OutcomeStatus.UNKNOWN == "unknown"


# ---------------------------------------------------------------------------
# ExitReason enum tests
# ---------------------------------------------------------------------------

class TestExitReason:
    def test_non_dropout_reasons_excludes_voluntary(self) -> None:
        assert ExitReason.VOLUNTARY_WITHDRAWAL not in NON_DROPOUT_REASONS

    def test_non_dropout_reasons_includes_graduated(self) -> None:
        assert ExitReason.GRADUATED in NON_DROPOUT_REASONS

    def test_non_dropout_reasons_includes_deceased(self) -> None:
        assert ExitReason.DECEASED in NON_DROPOUT_REASONS

    def test_potentially_temporary_includes_authorized_leave(self) -> None:
        assert ExitReason.AUTHORIZED_LEAVE in POTENTIALLY_TEMPORARY

    def test_potentially_temporary_includes_transfer(self) -> None:
        assert ExitReason.TRANSFERRED in POTENTIALLY_TEMPORARY


# ---------------------------------------------------------------------------
# CensorshipType tests
# ---------------------------------------------------------------------------

class TestCensorshipType:
    def test_all_types_exist(self) -> None:
        assert len(CensorshipType) == 5


# ---------------------------------------------------------------------------
# StudentOutcome — happy paths
# ---------------------------------------------------------------------------

class TestStudentOutcomeHappyPaths:
    def test_continued_outcome(self, continued_outcome: StudentOutcome) -> None:
        assert continued_outcome.status == OutcomeStatus.CONTINUED
        assert continued_outcome.is_dropout is False
        assert continued_outcome.is_censored is True
        assert continued_outcome.is_usable_for_survival is True

    def test_dropout_outcome(self, dropout_outcome: StudentOutcome) -> None:
        assert dropout_outcome.status == OutcomeStatus.DROPPED_OUT
        assert dropout_outcome.is_dropout is True
        assert dropout_outcome.is_censored is False
        assert dropout_outcome.is_usable_for_survival is True

    def test_pending_outcome(self, pending_outcome: StudentOutcome) -> None:
        assert pending_outcome.status == OutcomeStatus.PENDING
        assert pending_outcome.is_dropout is False
        assert pending_outcome.is_usable_for_survival is False

    def test_unknown_outcome(self, unknown_outcome: StudentOutcome) -> None:
        assert unknown_outcome.status == OutcomeStatus.UNKNOWN
        assert unknown_outcome.is_dropout is False
        assert unknown_outcome.is_usable_for_survival is False

    def test_dropout_with_transfer_reason(self) -> None:
        outcome = _make_outcome(
            status=OutcomeStatus.DROPPED_OUT,
            exit_reason=ExitReason.TRANSFERRED,
            censorship_type=CensorshipType.OBSERVED,
        )
        assert outcome.exit_reason == ExitReason.TRANSFERRED

    def test_left_censored_dropout(self) -> None:
        outcome = _make_outcome(
            status=OutcomeStatus.DROPPED_OUT,
            exit_reason=ExitReason.NOT_REPORTED,
            censorship_type=CensorshipType.LEFT_CENSORED,
        )
        assert outcome.censorship_type == CensorshipType.LEFT_CENSORED

    def test_interval_censored_dropout(self) -> None:
        outcome = _make_outcome(
            status=OutcomeStatus.DROPPED_OUT,
            exit_reason=ExitReason.ACADEMIC_DISMISSMENT,
            censorship_type=CensorshipType.INTERVAL_CENSORED,
        )
        assert outcome.censorship_type == CensorshipType.INTERVAL_CENSORED

    def test_different_calendars(self) -> None:
        for calendar in AcademicCalendar:
            outcome = _make_outcome(calendar_type=calendar)
            assert outcome.calendar_type == calendar

    def test_periods_elapsed_default(self) -> None:
        outcome = _make_outcome()
        assert outcome.periods_elapsed == 1

    def test_periods_elapsed_greater_than_one(self) -> None:
        outcome = _make_outcome(periods_elapsed=3)
        assert outcome.periods_elapsed == 3


# ---------------------------------------------------------------------------
# StudentOutcome — validation failures
# ---------------------------------------------------------------------------

class TestStudentOutcomeValidations:
    def test_continued_with_exit_reason_fails(self) -> None:
        with pytest.raises(ValidationError, match="CONTINUED status requires exit_reason=NONE"):
            _make_outcome(
                status=OutcomeStatus.CONTINUED,
                exit_reason=ExitReason.VOLUNTARY_WITHDRAWAL,
            )

    def test_dropout_without_exit_reason_fails(self) -> None:
        with pytest.raises(ValidationError, match="DROPPED_OUT status requires a specific exit_reason"):
            _make_outcome(
                status=OutcomeStatus.DROPPED_OUT,
                exit_reason=ExitReason.NONE,
                censorship_type=CensorshipType.OBSERVED,
            )

    def test_dropout_with_deceased_allowed(self) -> None:
        """DROPPED_OUT with DECEASED exit is allowed — policy decides via LabelContract."""
        outcome = _make_outcome(
            status=OutcomeStatus.DROPPED_OUT,
            exit_reason=ExitReason.DECEASED,
            censorship_type=CensorshipType.OBSERVED,
        )
        assert outcome.status == OutcomeStatus.DROPPED_OUT
        assert outcome.exit_reason == ExitReason.DECEASED

    def test_dropout_with_graduated_allowed(self) -> None:
        """DROPPED_OUT with GRADUATED exit is allowed — policy decides via LabelContract."""
        outcome = _make_outcome(
            status=OutcomeStatus.DROPPED_OUT,
            exit_reason=ExitReason.GRADUATED,
            censorship_type=CensorshipType.OBSERVED,
        )
        assert outcome.status == OutcomeStatus.DROPPED_OUT
        assert outcome.exit_reason == ExitReason.GRADUATED

    def test_pending_with_voluntary_reason_fails(self) -> None:
        with pytest.raises(ValidationError, match="status=pending cannot have exit_reason"):
            _make_outcome(
                status=OutcomeStatus.PENDING,
                exit_reason=ExitReason.VOLUNTARY_WITHDRAWAL,
                censorship_type=CensorshipType.NOT_CENSORABLE,
            )

    def test_unknown_with_academic_reason_fails(self) -> None:
        with pytest.raises(ValidationError, match="status=unknown cannot have exit_reason"):
            _make_outcome(
                status=OutcomeStatus.UNKNOWN,
                exit_reason=ExitReason.ACADEMIC_DISMISSMENT,
                censorship_type=CensorshipType.NOT_CENSORABLE,
            )

    def test_dropout_right_censored_fails(self) -> None:
        with pytest.raises(ValidationError, match="DROPPED_OUT cannot be RIGHT_CENSORED"):
            _make_outcome(
                status=OutcomeStatus.DROPPED_OUT,
                exit_reason=ExitReason.VOLUNTARY_WITHDRAWAL,
                censorship_type=CensorshipType.RIGHT_CENSORED,
            )

    def test_continued_observed_fails(self) -> None:
        with pytest.raises(ValidationError, match="CONTINUED cannot be OBSERVED"):
            _make_outcome(
                status=OutcomeStatus.CONTINUED,
                censorship_type=CensorshipType.OBSERVED,
            )

    def test_pending_must_be_not_censorable(self) -> None:
        with pytest.raises(ValidationError, match="status=pending must have censorship_type=NOT_CENSORABLE"):
            _make_outcome(
                status=OutcomeStatus.PENDING,
                censorship_type=CensorshipType.RIGHT_CENSORED,
            )

    def test_same_period_fails(self) -> None:
        with pytest.raises(ValidationError, match="reference_period and observation_period must be different"):
            _make_outcome(
                reference_period="2024-1",
                observation_period="2024-1",
            )

    def test_empty_student_id_fails(self) -> None:
        with pytest.raises(ValidationError):
            _make_outcome(student_id="")

    def test_empty_institution_id_fails(self) -> None:
        with pytest.raises(ValidationError):
            _make_outcome(institution_id="")

    def test_confidence_score_out_of_range(self) -> None:
        with pytest.raises(ValidationError):
            _make_outcome(confidence_score=1.5)

    def test_negative_periods_elapsed_fails(self) -> None:
        with pytest.raises(ValidationError):
            _make_outcome(periods_elapsed=-1)


# ---------------------------------------------------------------------------
# LabelVersion tests
# ---------------------------------------------------------------------------

class TestLabelVersion:
    def test_valid_version(self) -> None:
        v = LabelVersion(version="1.0.0")
        assert v.version == "1.0.0"

    def test_invalid_version_format(self) -> None:
        with pytest.raises(ValidationError):
            LabelVersion(version="1.0")

    def test_bump_major(self) -> None:
        v = LabelVersion(version="1.2.3")
        bumped = v.bump_major()
        assert bumped.version == "2.0.0"

    def test_bump_minor(self) -> None:
        v = LabelVersion(version="1.2.3")
        bumped = v.bump_minor()
        assert bumped.version == "1.3.0"

    def test_bump_patch(self) -> None:
        v = LabelVersion(version="1.2.3")
        bumped = v.bump_patch()
        assert bumped.version == "1.2.4"


# ---------------------------------------------------------------------------
# LabelContract tests
# ---------------------------------------------------------------------------

class TestLabelContract:
    def test_default_contract(self) -> None:
        contract = LabelContract(version="1.0.0", description="Test")
        assert contract.require_enrollment_record is True
        assert contract.require_period_certification is True
        assert contract.treat_graduation_as_dropout is False
        assert contract.treat_transfer_as_dropout is False

    def test_resolve_none_reason(self) -> None:
        contract = LabelContract(version="1.0.0", description="Test")
        assert contract.resolve_exit_reason(None) == ExitReason.NOT_REPORTED

    def test_resolve_graduation_variants(self) -> None:
        contract = LabelContract(version="1.0.0", description="Test")
        assert contract.resolve_exit_reason("graduado") == ExitReason.GRADUATED
        assert contract.resolve_exit_reason("Graduated") == ExitReason.GRADUATED
        assert contract.resolve_exit_reason("egresado") == ExitReason.GRADUATED

    def test_resolve_transfer_variants(self) -> None:
        contract = LabelContract(version="1.0.0", description="Test")
        assert contract.resolve_exit_reason("transferencia") == ExitReason.TRANSFERRED
        assert contract.resolve_exit_reason("traslado") == ExitReason.TRANSFERRED

    def test_resolve_unknown_reason(self) -> None:
        contract = LabelContract(version="1.0.0", description="Test")
        assert contract.resolve_exit_reason("some_unknown_reason") == ExitReason.NOT_REPORTED

    def test_is_dropout_exit_voluntary(self) -> None:
        contract = LabelContract(version="1.0.0", description="Test")
        assert contract.is_dropout_exit(ExitReason.VOLUNTARY_WITHDRAWAL) is True

    def test_is_dropout_exit_graduation_default(self) -> None:
        contract = LabelContract(version="1.0.0", description="Test")
        assert contract.is_dropout_exit(ExitReason.GRADUATED) is False

    def test_is_dropout_exit_graduation_custom(self) -> None:
        contract = LabelContract(
            version="1.0.0",
            description="Test",
            treat_graduation_as_dropout=True,
        )
        assert contract.is_dropout_exit(ExitReason.GRADUATED) is True

    def test_is_dropout_exit_transfer_default(self) -> None:
        contract = LabelContract(version="1.0.0", description="Test")
        assert contract.is_dropout_exit(ExitReason.TRANSFERRED) is False

    def test_is_dropout_exit_transfer_custom(self) -> None:
        contract = LabelContract(
            version="1.0.0",
            description="Test",
            treat_transfer_as_dropout=True,
        )
        assert contract.is_dropout_exit(ExitReason.TRANSFERRED) is True

    def test_is_dropout_exit_authorized_leave_default(self) -> None:
        contract = LabelContract(version="1.0.0", description="Test")
        assert contract.is_dropout_exit(ExitReason.AUTHORIZED_LEAVE) is False

    def test_is_dropout_exit_academic(self) -> None:
        contract = LabelContract(version="1.0.0", description="Test")
        assert contract.is_dropout_exit(ExitReason.ACADEMIC_DISMISSMENT) is True

    def test_is_dropout_exit_administrative(self) -> None:
        contract = LabelContract(version="1.0.0", description="Test")
        assert contract.is_dropout_exit(ExitReason.ADMINISTRATIVE) is True

    def test_is_dropout_exit_not_reported(self) -> None:
        contract = LabelContract(version="1.0.0", description="Test")
        assert contract.is_dropout_exit(ExitReason.NOT_REPORTED) is True

    def test_is_dropout_exit_none(self) -> None:
        contract = LabelContract(version="1.0.0", description="Test")
        assert contract.is_dropout_exit(ExitReason.NONE) is False

    def test_is_dropout_exit_deceased(self) -> None:
        contract = LabelContract(version="1.0.0", description="Test")
        assert contract.is_dropout_exit(ExitReason.DECEASED) is False


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_unicode_student_id(self) -> None:
        outcome = _make_outcome(student_id="EST-2024-Ñ")
        assert outcome.student_id == "EST-2024-Ñ"

    def test_unicode_period(self) -> None:
        outcome = _make_outcome(
            reference_period="2024-I",
            observation_period="2024-II",
        )
        assert outcome.reference_period == "2024-I"

    def test_low_confidence_dropout(self) -> None:
        outcome = _make_outcome(
            status=OutcomeStatus.DROPPED_OUT,
            exit_reason=ExitReason.NOT_REPORTED,
            censorship_type=CensorshipType.OBSERVED,
            confidence_score=0.3,
        )
        assert outcome.confidence_score == 0.3

    def test_zero_confidence_unknown(self) -> None:
        outcome = _make_outcome(
            status=OutcomeStatus.UNKNOWN,
            exit_reason=ExitReason.NOT_REPORTED,
            censorship_type=CensorshipType.NOT_CENSORABLE,
            confidence_score=0.0,
        )
        assert outcome.confidence_score == 0.0

    def test_custom_calendar(self) -> None:
        outcome = _make_outcome(calendar_type=AcademicCalendar.CUSTOM)
        assert outcome.calendar_type == AcademicCalendar.CUSTOM
