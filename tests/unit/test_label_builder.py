"""Tests for the Label Builder.

Comprehensive test suite covering:
- Basic continuation/dropout/pending/unknown outcomes
- Exit reason resolution and classification
- Period closure rules
- Filtering (institution, period, date range)
- Idempotency
- Report generation
- Edge cases
"""

from datetime import datetime

from leo_risk.contracts.core import AcademicPeriod
from leo_risk.contracts.enrollment import Enrollment, EnrollmentStatus
from leo_risk.domain.builder import LabelBuilder
from leo_risk.domain.censorship import CensorshipType
from leo_risk.domain.enums import OutcomeStatus
from leo_risk.domain.exit_reason import ExitReason
from leo_risk.domain.label_contract import LabelContract
from leo_risk.domain.label_version import LabelVersion

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _period(
    period_id: str,
    institution_id: str = "inst-1",
    code: str | None = None,
    start_date: str = "2026-01-01",
    end_date: str = "2026-06-30",
    is_closed: bool = True,
    calendar_type: str = "semester",
) -> AcademicPeriod:
    return AcademicPeriod(
        period_id=period_id,
        institution_id=institution_id,
        code=code or period_id,
        calendar_type=calendar_type,
        start_date=start_date,
        end_date=end_date,
        is_closed=is_closed,
    )


def _enrollment(
    enrollment_id: str,
    student_id: str,
    period_id: str,
    institution_id: str = "inst-1",
    program_id: str = "prog-1",
    status: EnrollmentStatus = EnrollmentStatus.ENROLLED,
    is_active: bool = True,
    exit_reason: str | None = None,
) -> Enrollment:
    now = datetime(2026, 1, 1, tzinfo=None)
    return Enrollment(
        enrollment_id=enrollment_id,
        student_id=student_id,
        institution_id=institution_id,
        program_id=program_id,
        period_id=period_id,
        status=status,
        is_active=is_active,
        exit_reason=exit_reason,
        observed_at=now,
        available_at=now,
        source_system="test",
    )


# ---------------------------------------------------------------------------
# Test: Basic Continuation
# ---------------------------------------------------------------------------

class TestBasicContinuation:
    def test_student_continues_next_period(self) -> None:
        """Student enrolled in T and T+1 (closed) → CONTINUED."""
        periods = [
            _period("T", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T1", start_date="2026-07-01", end_date="2026-12-31"),
        ]
        enrollments = [
            _enrollment("e1", "s1", "T"),
            _enrollment("e2", "s1", "T1"),
        ]

        builder = LabelBuilder()
        result = builder.run(enrollments, periods)

        assert len(result) == 1
        outcome = result[0]
        assert outcome.status == OutcomeStatus.CONTINUED
        assert outcome.exit_reason == ExitReason.NONE
        assert outcome.censorship_type == CensorshipType.RIGHT_CENSORED

    def test_student_continues_multiple_periods(self) -> None:
        """Student enrolled in T, T+1, T+2 (all closed) → two CONTINUED."""
        periods = [
            _period("T", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T1", start_date="2026-07-01", end_date="2026-12-31"),
            _period("T2", start_date="2027-01-01", end_date="2027-06-30"),
        ]
        enrollments = [
            _enrollment("e1", "s1", "T"),
            _enrollment("e2", "s1", "T1"),
            _enrollment("e3", "s1", "T2"),
        ]

        builder = LabelBuilder()
        result = builder.run(enrollments, periods)

        assert len(result) == 2
        assert all(o.status == OutcomeStatus.CONTINUED for o in result)


# ---------------------------------------------------------------------------
# Test: Dropout
# ---------------------------------------------------------------------------

class TestDropout:
    def test_dropout_voluntary_withdrawal(self) -> None:
        """Student enrolled in T, not in T+1 (closed), exit_reason=withdrawal → DROPPED_OUT."""
        periods = [
            _period("T", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T1", start_date="2026-07-01", end_date="2026-12-31"),
        ]
        enrollments = [
            _enrollment("e1", "s1", "T", exit_reason="withdrawal"),
        ]

        builder = LabelBuilder()
        result = builder.run(enrollments, periods)

        assert len(result) == 1
        outcome = result[0]
        assert outcome.status == OutcomeStatus.DROPPED_OUT
        assert outcome.exit_reason == ExitReason.VOLUNTARY_WITHDRAWAL
        assert outcome.censorship_type == CensorshipType.OBSERVED

    def test_dropout_academic_dismissal(self) -> None:
        """Student with academic_dismissal exit → DROPPED_OUT."""
        periods = [
            _period("T", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T1", start_date="2026-07-01", end_date="2026-12-31"),
        ]
        enrollments = [
            _enrollment("e1", "s1", "T", exit_reason="academic_dismissal"),
        ]

        builder = LabelBuilder()
        result = builder.run(enrollments, periods)

        assert result[0].status == OutcomeStatus.DROPPED_OUT
        assert result[0].exit_reason == ExitReason.ACADEMIC_DISMISSMENT

    def test_dropout_administrative(self) -> None:
        """Student with administrative exit → DROPPED_OUT."""
        periods = [
            _period("T", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T1", start_date="2026-07-01", end_date="2026-12-31"),
        ]
        enrollments = [
            _enrollment("e1", "s1", "T", exit_reason="administrative"),
        ]

        builder = LabelBuilder()
        result = builder.run(enrollments, periods)

        assert result[0].status == OutcomeStatus.DROPPED_OUT
        assert result[0].exit_reason == ExitReason.ADMINISTRATIVE

    def test_dropout_not_reported(self) -> None:
        """Student with no exit reason → DROPPED_OUT (NOT_REPORTED counts as dropout)."""
        periods = [
            _period("T", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T1", start_date="2026-07-01", end_date="2026-12-31"),
        ]
        enrollments = [
            _enrollment("e1", "s1", "T", exit_reason=None),
        ]

        builder = LabelBuilder()
        result = builder.run(enrollments, periods)

        assert result[0].status == OutcomeStatus.DROPPED_OUT
        assert result[0].exit_reason == ExitReason.NOT_REPORTED


# ---------------------------------------------------------------------------
# Test: Non-Dropout Exits
# ---------------------------------------------------------------------------

class TestNonDropoutExits:
    def test_graduation(self) -> None:
        """Student with graduation exit → UNKNOWN (not dropout by default)."""
        periods = [
            _period("T", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T1", start_date="2026-07-01", end_date="2026-12-31"),
        ]
        enrollments = [
            _enrollment("e1", "s1", "T", exit_reason="graduated"),
        ]

        builder = LabelBuilder()
        result = builder.run(enrollments, periods)

        assert result[0].status == OutcomeStatus.UNKNOWN
        assert result[0].exit_reason == ExitReason.NOT_REPORTED
        assert result[0].censorship_type == CensorshipType.NOT_CENSORABLE

    def test_graduation_treated_as_dropout(self) -> None:
        """With contract flag, graduation → DROPPED_OUT."""
        contract = LabelContract(
            version="1.0.0",
            description="Test",
            treat_graduation_as_dropout=True,
        )
        periods = [
            _period("T", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T1", start_date="2026-07-01", end_date="2026-12-31"),
        ]
        enrollments = [
            _enrollment("e1", "s1", "T", exit_reason="graduated"),
        ]

        builder = LabelBuilder(contract=contract)
        result = builder.run(enrollments, periods)

        assert result[0].status == OutcomeStatus.DROPPED_OUT
        assert result[0].exit_reason == ExitReason.GRADUATED

    def test_transfer(self) -> None:
        """Student with transfer exit → UNKNOWN (not dropout by default)."""
        periods = [
            _period("T", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T1", start_date="2026-07-01", end_date="2026-12-31"),
        ]
        enrollments = [
            _enrollment("e1", "s1", "T", exit_reason="transferred"),
        ]

        builder = LabelBuilder()
        result = builder.run(enrollments, periods)

        assert result[0].status == OutcomeStatus.UNKNOWN

    def test_authorized_leave(self) -> None:
        """Student with authorized leave → UNKNOWN (not dropout by default)."""
        periods = [
            _period("T", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T1", start_date="2026-07-01", end_date="2026-12-31"),
        ]
        enrollments = [
            _enrollment("e1", "s1", "T", exit_reason="authorized_leave"),
        ]

        builder = LabelBuilder()
        result = builder.run(enrollments, periods)

        assert result[0].status == OutcomeStatus.UNKNOWN


# ---------------------------------------------------------------------------
# Test: Pending
# ---------------------------------------------------------------------------

class TestPending:
    def test_pending_period_not_closed(self) -> None:
        """Student enrolled in T, T+1 not closed → PENDING."""
        periods = [
            _period("T", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T1", start_date="2026-07-01", end_date="2026-12-31", is_closed=False),
        ]
        enrollments = [
            _enrollment("e1", "s1", "T"),
            _enrollment("e2", "s1", "T1"),
        ]

        builder = LabelBuilder()
        result = builder.run(enrollments, periods)

        assert len(result) == 1
        assert result[0].status == OutcomeStatus.PENDING
        assert result[0].censorship_type == CensorshipType.NOT_CENSORABLE

    def test_pending_not_enrolled_next_period(self) -> None:
        """Student enrolled in T, not in T+1 (not closed) → PENDING."""
        periods = [
            _period("T", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T1", start_date="2026-07-01", end_date="2026-12-31", is_closed=False),
        ]
        enrollments = [
            _enrollment("e1", "s1", "T"),
        ]

        builder = LabelBuilder()
        result = builder.run(enrollments, periods)

        assert result[0].status == OutcomeStatus.PENDING


# ---------------------------------------------------------------------------
# Test: Filtering
# ---------------------------------------------------------------------------

class TestFiltering:
    def test_filter_by_institution(self) -> None:
        """Only process enrollments from the specified institution."""
        periods = [
            _period("T", institution_id="inst-1", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T1", institution_id="inst-1", start_date="2026-07-01", end_date="2026-12-31"),
            _period("T", institution_id="inst-2", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T1", institution_id="inst-2", start_date="2026-07-01", end_date="2026-12-31"),
        ]
        enrollments = [
            _enrollment("e1", "s1", "T", institution_id="inst-1"),
            _enrollment("e2", "s1", "T1", institution_id="inst-1"),
            _enrollment("e3", "s2", "T", institution_id="inst-2"),
            _enrollment("e4", "s2", "T1", institution_id="inst-2"),
        ]

        builder = LabelBuilder()
        result = builder.run(enrollments, periods, institution_id="inst-1")

        assert len(result) == 1
        assert result[0].institution_id == "inst-1"

    def test_filter_by_period(self) -> None:
        """Only process the specified reference periods."""
        periods = [
            _period("T", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T1", start_date="2026-07-01", end_date="2026-12-31"),
            _period("T2", start_date="2027-01-01", end_date="2027-06-30"),
        ]
        enrollments = [
            _enrollment("e1", "s1", "T"),
            _enrollment("e2", "s1", "T1"),
            _enrollment("e3", "s1", "T2"),
        ]

        builder = LabelBuilder()
        result = builder.run(enrollments, periods, period_ids=["T"])

        assert len(result) == 1
        assert result[0].reference_period == "T"

    def test_filter_by_date_range(self) -> None:
        """Only process periods within the specified date range."""
        periods = [
            _period("T", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T1", start_date="2026-07-01", end_date="2026-12-31"),
            _period("T2", start_date="2027-01-01", end_date="2027-06-30"),
        ]
        enrollments = [
            _enrollment("e1", "s1", "T"),
            _enrollment("e2", "s1", "T1"),
            _enrollment("e3", "s1", "T2"),
        ]

        builder = LabelBuilder()
        result = builder.run(
            enrollments,
            periods,
            date_range=(
                datetime(2026, 1, 1),
                datetime(2026, 12, 31),
            ),
        )

        # T is within range, T1 starts within range → 2 outcomes
        assert len(result) == 2

    def test_filter_combined(self) -> None:
        """Combine institution and period filters."""
        periods = [
            _period("T", institution_id="inst-1", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T1", institution_id="inst-1", start_date="2026-07-01", end_date="2026-12-31"),
            _period("T", institution_id="inst-2", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T1", institution_id="inst-2", start_date="2026-07-01", end_date="2026-12-31"),
        ]
        enrollments = [
            _enrollment("e1", "s1", "T", institution_id="inst-1"),
            _enrollment("e2", "s1", "T1", institution_id="inst-1"),
            _enrollment("e3", "s2", "T", institution_id="inst-2"),
            _enrollment("e4", "s2", "T1", institution_id="inst-2"),
        ]

        builder = LabelBuilder()
        result = builder.run(
            enrollments,
            periods,
            institution_id="inst-1",
            period_ids=["T"],
        )

        assert len(result) == 1
        assert result[0].institution_id == "inst-1"
        assert result[0].reference_period == "T"


# ---------------------------------------------------------------------------
# Test: as_of Cutoff
# ---------------------------------------------------------------------------

class TestAsOf:
    def test_as_of_before_period_end(self) -> None:
        """Period not closed but as_of after end_date → treated as closed."""
        periods = [
            _period("T", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T1", start_date="2026-07-01", end_date="2026-12-31", is_closed=False),
        ]
        enrollments = [
            _enrollment("e1", "s1", "T"),
            _enrollment("e2", "s1", "T1"),
        ]

        builder = LabelBuilder()
        # as_of is after T1 end_date, so T1 is effectively closed
        result = builder.run(
            enrollments,
            periods,
            as_of=datetime(2027, 1, 1),
        )

        assert result[0].status == OutcomeStatus.CONTINUED

    def test_as_of_before_period_end_dropout(self) -> None:
        """Period not closed but as_of after end_date, no enrollment → DROPPED_OUT."""
        periods = [
            _period("T", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T1", start_date="2026-07-01", end_date="2026-12-31", is_closed=False),
        ]
        enrollments = [
            _enrollment("e1", "s1", "T", exit_reason="withdrawal"),
        ]

        builder = LabelBuilder()
        result = builder.run(
            enrollments,
            periods,
            as_of=datetime(2027, 1, 1),
        )

        assert result[0].status == OutcomeStatus.DROPPED_OUT


# ---------------------------------------------------------------------------
# Test: Idempotency
# ---------------------------------------------------------------------------

class TestIdempotency:
    def test_same_input_same_output(self) -> None:
        """Running the builder twice with same input produces identical output."""
        periods = [
            _period("T", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T1", start_date="2026-07-01", end_date="2026-12-31"),
        ]
        enrollments = [
            _enrollment("e1", "s1", "T"),
            _enrollment("e2", "s1", "T1"),
        ]

        builder = LabelBuilder()
        result1 = builder.run(enrollments, periods)
        result2 = builder.run(enrollments, periods)

        assert len(result1) == len(result2)
        for o1, o2 in zip(result1, result2, strict=True):
            assert o1.student_id == o2.student_id
            assert o1.reference_period == o2.reference_period
            assert o1.observation_period == o2.observation_period
            assert o1.status == o2.status
            assert o1.exit_reason == o2.exit_reason
            assert o1.censorship_type == o2.censorship_type

    def test_order_independence(self) -> None:
        """Enrollment order doesn't affect output."""
        periods = [
            _period("T", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T1", start_date="2026-07-01", end_date="2026-12-31"),
        ]
        enrollments_forward = [
            _enrollment("e1", "s1", "T"),
            _enrollment("e2", "s1", "T1"),
        ]
        enrollments_reverse = [
            _enrollment("e2", "s1", "T1"),
            _enrollment("e1", "s1", "T"),
        ]

        builder = LabelBuilder()
        result_forward = builder.run(enrollments_forward, periods)
        result_reverse = builder.run(enrollments_reverse, periods)

        assert len(result_forward) == len(result_reverse)
        for o1, o2 in zip(result_forward, result_reverse, strict=True):
            assert o1.status == o2.status
            assert o1.exit_reason == o2.exit_reason


# ---------------------------------------------------------------------------
# Test: Report
# ---------------------------------------------------------------------------

class TestReport:
    def test_report_counts(self) -> None:
        """Report correctly counts outcomes by status."""
        periods = [
            _period("T", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T1", start_date="2026-07-01", end_date="2026-12-31"),
        ]
        enrollments = [
            # s1: continues
            _enrollment("e1", "s1", "T"),
            _enrollment("e2", "s1", "T1"),
            # s2: dropout
            _enrollment("e3", "s2", "T", exit_reason="withdrawal"),
            # s3: graduation (unknown)
            _enrollment("e4", "s3", "T", exit_reason="graduated"),
        ]

        builder = LabelBuilder()
        result = builder.run(enrollments, periods)

        report = result.report
        assert report.total_pairs == 3
        assert report.counts_by_status["continued"] == 1
        assert report.counts_by_status["dropped_out"] == 1
        assert report.counts_by_status["unknown"] == 1
        assert report.usable_for_classification == 2
        assert report.excluded_from_ml == 1

    def test_report_utilization_rates(self) -> None:
        """Report computes correct utilization rates."""
        periods = [
            _period("T", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T1", start_date="2026-07-01", end_date="2026-12-31", is_closed=False),
        ]
        enrollments = [
            _enrollment("e1", "s1", "T"),
            _enrollment("e2", "s1", "T1"),
        ]

        builder = LabelBuilder()
        result = builder.run(enrollments, periods)

        report = result.report
        assert report.utilization_rate_survival == 0.0
        assert report.utilization_rate_classification == 0.0

    def test_report_summary_output(self) -> None:
        """Report summary() produces a non-empty string."""
        periods = [
            _period("T", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T1", start_date="2026-07-01", end_date="2026-12-31"),
        ]
        enrollments = [
            _enrollment("e1", "s1", "T"),
            _enrollment("e2", "s1", "T1"),
        ]

        builder = LabelBuilder()
        result = builder.run(enrollments, periods)

        summary = result.report.summary()
        assert "Label Build Report" in summary
        assert "Total pairs: 1" in summary

    def test_report_institution_count(self) -> None:
        """Report tracks unique institutions."""
        periods = [
            _period("T", institution_id="inst-1", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T1", institution_id="inst-1", start_date="2026-07-01", end_date="2026-12-31"),
            _period("T", institution_id="inst-2", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T1", institution_id="inst-2", start_date="2026-07-01", end_date="2026-12-31"),
        ]
        enrollments = [
            _enrollment("e1", "s1", "T", institution_id="inst-1"),
            _enrollment("e2", "s1", "T1", institution_id="inst-1"),
            _enrollment("e3", "s2", "T", institution_id="inst-2"),
            _enrollment("e4", "s2", "T1", institution_id="inst-2"),
        ]

        builder = LabelBuilder()
        result = builder.run(enrollments, periods)

        assert result.report.institutions_processed == 2
        assert result.report.students_processed == 2


# ---------------------------------------------------------------------------
# Test: Multiple Students
# ---------------------------------------------------------------------------

class TestMultipleStudents:
    def test_multiple_students_independent(self) -> None:
        """Each student's outcome is computed independently."""
        periods = [
            _period("T", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T1", start_date="2026-07-01", end_date="2026-12-31"),
        ]
        enrollments = [
            _enrollment("e1", "s1", "T"),
            _enrollment("e2", "s1", "T1"),  # s1 continues
            _enrollment("e3", "s2", "T", exit_reason="withdrawal"),  # s2 drops out
        ]

        builder = LabelBuilder()
        result = builder.run(enrollments, periods)

        outcomes_by_student = {o.student_id: o for o in result}
        assert outcomes_by_student["s1"].status == OutcomeStatus.CONTINUED
        assert outcomes_by_student["s2"].status == OutcomeStatus.DROPPED_OUT

    def test_multiple_programs(self) -> None:
        """Student enrolled in multiple programs gets separate outcomes."""
        periods = [
            _period("T", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T1", start_date="2026-07-01", end_date="2026-12-31"),
        ]
        enrollments = [
            _enrollment("e1", "s1", "T", program_id="prog-1"),
            _enrollment("e2", "s1", "T1", program_id="prog-1"),
            _enrollment("e3", "s1", "T", program_id="prog-2"),
            # No enrollment in prog-2 for T1 → dropout in prog-2
        ]

        builder = LabelBuilder()
        result = builder.run(enrollments, periods)

        outcomes_by_program = {o.program_id: o for o in result}
        assert outcomes_by_program["prog-1"].status == OutcomeStatus.CONTINUED
        assert outcomes_by_program["prog-2"].status == OutcomeStatus.DROPPED_OUT


# ---------------------------------------------------------------------------
# Test: Edge Cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_enrollments(self) -> None:
        """No enrollments → no outcomes."""
        periods = [
            _period("T", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T1", start_date="2026-07-01", end_date="2026-12-31"),
        ]

        builder = LabelBuilder()
        result = builder.run([], periods)

        assert len(result) == 0
        assert result.report.total_pairs == 0

    def test_empty_periods(self) -> None:
        """No periods → no outcomes."""
        enrollments = [
            _enrollment("e1", "s1", "T"),
        ]

        builder = LabelBuilder()
        result = builder.run(enrollments, [])

        assert len(result) == 0

    def test_single_period(self) -> None:
        """Only one period → no consecutive pairs → no outcomes."""
        periods = [
            _period("T", start_date="2026-01-01", end_date="2026-06-30"),
        ]
        enrollments = [
            _enrollment("e1", "s1", "T"),
        ]

        builder = LabelBuilder()
        result = builder.run(enrollments, periods)

        assert len(result) == 0

    def test_student_enrolled_in_non_adjacent_periods(self) -> None:
        """Student skips a period → only one outcome for the pair that exists."""
        periods = [
            _period("T", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T1", start_date="2026-07-01", end_date="2026-12-31"),
            _period("T2", start_date="2027-01-01", end_date="2027-06-30"),
        ]
        enrollments = [
            _enrollment("e1", "s1", "T"),
            # No enrollment in T1
            _enrollment("e2", "s1", "T2"),
        ]

        builder = LabelBuilder()
        result = builder.run(enrollments, periods)

        # T → T1: no enrollment in T1, T1 closed → DROPPED_OUT
        assert len(result) == 1
        assert result[0].reference_period == "T"
        assert result[0].observation_period == "T1"
        assert result[0].status == OutcomeStatus.DROPPED_OUT

    def test_no_next_period(self) -> None:
        """Last period has no next period → no outcome generated."""
        periods = [
            _period("T", start_date="2026-01-01", end_date="2026-06-30"),
        ]
        enrollments = [
            _enrollment("e1", "s1", "T"),
        ]

        builder = LabelBuilder()
        result = builder.run(enrollments, periods)

        assert len(result) == 0


# ---------------------------------------------------------------------------
# Test: LabelVersion and Contract
# ---------------------------------------------------------------------------

class TestVersionAndContract:
    def test_custom_version(self) -> None:
        """Builder attaches the specified version to the result."""
        version = LabelVersion(version="2.1.0", description="Test version")
        builder = LabelBuilder(version=version)
        periods = [
            _period("T", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T1", start_date="2026-07-01", end_date="2026-12-31"),
        ]
        enrollments = [_enrollment("e1", "s1", "T")]

        result = builder.run(enrollments, periods)

        assert result.version.version == "2.1.0"

    def test_custom_contract(self) -> None:
        """Builder uses the specified contract for exit reason resolution."""
        contract = LabelContract(
            version="1.0.0",
            description="Test",
            treat_graduation_as_dropout=True,
            treat_transfer_as_dropout=True,
        )
        builder = LabelBuilder(contract=contract)
        periods = [
            _period("T", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T1", start_date="2026-07-01", end_date="2026-12-31"),
        ]
        enrollments = [
            _enrollment("e1", "s1", "T", exit_reason="graduated"),
            _enrollment("e2", "s2", "T", exit_reason="transferred"),
        ]

        result = builder.run(enrollments, periods)

        outcomes_by_student = {o.student_id: o for o in result}
        assert outcomes_by_student["s1"].status == OutcomeStatus.DROPPED_OUT
        assert outcomes_by_student["s1"].exit_reason == ExitReason.GRADUATED
        assert outcomes_by_student["s2"].status == OutcomeStatus.DROPPED_OUT
        assert outcomes_by_student["s2"].exit_reason == ExitReason.TRANSFERRED


# ---------------------------------------------------------------------------
# Test: Exit Reason Resolution
# ---------------------------------------------------------------------------

class TestExitReasonResolution:
    def test_spanish_exit_reasons(self) -> None:
        """Spanish exit reason strings are correctly resolved."""
        contract = LabelContract(version="1.0.0", description="Test")
        assert contract.resolve_exit_reason("retiro_voluntario") == ExitReason.VOLUNTARY_WITHDRAWAL
        assert contract.resolve_exit_reason("cancelacion_academica") == ExitReason.ACADEMIC_DISMISSMENT
        assert contract.resolve_exit_reason("administrativo") == ExitReason.ADMINISTRATIVE
        assert contract.resolve_exit_reason("graduado") == ExitReason.GRADUATED
        assert contract.resolve_exit_reason("fallecido") == ExitReason.DECEASED

    def test_english_exit_reasons(self) -> None:
        """English exit reason strings are correctly resolved."""
        contract = LabelContract(version="1.0.0", description="Test")
        assert contract.resolve_exit_reason("voluntary_withdrawal") == ExitReason.VOLUNTARY_WITHDRAWAL
        assert contract.resolve_exit_reason("academic_dismissal") == ExitReason.ACADEMIC_DISMISSMENT
        assert contract.resolve_exit_reason("graduated") == ExitReason.GRADUATED
        assert contract.resolve_exit_reason("transferred") == ExitReason.TRANSFERRED

    def test_unknown_exit_reason(self) -> None:
        """Unknown exit reason → NOT_REPORTED."""
        contract = LabelContract(version="1.0.0", description="Test")
        assert contract.resolve_exit_reason("something_unknown") == ExitReason.NOT_REPORTED

    def test_none_exit_reason(self) -> None:
        """None exit reason → NOT_REPORTED."""
        contract = LabelContract(version="1.0.0", description="Test")
        assert contract.resolve_exit_reason(None) == ExitReason.NOT_REPORTED


# ---------------------------------------------------------------------------
# Test: Censorship Classification
# ---------------------------------------------------------------------------

class TestCensorship:
    def test_continued_is_right_censored(self) -> None:
        """CONTINUED outcome → RIGHT_CENSORED."""
        periods = [
            _period("T", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T1", start_date="2026-07-01", end_date="2026-12-31"),
        ]
        enrollments = [
            _enrollment("e1", "s1", "T"),
            _enrollment("e2", "s1", "T1"),
        ]

        builder = LabelBuilder()
        result = builder.run(enrollments, periods)

        assert result[0].censorship_type == CensorshipType.RIGHT_CENSORED

    def test_dropout_is_observed(self) -> None:
        """DROPPED_OUT outcome → OBSERVED."""
        periods = [
            _period("T", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T1", start_date="2026-07-01", end_date="2026-12-31"),
        ]
        enrollments = [
            _enrollment("e1", "s1", "T", exit_reason="withdrawal"),
        ]

        builder = LabelBuilder()
        result = builder.run(enrollments, periods)

        assert result[0].censorship_type == CensorshipType.OBSERVED

    def test_pending_is_not_censorable(self) -> None:
        """PENDING outcome → NOT_CENSORABLE."""
        periods = [
            _period("T", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T1", start_date="2026-07-01", end_date="2026-12-31", is_closed=False),
        ]
        enrollments = [
            _enrollment("e1", "s1", "T"),
            _enrollment("e2", "s1", "T1"),
        ]

        builder = LabelBuilder()
        result = builder.run(enrollments, periods)

        assert result[0].censorship_type == CensorshipType.NOT_CENSORABLE

    def test_unknown_is_not_censorable(self) -> None:
        """UNKNOWN outcome → NOT_CENSORABLE."""
        periods = [
            _period("T", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T1", start_date="2026-07-01", end_date="2026-12-31"),
        ]
        enrollments = [
            _enrollment("e1", "s1", "T", exit_reason="graduated"),
        ]

        builder = LabelBuilder()
        result = builder.run(enrollments, periods)

        assert result[0].censorship_type == CensorshipType.NOT_CENSORABLE


# ---------------------------------------------------------------------------
# Test: Result API
# ---------------------------------------------------------------------------

class TestResultAPI:
    def test_result_len(self) -> None:
        """LabelBuildResult.__len__ returns the number of outcomes."""
        periods = [
            _period("T", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T1", start_date="2026-07-01", end_date="2026-12-31"),
        ]
        enrollments = [
            _enrollment("e1", "s1", "T"),
            _enrollment("e2", "s1", "T1"),
        ]

        builder = LabelBuilder()
        result = builder.run(enrollments, periods)

        assert len(result) == 1

    def test_result_iteration(self) -> None:
        """LabelBuildResult is iterable."""
        periods = [
            _period("T", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T1", start_date="2026-07-01", end_date="2026-12-31"),
        ]
        enrollments = [
            _enrollment("e1", "s1", "T"),
            _enrollment("e2", "s1", "T1"),
        ]

        builder = LabelBuilder()
        result = builder.run(enrollments, periods)

        for outcome in result:
            assert outcome.status == OutcomeStatus.CONTINUED

    def test_result_indexing(self) -> None:
        """LabelBuildResult supports indexing."""
        periods = [
            _period("T", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T1", start_date="2026-07-01", end_date="2026-12-31"),
        ]
        enrollments = [
            _enrollment("e1", "s1", "T"),
            _enrollment("e2", "s1", "T1"),
        ]

        builder = LabelBuilder()
        result = builder.run(enrollments, periods)

        assert result[0].status == OutcomeStatus.CONTINUED
