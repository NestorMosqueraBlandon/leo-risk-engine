"""Tests for the Data Auditor.

Covers:
- Basic audit with no data
- Per-institution metrics
- Coverage calculations
- Outcome counting
- Dropout rate
- Temporal depth
- Event counting
- JSON export
- CSV export
- Console output
"""

from datetime import datetime

import pytest

from leo_risk.contracts.core import AcademicPeriod
from leo_risk.contracts.enrollment import Enrollment, EnrollmentStatus
from leo_risk.contracts.interventions import Intervention, InterventionType
from leo_risk.contracts.observations import (
    AttendanceObservation,
    AttendanceStatus,
    FinancialStatus,
    FinancialStatusRecord,
    GradeObservation,
)
from leo_risk.contracts.support import EngagementEvent, EngagementEventType, StudentSupport, SupportType
from leo_risk.domain.audit import DataAuditor, export_csv, export_json
from leo_risk.domain.builder import LabelBuilder
from leo_risk.domain.censorship import CensorshipType
from leo_risk.domain.enums import OutcomeStatus
from leo_risk.domain.exit_reason import ExitReason

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

NOW = datetime(2026, 1, 1)


def _period(
    period_id: str,
    institution_id: str = "inst-1",
    start_date: str = "2026-01-01",
    end_date: str = "2026-06-30",
    is_closed: bool = True,
) -> AcademicPeriod:
    return AcademicPeriod(
        period_id=period_id,
        institution_id=institution_id,
        code=period_id,
        calendar_type="semester",
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
    exit_reason: str | None = None,
) -> Enrollment:
    return Enrollment(
        enrollment_id=enrollment_id,
        student_id=student_id,
        institution_id=institution_id,
        program_id=program_id,
        period_id=period_id,
        status=EnrollmentStatus.ENROLLED,
        is_active=True,
        exit_reason=exit_reason,
        observed_at=NOW,
        available_at=NOW,
        source_system="test",
    )


def _outcome(
    student_id: str,
    institution_id: str,
    reference_period: str,
    observation_period: str,
    status: OutcomeStatus,
    exit_reason: ExitReason = ExitReason.NONE,
):
    from leo_risk.domain.entities.student_outcome import StudentOutcome

    # DROPPED_OUT needs a real exit reason
    if status == OutcomeStatus.DROPPED_OUT and exit_reason == ExitReason.NONE:
        exit_reason = ExitReason.NOT_REPORTED

    return StudentOutcome(
        student_id=student_id,
        institution_id=institution_id,
        program_id="prog-1",
        reference_period=reference_period,
        observation_period=observation_period,
        status=status,
        exit_reason=exit_reason,
        censorship_type=(
            CensorshipType.OBSERVED
            if status == OutcomeStatus.DROPPED_OUT
            else CensorshipType.RIGHT_CENSORED
            if status == OutcomeStatus.CONTINUED
            else CensorshipType.NOT_CENSORABLE
        ),
        calendar_type="semester",
    )


def _grade(
    observation_id: str,
    student_id: str,
    period_id: str,
    institution_id: str = "inst-1",
) -> GradeObservation:
    return GradeObservation(
        observation_id=observation_id,
        student_id=student_id,
        course_enrollment_id=f"ce-{observation_id}",
        period_id=period_id,
        grade_type="midterm",
        score=4.0,
        observed_at=NOW,
        available_at=NOW,
        source_system="test",
    )


def _attendance(
    observation_id: str,
    student_id: str,
    period_id: str,
    institution_id: str = "inst-1",
) -> AttendanceObservation:
    return AttendanceObservation(
        observation_id=observation_id,
        student_id=student_id,
        course_enrollment_id=f"ce-{observation_id}",
        period_id=period_id,
        session_date="2026-03-01",
        status=AttendanceStatus.PRESENT,
        observed_at=NOW,
        available_at=NOW,
        source_system="test",
    )


def _financial(
    observation_id: str,
    student_id: str,
    period_id: str,
    institution_id: str = "inst-1",
) -> FinancialStatusRecord:
    return FinancialStatusRecord(
        observation_id=observation_id,
        student_id=student_id,
        period_id=period_id,
        status=FinancialStatus.CURRENT,
        observed_at=NOW,
        available_at=NOW,
        source_system="test",
    )


def _engagement(
    event_id: str,
    student_id: str,
    period_id: str,
    institution_id: str = "inst-1",
) -> EngagementEvent:
    return EngagementEvent(
        event_id=event_id,
        student_id=student_id,
        period_id=period_id,
        event_type=EngagementEventType.LMS_LOGIN,
        observed_at=NOW,
        available_at=NOW,
        source_system="test",
    )


def _support(
    support_id: str,
    student_id: str,
    period_id: str,
    institution_id: str = "inst-1",
) -> StudentSupport:
    return StudentSupport(
        support_id=support_id,
        student_id=student_id,
        period_id=period_id,
        support_type=SupportType.TUTORING,
        observed_at=NOW,
        available_at=NOW,
        source_system="test",
    )


def _intervention(
    intervention_id: str,
    student_id: str,
    period_id: str,
    institution_id: str = "inst-1",
) -> Intervention:
    return Intervention(
        intervention_id=intervention_id,
        student_id=student_id,
        period_id=period_id,
        intervention_type=InterventionType.ADVISOR_OUTREACH,
        observed_at=NOW,
        available_at=NOW,
        source_system="test",
    )


# ---------------------------------------------------------------------------
# Test: Empty Data
# ---------------------------------------------------------------------------

class TestEmptyAudit:
    def test_empty_audit(self) -> None:
        """Audit with no data produces empty report."""
        auditor = DataAuditor()
        report = auditor.audit([], [], [])

        assert report.total_real_dropouts == 0
        assert report.total_usable_outcomes == 0
        assert report.total_excluded_outcomes == 0
        assert len(report.institutions) == 0
        assert report.aggregate.students_unique == 0

    def test_empty_summary(self) -> None:
        """Empty report produces valid summary string."""
        auditor = DataAuditor()
        report = auditor.audit([], [], [])

        summary = report.summary()
        assert "DATA AVAILABILITY AUDIT REPORT" in summary
        assert "Real observed dropouts for training: 0" in summary


# ---------------------------------------------------------------------------
# Test: Basic Counts
# ---------------------------------------------------------------------------

class TestBasicCounts:
    def test_students_and_snapshots(self) -> None:
        """Correctly counts students and snapshots."""
        periods = [
            _period("T1", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T2", start_date="2026-07-01", end_date="2026-12-31"),
        ]
        enrollments = [
            _enrollment("e1", "s1", "T1"),
            _enrollment("e2", "s1", "T2"),
            _enrollment("e3", "s2", "T1"),
        ]

        auditor = DataAuditor()
        report = auditor.audit(enrollments, periods, [])

        assert report.aggregate.students_unique == 2
        assert report.aggregate.snapshots == 3
        assert report.aggregate.periods == 2

    def test_cohorts(self) -> None:
        """Cohorts are (program, period) pairs."""
        periods = [_period("T1")]
        enrollments = [
            _enrollment("e1", "s1", "T1", program_id="prog-1"),
            _enrollment("e2", "s2", "T1", program_id="prog-1"),
            _enrollment("e3", "s3", "T1", program_id="prog-2"),
        ]

        auditor = DataAuditor()
        report = auditor.audit(enrollments, periods, [])

        assert report.aggregate.cohorts == 2  # prog-1/T1, prog-2/T1


# ---------------------------------------------------------------------------
# Test: Outcome Counting
# ---------------------------------------------------------------------------

class TestOutcomeCounting:
    def test_outcome_counts(self) -> None:
        """Correctly counts outcomes by status."""
        periods = [
            _period("T1", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T2", start_date="2026-07-01", end_date="2026-12-31"),
        ]
        enrollments = [
            _enrollment("e1", "s1", "T1"),
            _enrollment("e2", "s1", "T2"),
            _enrollment("e3", "s2", "T1", exit_reason="withdrawal"),
        ]
        outcomes = [
            _outcome("s1", "inst-1", "T1", "T2", OutcomeStatus.CONTINUED),
            _outcome("s2", "inst-1", "T1", "T2", OutcomeStatus.DROPPED_OUT, ExitReason.VOLUNTARY_WITHDRAWAL),
        ]

        auditor = DataAuditor()
        report = auditor.audit(enrollments, periods, outcomes)

        assert report.aggregate.outcomes_continued == 1
        assert report.aggregate.outcomes_dropped_out == 1
        assert report.total_real_dropouts == 1
        assert report.total_usable_outcomes == 2

    def test_pending_and_unknown(self) -> None:
        """Pending and unknown outcomes are counted separately."""
        outcomes = [
            _outcome("s1", "inst-1", "T1", "T2", OutcomeStatus.PENDING),
            _outcome("s2", "inst-1", "T1", "T2", OutcomeStatus.UNKNOWN),
        ]

        auditor = DataAuditor()
        report = auditor.audit([], [], outcomes)

        assert report.aggregate.outcomes_pending == 1
        assert report.aggregate.outcomes_unknown == 1
        assert report.total_excluded_outcomes == 2


# ---------------------------------------------------------------------------
# Test: Dropout Rate
# ---------------------------------------------------------------------------

class TestDropoutRate:
    def test_dropout_rate(self) -> None:
        """Dropout rate = dropped_out / (continued + dropped_out)."""
        outcomes = [
            _outcome("s1", "inst-1", "T1", "T2", OutcomeStatus.CONTINUED),
            _outcome("s2", "inst-1", "T1", "T2", OutcomeStatus.CONTINUED),
            _outcome("s3", "inst-1", "T1", "T2", OutcomeStatus.DROPPED_OUT),
        ]

        auditor = DataAuditor()
        report = auditor.audit([], [], outcomes)

        assert report.aggregate.dropout_rate == pytest.approx(1 / 3)

    def test_dropout_rate_no_determinable(self) -> None:
        """Dropout rate is 0 when no determinable outcomes."""
        outcomes = [
            _outcome("s1", "inst-1", "T1", "T2", OutcomeStatus.PENDING),
        ]

        auditor = DataAuditor()
        report = auditor.audit([], [], outcomes)

        assert report.aggregate.dropout_rate == 0.0


# ---------------------------------------------------------------------------
# Test: Coverage
# ---------------------------------------------------------------------------

class TestCoverage:
    def test_grade_coverage(self) -> None:
        """Grade coverage = students with grades / total students."""
        enrollments = [
            _enrollment("e1", "s1", "T1"),
            _enrollment("e2", "s2", "T1"),
            _enrollment("e3", "s3", "T1"),
        ]
        grades = [
            _grade("g1", "s1", "T1"),
            _grade("g2", "s2", "T1"),
            # s3 has no grades
        ]

        auditor = DataAuditor()
        report = auditor.audit(enrollments, [], [], grade_observations=grades)

        assert report.aggregate.coverage_grades == pytest.approx(2 / 3)

    def test_attendance_coverage(self) -> None:
        """Attendance coverage calculation."""
        enrollments = [
            _enrollment("e1", "s1", "T1"),
            _enrollment("e2", "s2", "T1"),
        ]
        attendance = [
            _attendance("a1", "s1", "T1"),
        ]

        auditor = DataAuditor()
        report = auditor.audit(enrollments, [], [], attendance_observations=attendance)

        assert report.aggregate.coverage_attendance == pytest.approx(0.5)

    def test_financial_coverage(self) -> None:
        """Financial coverage calculation."""
        enrollments = [
            _enrollment("e1", "s1", "T1"),
            _enrollment("e2", "s2", "T1"),
        ]
        financial = [
            _financial("f1", "s1", "T1"),
        ]

        auditor = DataAuditor()
        report = auditor.audit(enrollments, [], [], financial_records=financial)

        assert report.aggregate.coverage_financial == pytest.approx(0.5)

    def test_engagement_coverage(self) -> None:
        """Engagement coverage calculation."""
        enrollments = [
            _enrollment("e1", "s1", "T1"),
            _enrollment("e2", "s2", "T1"),
        ]
        engagement = [
            _engagement("ev1", "s1", "T1"),
        ]

        auditor = DataAuditor()
        report = auditor.audit(enrollments, [], [], engagement_events=engagement)

        assert report.aggregate.coverage_engagement == pytest.approx(0.5)

    def test_supports_coverage(self) -> None:
        """Support coverage calculation."""
        enrollments = [
            _enrollment("e1", "s1", "T1"),
            _enrollment("e2", "s2", "T1"),
        ]
        supports = [
            _support("sup1", "s1", "T1"),
        ]

        auditor = DataAuditor()
        report = auditor.audit(enrollments, [], [], support_records=supports)

        assert report.aggregate.coverage_supports == pytest.approx(0.5)

    def test_interventions_coverage(self) -> None:
        """Intervention coverage calculation."""
        enrollments = [
            _enrollment("e1", "s1", "T1"),
            _enrollment("e2", "s2", "T1"),
        ]
        interventions = [
            _intervention("i1", "s1", "T1"),
        ]

        auditor = DataAuditor()
        report = auditor.audit(enrollments, [], [], interventions=interventions)

        assert report.aggregate.coverage_interventions == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Test: Temporal Depth
# ---------------------------------------------------------------------------

class TestTemporalDepth:
    def test_avg_temporal_depth(self) -> None:
        """Avg periods per student."""
        enrollments = [
            _enrollment("e1", "s1", "T1"),
            _enrollment("e2", "s1", "T2"),
            _enrollment("e3", "s1", "T3"),
            _enrollment("e4", "s2", "T1"),
        ]

        auditor = DataAuditor()
        report = auditor.audit(enrollments, [], [])

        # s1: 3 periods, s2: 1 period → avg = 2.0
        assert report.aggregate.avg_temporal_depth == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# Test: Event Counts
# ---------------------------------------------------------------------------

class TestEventCounts:
    def test_event_counts(self) -> None:
        """Event counts are tracked correctly."""
        grades = [_grade("g1", "s1", "T1"), _grade("g2", "s1", "T1")]
        attendance = [_attendance("a1", "s1", "T1")]
        financial = [_financial("f1", "s1", "T1")]
        engagement = [_engagement("ev1", "s1", "T1")]
        supports = [_support("sup1", "s1", "T1")]
        interventions = [_intervention("i1", "s1", "T1")]

        auditor = DataAuditor()
        report = auditor.audit(
            [], [], [],
            grade_observations=grades,
            attendance_observations=attendance,
            financial_records=financial,
            engagement_events=engagement,
            support_records=supports,
            interventions=interventions,
        )

        assert report.aggregate.grade_events == 2
        assert report.aggregate.attendance_events == 1
        assert report.aggregate.financial_events == 1
        assert report.aggregate.engagement_events == 1
        assert report.aggregate.support_events == 1
        assert report.aggregate.intervention_events == 1


# ---------------------------------------------------------------------------
# Test: Per-Institution
# ---------------------------------------------------------------------------

class TestPerInstitution:
    def test_multiple_institutions(self) -> None:
        """Metrics are computed per institution."""
        periods = [
            _period("T1", institution_id="inst-1"),
            _period("T1", institution_id="inst-2"),
        ]
        enrollments = [
            _enrollment("e1", "s1", "T1", institution_id="inst-1"),
            _enrollment("e2", "s2", "T1", institution_id="inst-2"),
            _enrollment("e3", "s3", "T1", institution_id="inst-2"),
        ]
        outcomes = [
            _outcome("s1", "inst-1", "T1", "T2", OutcomeStatus.CONTINUED),
            _outcome("s2", "inst-2", "T1", "T2", OutcomeStatus.DROPPED_OUT),
            _outcome("s3", "inst-2", "T1", "T2", OutcomeStatus.CONTINUED),
        ]

        auditor = DataAuditor()
        report = auditor.audit(enrollments, periods, outcomes)

        assert len(report.institutions) == 2

        inst1 = next(i for i in report.institutions if i.institution_id == "inst-1")
        inst2 = next(i for i in report.institutions if i.institution_id == "inst-2")

        assert inst1.students_unique == 1
        assert inst1.outcomes_continued == 1
        assert inst2.students_unique == 2
        assert inst2.outcomes_dropped_out == 1
        assert inst2.outcomes_continued == 1


# ---------------------------------------------------------------------------
# Test: Period Range
# ---------------------------------------------------------------------------

class TestPeriodRange:
    def test_period_range(self) -> None:
        """Earliest and latest period dates are tracked."""
        periods = [
            _period("T1", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T2", start_date="2026-07-01", end_date="2026-12-31"),
        ]
        enrollments = [
            _enrollment("e1", "s1", "T1"),
            _enrollment("e2", "s1", "T2"),
        ]

        auditor = DataAuditor()
        report = auditor.audit(enrollments, periods, [])

        assert report.aggregate.earliest_period == "2026-01-01"
        assert report.aggregate.latest_period == "2026-12-31"


# ---------------------------------------------------------------------------
# Test: JSON Export
# ---------------------------------------------------------------------------

class TestJsonExport:
    def test_json_export(self) -> None:
        """JSON export produces valid file."""
        import json
        import tempfile

        auditor = DataAuditor()
        report = auditor.audit([], [], [])

        with tempfile.TemporaryDirectory() as tmpdir:
            path = export_json(report, f"{tmpdir}/audit.json")
            assert path.exists()

            data = json.loads(path.read_text())
            assert "institutions" in data
            assert "aggregate" in data
            assert "total_real_dropouts" in data


# ---------------------------------------------------------------------------
# Test: CSV Export
# ---------------------------------------------------------------------------

class TestCsvExport:
    def test_csv_export(self) -> None:
        """CSV export produces valid file."""
        import csv
        import tempfile

        enrollments = [_enrollment("e1", "s1", "T1")]
        auditor = DataAuditor()
        report = auditor.audit(enrollments, [], [])

        with tempfile.TemporaryDirectory() as tmpdir:
            path = export_csv(report, f"{tmpdir}/audit.csv")
            assert path.exists()

            with path.open() as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                assert len(rows) == 1
                assert rows[0]["institution_id"] == "inst-1"


# ---------------------------------------------------------------------------
# Test: Summary String
# ---------------------------------------------------------------------------

class TestSummary:
    def test_summary_contains_key_sections(self) -> None:
        """Summary contains all expected sections."""
        auditor = DataAuditor()
        report = auditor.audit([], [], [])

        summary = report.summary()
        assert "CRITICAL NUMBER" in summary
        assert "Real observed dropouts for training" in summary
        assert "AGGREGATE" in summary


# ---------------------------------------------------------------------------
# Test: With LabelBuilder Output
# ---------------------------------------------------------------------------

class TestWithLabelBuilder:
    def test_audit_with_builder_output(self) -> None:
        """Audit works with real LabelBuilder output."""
        periods = [
            _period("T1", start_date="2026-01-01", end_date="2026-06-30"),
            _period("T2", start_date="2026-07-01", end_date="2026-12-31"),
        ]
        enrollments = [
            _enrollment("e1", "s1", "T1"),
            _enrollment("e2", "s1", "T2"),
            _enrollment("e3", "s2", "T1", exit_reason="withdrawal"),
        ]

        builder = LabelBuilder()
        build_result = builder.run(enrollments, periods)

        auditor = DataAuditor()
        report = auditor.audit(enrollments, periods, list(build_result))

        assert report.total_real_dropouts == 1
        assert report.total_usable_outcomes == 2
        assert report.aggregate.students_unique == 2
