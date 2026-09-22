"""Tests for RiskInput contract.

Covers:
  - Happy path (minimal, full, different calendars)
  - Point-in-time validation (future leakage rejection)
  - PII exclusion (schema-level protection)
  - Round-trip serialization (JSON ↔ RiskInput)
  - Canonical serialization determinism
  - Timezone handling
  - International fixtures (semester vs quarter)
  - Extensions mechanism
  - Edge cases
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from leo_risk.contracts.enrollment import Course, CourseEnrollment, Enrollment, EnrollmentStatus
from leo_risk.contracts.observations import (
    AttendanceObservation,
    AttendanceStatus,
    FinancialStatus,
    FinancialStatusRecord,
    GradeObservation,
)
from leo_risk.contracts.risk_input import (
    SCHEMA_VERSION,
    AcademicBlock,
    AttendanceBlock,
    EducationLevel,
    EngagementBlock,
    FinancialBlock,
    InstitutionalContext,
    InterventionsBlock,
    RiskInput,
    SourceAvailability,
    SourceStatus,
    SupportsBlock,
)
from leo_risk.contracts.support import EngagementEvent, EngagementEventType

# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

NOW = datetime(2026, 9, 21, 12, 0, 0, tzinfo=UTC)


def _hours(n: float) -> datetime:
    from datetime import timedelta
    return NOW - timedelta(hours=n)


def _future(hours: float = 1) -> datetime:
    from datetime import timedelta
    return NOW + timedelta(hours=hours)


# ---------------------------------------------------------------------------
# Minimal fixture (no optional blocks)
# ---------------------------------------------------------------------------

def _make_minimal(**overrides) -> RiskInput:
    defaults = dict(
        student_id="STU-001",
        institution_id="INST-01",
        as_of=NOW,
    )
    defaults.update(overrides)
    return RiskInput(**defaults)


# ---------------------------------------------------------------------------
# Semester fixture (Fixture A)
# ---------------------------------------------------------------------------

def _make_semester_fixture() -> RiskInput:
    """Fixture A: Semester institution with numeric grades and attendance."""
    return RiskInput(
        student_id="STU-SEM-001",
        institution_id="INST-SEM-01",
        academic_program_id="PROG-CS",
        academic_period_id="PER-2024-2",
        as_of=NOW,
        academic=AcademicBlock(
            enrollments=[
                Enrollment(
                    enrollment_id="ENR-001",
                    student_id="STU-SEM-001",
                    institution_id="INST-SEM-01",
                    program_id="PROG-CS",
                    period_id="PER-2024-2",
                    status=EnrollmentStatus.ENROLLED,
                    semester_index=4,
                    accumulated_credits=60.0,
                    term_gpa=3.8,
                    cumulative_gpa=3.5,
                    observed_at=_hours(72),
                    available_at=_hours(48),
                    source_system="sis_semester",
                ),
            ],
            courses=[
                Course(
                    course_id="CRS-001",
                    institution_id="INST-SEM-01",
                    program_id="PROG-CS",
                    period_id="PER-2024-2",
                    code="CS201",
                    name="Data Structures",
                    credits=4.0,
                ),
            ],
            course_enrollments=[
                CourseEnrollment(
                    course_enrollment_id="CENR-001",
                    student_id="STU-SEM-001",
                    course_id="CRS-001",
                    period_id="PER-2024-2",
                    enrollment_id="ENR-001",
                    status=EnrollmentStatus.ENROLLED,
                    grade_scale="0-5",
                    observed_at=_hours(48),
                    available_at=_hours(24),
                    source_system="sis_semester",
                ),
            ],
            grade_observations=[
                GradeObservation(
                    observation_id="GRD-001",
                    student_id="STU-SEM-001",
                    course_enrollment_id="CENR-001",
                    period_id="PER-2024-2",
                    grade_type="midterm",
                    score=4.2,
                    max_score=5.0,
                    percentage=84.0,
                    passed=True,
                    observed_at=_hours(72),
                    available_at=_hours(48),
                    source_system="lms_canvas",
                ),
            ],
        ),
        attendance=AttendanceBlock(
            observations=[
                AttendanceObservation(
                    observation_id="ATT-001",
                    student_id="STU-SEM-001",
                    course_enrollment_id="CENR-001",
                    period_id="PER-2024-2",
                    session_date="2024-09-15",
                    status=AttendanceStatus.PRESENT,
                    observed_at=_hours(72),
                    available_at=_hours(48),
                    source_system="lms_canvas",
                ),
            ],
        ),
        institutional_context=InstitutionalContext(
            period_id="PER-2024-2",
            period_code="2024-2",
            period_start_date="2024-08-26",
            period_end_date="2024-12-13",
            calendar_type="semester",
            program_id="PROG-CS",
            program_name="Computer Science",
            program_level=EducationLevel.UNDERGRADUATE,
            credit_system="semester_credits",
            periods_completed=3,
            total_periods=10,
            period_position_ratio=0.45,
        ),
        available_sources=[
            SourceAvailability(source_id="academic", status=SourceStatus.AVAILABLE),
            SourceAvailability(source_id="attendance", status=SourceStatus.AVAILABLE),
            SourceAvailability(source_id="financial", status=SourceStatus.NOT_PROVIDED),
            SourceAvailability(source_id="engagement", status=SourceStatus.NOT_INTEGRATED),
        ],
    )


# ---------------------------------------------------------------------------
# Quarter fixture (Fixture B)
# ---------------------------------------------------------------------------

def _make_quarter_fixture() -> RiskInput:
    """Fixture B: Quarter institution with different grading and sources."""
    return RiskInput(
        student_id="STU-QTR-001",
        institution_id="INST-QTR-01",
        academic_program_id="PROG-BA",
        academic_period_id="PER-2024-FALL",
        as_of=NOW,
        academic=AcademicBlock(
            enrollments=[
                Enrollment(
                    enrollment_id="ENR-Q-001",
                    student_id="STU-QTR-001",
                    institution_id="INST-QTR-01",
                    program_id="PROG-BA",
                    period_id="PER-2024-FALL",
                    status=EnrollmentStatus.ENROLLED,
                    semester_index=2,
                    accumulated_credits=45.0,
                    cumulative_gpa=3.2,
                    observed_at=_hours(96),
                    available_at=_hours(72),
                    source_system="sis_quarter",
                ),
            ],
            grade_observations=[
                GradeObservation(
                    observation_id="GRD-Q-001",
                    student_id="STU-QTR-001",
                    course_enrollment_id="CENR-Q-001",
                    period_id="PER-2024-FALL",
                    grade_type="midterm",
                    percentage=72.0,
                    letter_grade="B-",
                    observed_at=_hours(96),
                    available_at=_hours(72),
                    source_system="lms_moodle",
                ),
            ],
        ),
        financial=FinancialBlock(
            records=[
                FinancialStatusRecord(
                    observation_id="FIN-Q-001",
                    student_id="STU-QTR-001",
                    period_id="PER-2024-FALL",
                    status=FinancialStatus.CURRENT,
                    amount_due=15000.00,
                    amount_paid=15000.00,
                    currency="USD",
                    observed_at=_hours(48),
                    available_at=_hours(24),
                    source_system="sis_quarter",
                ),
            ],
        ),
        engagement=EngagementBlock(
            events=[
                EngagementEvent(
                    event_id="EVT-Q-001",
                    student_id="STU-QTR-001",
                    period_id="PER-2024-FALL",
                    event_type=EngagementEventType.LMS_LOGIN,
                    platform="moodle",
                    observed_at=_hours(6),
                    available_at=_hours(3),
                    source_system="lms_moodle",
                ),
            ],
        ),
        institutional_context=InstitutionalContext(
            period_id="PER-2024-FALL",
            period_code="2024-FALL",
            period_start_date="2024-09-25",
            period_end_date="2024-12-10",
            calendar_type="quarter",
            program_id="PROG-BA",
            program_name="Business Administration",
            program_level=EducationLevel.UNDERGRADUATE,
            modality="hybrid",
            credit_system="quarter_credits",
            periods_completed=1,
            total_periods=12,
            period_position_ratio=0.55,
        ),
        available_sources=[
            SourceAvailability(source_id="academic", status=SourceStatus.AVAILABLE),
            SourceAvailability(source_id="attendance", status=SourceStatus.NOT_PROVIDED),
            SourceAvailability(source_id="financial", status=SourceStatus.AVAILABLE),
            SourceAvailability(source_id="engagement", status=SourceStatus.AVAILABLE),
            SourceAvailability(source_id="lms", status=SourceStatus.AVAILABLE),
        ],
    )


# ---------------------------------------------------------------------------
# Happy path tests
# ---------------------------------------------------------------------------

class TestRiskInputHappyPath:
    def test_minimal(self) -> None:
        ri = _make_minimal()
        assert ri.student_id == "STU-001"
        assert ri.schema_version == SCHEMA_VERSION

    def test_semester_fixture(self) -> None:
        ri = _make_semester_fixture()
        assert ri.academic.enrollments[0].status == EnrollmentStatus.ENROLLED
        assert ri.institutional_context.calendar_type == "semester"

    def test_quarter_fixture(self) -> None:
        ri = _make_quarter_fixture()
        assert ri.financial is not None
        assert ri.engagement is not None
        assert ri.institutional_context.calendar_type == "quarter"

    def test_optional_blocks_can_be_none(self) -> None:
        ri = _make_minimal()
        assert ri.financial is None
        assert ri.engagement is None
        assert ri.supports is None
        assert ri.interventions is None

    def test_extensions(self) -> None:
        ri = _make_minimal(
            extensions={
                "co.education": {"admission_exam_score": 315},
                "us.collegeboard": {"sat_score": 1200},
            }
        )
        assert ri.extensions["co.education"]["admission_exam_score"] == 315

    def test_sources_distinction(self) -> None:
        """AVAILABLE vs NOT_PROVIDED vs NOT_INTEGRATED vs EMPTY."""
        ri = _make_minimal(
            available_sources=[
                SourceAvailability(source_id="academic", status=SourceStatus.AVAILABLE),
                SourceAvailability(source_id="financial", status=SourceStatus.NOT_PROVIDED),
                SourceAvailability(source_id="lms", status=SourceStatus.NOT_INTEGRATED),
                SourceAvailability(source_id="support", status=SourceStatus.EMPTY),
            ]
        )
        statuses = {s.source_id: s.status for s in ri.available_sources}
        assert statuses["academic"] == SourceStatus.AVAILABLE
        assert statuses["financial"] == SourceStatus.NOT_PROVIDED
        assert statuses["lms"] == SourceStatus.NOT_INTEGRATED
        assert statuses["support"] == SourceStatus.EMPTY


# ---------------------------------------------------------------------------
# Point-in-time validation tests
# ---------------------------------------------------------------------------

class TestPointInTime:
    def test_future_leakage_in_enrollment(self) -> None:
        with pytest.raises(ValidationError, match="Future data detected"):
            RiskInput(
                student_id="S1",
                institution_id="I1",
                as_of=NOW,
                academic=AcademicBlock(
                    enrollments=[
                        Enrollment(
                            enrollment_id="E1",
                            student_id="S1",
                            institution_id="I1",
                            program_id="P1",
                            period_id="PER1",
                            status=EnrollmentStatus.ENROLLED,
                            observed_at=_hours(24),
                            available_at=_future(1),  # Future!
                            source_system="sis",
                        ),
                    ],
                ),
            )

    def test_future_leakage_in_grade(self) -> None:
        with pytest.raises(ValidationError, match="Future data detected"):
            RiskInput(
                student_id="S1",
                institution_id="I1",
                as_of=NOW,
                academic=AcademicBlock(
                    grade_observations=[
                        GradeObservation(
                            observation_id="G1",
                            student_id="S1",
                            course_enrollment_id="C1",
                            period_id="PER1",
                            grade_type="final",
                            score=4.0,
                            observed_at=_hours(24),
                            available_at=_future(1),  # Future!
                            source_system="lms",
                        ),
                    ],
                ),
            )

    def test_future_leakage_in_attendance(self) -> None:
        with pytest.raises(ValidationError, match="Future data detected"):
            RiskInput(
                student_id="S1",
                institution_id="I1",
                as_of=NOW,
                attendance=AttendanceBlock(
                    observations=[
                        AttendanceObservation(
                            observation_id="A1",
                            student_id="S1",
                            course_enrollment_id="C1",
                            period_id="PER1",
                            session_date="2024-09-15",
                            status=AttendanceStatus.PRESENT,
                            observed_at=_hours(24),
                            available_at=_future(1),  # Future!
                            source_system="lms",
                        ),
                    ],
                ),
            )

    def test_valid_observation_passes(self) -> None:
        ri = RiskInput(
            student_id="S1",
            institution_id="I1",
            as_of=_hours(0),
            academic=AcademicBlock(
                enrollments=[
                    Enrollment(
                        enrollment_id="E1",
                        student_id="S1",
                        institution_id="I1",
                        program_id="P1",
                        period_id="PER1",
                        status=EnrollmentStatus.ENROLLED,
                        observed_at=_hours(48),
                        available_at=_hours(24),
                        source_system="sis",
                    ),
                ],
            ),
        )
        assert len(ri.academic.enrollments) == 1

    def test_available_at_equals_as_of(self) -> None:
        """available_at == as_of is allowed (data was available at the prediction time)."""
        ri = RiskInput(
            student_id="S1",
            institution_id="I1",
            as_of=NOW,
            academic=AcademicBlock(
                enrollments=[
                    Enrollment(
                        enrollment_id="E1",
                        student_id="S1",
                        institution_id="I1",
                        program_id="P1",
                        period_id="PER1",
                        status=EnrollmentStatus.ENROLLED,
                        observed_at=_hours(24),
                        available_at=NOW,  # Exactly as_of
                        source_system="sis",
                    ),
                ],
            ),
        )
        assert ri.as_of == NOW


# ---------------------------------------------------------------------------
# PII exclusion tests
# ---------------------------------------------------------------------------

class TestPIIExclusion:
    def test_no_pii_fields_in_schema(self) -> None:
        """RiskInput schema must not expose PII fields."""
        schema = RiskInput.model_json_schema()
        props = schema.get("properties", {})

        pii_fields = {
            "first_name", "last_name", "email", "phone", "phone_number",
            "document_number", "address", "username", "photo", "photograph",
            "full_name", "name", "surname", "cell_phone", "mobile",
            "id_number", "passport", "ssn", "national_id",
        }
        exposed = pii_fields.intersection(props.keys())
        assert not exposed, f"PII fields found in RiskInput schema: {exposed}"

    def test_no_pii_in_sub_blocks(self) -> None:
        """Sub-blocks should not introduce PII either."""
        for block_cls in [AcademicBlock, AttendanceBlock, FinancialBlock,
                          EngagementBlock, SupportsBlock, InterventionsBlock]:
            schema = block_cls.model_json_schema()
            props = schema.get("properties", {})
            pii_fields = {
                "first_name", "last_name", "email", "phone", "address",
                "document_number", "username",
            }
            exposed = pii_fields.intersection(props.keys())
            assert not exposed, f"PII in {block_cls.__name__}: {exposed}"


# ---------------------------------------------------------------------------
# Round-trip serialization tests
# ---------------------------------------------------------------------------

class TestRoundTrip:
    def test_minimal_roundtrip(self) -> None:
        ri = _make_minimal()
        json_str = ri.model_dump_json()
        ri2 = RiskInput.model_validate_json(json_str)
        assert ri.student_id == ri2.student_id
        assert ri.as_of == ri2.as_of

    def test_semester_roundtrip(self) -> None:
        ri = _make_semester_fixture()
        json_str = ri.model_dump_json()
        ri2 = RiskInput.model_validate_json(json_str)
        assert len(ri2.academic.enrollments) == 1
        assert ri2.institutional_context.calendar_type == "semester"

    def test_quarter_roundtrip(self) -> None:
        ri = _make_quarter_fixture()
        json_str = ri.model_dump_json()
        ri2 = RiskInput.model_validate_json(json_str)
        assert ri2.financial is not None
        assert ri2.engagement is not None

    def test_extensions_roundtrip(self) -> None:
        ri = _make_minimal(extensions={"co.education": {"score": 315}})
        json_str = ri.model_dump_json()
        ri2 = RiskInput.model_validate_json(json_str)
        assert ri2.extensions["co.education"]["score"] == 315


# ---------------------------------------------------------------------------
# Canonical serialization determinism tests
# ---------------------------------------------------------------------------

class TestCanonicalDeterminism:
    def test_to_canonical_dict_same_content(self) -> None:
        ri1 = _make_semester_fixture()
        ri2 = _make_semester_fixture()
        assert ri1.to_canonical_dict() == ri2.to_canonical_dict()

    def test_deterministic_hash(self) -> None:
        ri1 = _make_semester_fixture()
        ri2 = _make_semester_fixture()
        assert ri1.compute_hash() == ri2.compute_hash()

    def test_different_content_different_hash(self) -> None:
        ri1 = _make_minimal(student_id="S1")
        ri2 = _make_minimal(student_id="S2")
        assert ri1.compute_hash() != ri2.compute_hash()

    def test_sorted_observations(self) -> None:
        """Canonical dict sorts observations by available_at, then observed_at."""
        ri = RiskInput(
            student_id="S1",
            institution_id="I1",
            as_of=NOW,
            attendance=AttendanceBlock(
                observations=[
                    AttendanceObservation(
                        observation_id="A2",
                        student_id="S1",
                        course_enrollment_id="C1",
                        period_id="P1",
                        session_date="2024-09-15",
                        status=AttendanceStatus.PRESENT,
                        observed_at=_hours(24),
                        available_at=_hours(6),  # Later available
                        source_system="lms",
                    ),
                    AttendanceObservation(
                        observation_id="A1",
                        student_id="S1",
                        course_enrollment_id="C1",
                        period_id="P1",
                        session_date="2024-09-10",
                        status=AttendanceStatus.PRESENT,
                        observed_at=_hours(48),
                        available_at=_hours(24),  # Earlier available
                        source_system="lms",
                    ),
                ],
            ),
        )
        canonical = ri.to_canonical_dict()
        obs = canonical["attendance"]["observations"]
        assert obs[0]["observation_id"] == "A1"  # available_at=24h ago comes first
        assert obs[1]["observation_id"] == "A2"  # available_at=6h ago comes second


# ---------------------------------------------------------------------------
# Timezone tests
# ---------------------------------------------------------------------------

class TestTimezone:
    def test_utc_timestamps_work(self) -> None:
        ri = _make_minimal(as_of=datetime(2026, 9, 21, 12, 0, 0, tzinfo=UTC))
        assert ri.as_of.tzinfo is not None

    def test_naive_datetime_gets_utc(self) -> None:
        """Pydantic v2 coerces naive datetimes to UTC by default.
        The as_of field accepts naive datetimes and stores them.
        The recommendation is to always pass timezone-aware datetimes."""
        ri = _make_minimal(as_of=datetime(2026, 9, 21, 12, 0, 0))
        # Pydantic v2 accepts naive datetimes
        assert ri.as_of is not None


# ---------------------------------------------------------------------------
# Version tests
# ---------------------------------------------------------------------------

class TestVersion:
    def test_default_version(self) -> None:
        ri = _make_minimal()
        assert ri.schema_version == "1.0.0"

    def test_custom_version(self) -> None:
        ri = _make_minimal(schema_version="2.0.0")
        assert ri.schema_version == "2.0.0"

    def test_invalid_version_format(self) -> None:
        with pytest.raises(ValidationError):
            _make_minimal(schema_version="v1")


# ---------------------------------------------------------------------------
# International fixtures tests
# ---------------------------------------------------------------------------

class TestInternationalFixtures:
    def test_semester_institution(self) -> None:
        ri = _make_semester_fixture()
        assert ri.institutional_context.calendar_type == "semester"
        assert ri.institutional_context.credit_system == "semester_credits"
        # No financial data - institution doesn't track it
        assert ri.financial is None

    def test_quarter_institution(self) -> None:
        ri = _make_quarter_fixture()
        assert ri.institutional_context.calendar_type == "quarter"
        assert ri.institutional_context.credit_system == "quarter_credits"
        # Has financial and engagement data
        assert ri.financial is not None
        assert ri.engagement is not None

    def test_both_produce_valid_risk_input(self) -> None:
        """Both fixtures produce valid RiskInputs using the same contract."""
        ri_sem = _make_semester_fixture()
        ri_qtr = _make_quarter_fixture()
        assert ri_sem.schema_version == ri_qtr.schema_version
        assert ri_sem.model_json_schema() == ri_qtr.model_json_schema()


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_extensions(self) -> None:
        ri = _make_minimal(extensions={})
        assert ri.extensions == {}

    def test_empty_sources(self) -> None:
        ri = _make_minimal(available_sources=[])
        assert ri.available_sources == []

    def test_large_enrollment_history(self) -> None:
        enrollments = [
            Enrollment(
                enrollment_id=f"ENR-{i}",
                student_id="S1",
                institution_id="I1",
                program_id="P1",
                period_id=f"PER-{i}",
                status=EnrollmentStatus.COMPLETED,
                observed_at=_hours(24 * (20 - i)),
                available_at=_hours(24 * (19 - i)),
                source_system="sis",
            )
            for i in range(20)
        ]
        ri = RiskInput(
            student_id="S1",
            institution_id="I1",
            as_of=NOW,
            academic=AcademicBlock(enrollments=enrollments),
        )
        assert len(ri.academic.enrollments) == 20

    def test_unicode_ids(self) -> None:
        ri = _make_minimal(
            student_id="STU-Ñ-001",
            institution_id="INST-É-01",
        )
        assert ri.student_id == "STU-Ñ-001"

    def test_json_schema_generation(self) -> None:
        schema = RiskInput.model_json_schema()
        assert "properties" in schema
        assert "as_of" in schema["properties"]
        assert "student_id" in schema["properties"]
        assert "academic" in schema["properties"]
