"""Tests for canonical academic contracts.

Covers:
  - Serialization/deserialization (model_validate_json, model_dump_json)
  - Field validation (required fields, constraints, enums)
  - Data availability pattern (available_at, is_available_before)
  - Cross-model consistency
  - Edge cases (unicode, empty optional fields, extreme values)
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from leo_risk.contracts.core import (
    AcademicPeriod,
    AcademicProgram,
    Institution,
    Student,
    StudentStatus,
)
from leo_risk.contracts.enrollment import (
    Course,
    CourseEnrollment,
    Enrollment,
    EnrollmentStatus,
)
from leo_risk.contracts.interventions import Intervention, InterventionOutcome, InterventionType
from leo_risk.contracts.observations import (
    AttendanceObservation,
    AttendanceStatus,
    FinancialStatus,
    FinancialStatusRecord,
    GradeObservation,
)
from leo_risk.contracts.support import EngagementEvent, EngagementEventType, StudentSupport, SupportType

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

NOW = datetime.now(UTC)


def _ts(hours_ago: float = 0) -> datetime:
    from datetime import timedelta
    return NOW - timedelta(hours=hours_ago)


def _make_student(**overrides) -> Student:
    defaults = dict(
        student_id="STU-001",
        institution_id="INST-01",
        status=StudentStatus.ACTIVE,
        external_ids={"sis_us": "us-123"},
    )
    defaults.update(overrides)
    return Student(**defaults)


def _make_institution(**overrides) -> Institution:
    defaults = dict(
        institution_id="INST-01",
        name="University of Example",
        country_code="US",
    )
    defaults.update(overrides)
    return Institution(**defaults)


def _make_period(**overrides) -> AcademicPeriod:
    defaults = dict(
        period_id="PER-001",
        institution_id="INST-01",
        code="2024-Fall",
        calendar_type="semester",
        start_date="2024-08-26",
        end_date="2024-12-13",
    )
    defaults.update(overrides)
    return AcademicPeriod(**defaults)


def _make_program(**overrides) -> AcademicProgram:
    defaults = dict(
        program_id="PROG-01",
        institution_id="INST-01",
        name="Computer Science",
    )
    defaults.update(overrides)
    return AcademicProgram(**defaults)


def _make_enrollment(**overrides) -> Enrollment:
    defaults = dict(
        enrollment_id="ENR-001",
        student_id="STU-001",
        institution_id="INST-01",
        program_id="PROG-01",
        period_id="PER-001",
        status=EnrollmentStatus.ENROLLED,
        observed_at=_ts(24),
        available_at=_ts(12),
        source_system="sis_us",
    )
    defaults.update(overrides)
    return Enrollment(**defaults)


def _make_grade(**overrides) -> GradeObservation:
    defaults = dict(
        observation_id="GRD-001",
        student_id="STU-001",
        course_enrollment_id="CENR-001",
        period_id="PER-001",
        grade_type="midterm",
        score=4.2,
        max_score=5.0,
        percentage=84.0,
        passed=True,
        observed_at=_ts(48),
        available_at=_ts(24),
        source_system="lms_canvas",
    )
    defaults.update(overrides)
    return GradeObservation(**defaults)


def _make_attendance(**overrides) -> AttendanceObservation:
    defaults = dict(
        observation_id="ATT-001",
        student_id="STU-001",
        course_enrollment_id="CENR-001",
        period_id="PER-001",
        session_date="2024-09-15",
        status=AttendanceStatus.PRESENT,
        observed_at=_ts(72),
        available_at=_ts(48),
        source_system="lms_canvas",
    )
    defaults.update(overrides)
    return AttendanceObservation(**defaults)


def _make_financial(**overrides) -> FinancialStatusRecord:
    defaults = dict(
        observation_id="FIN-001",
        student_id="STU-001",
        period_id="PER-001",
        status=FinancialStatus.CURRENT,
        amount_due=5000.00,
        amount_paid=5000.00,
        currency="USD",
        observed_at=_ts(24),
        available_at=_ts(12),
        source_system="sis_us",
    )
    defaults.update(overrides)
    return FinancialStatusRecord(**defaults)


def _make_engagement(**overrides) -> EngagementEvent:
    defaults = dict(
        event_id="EVT-001",
        student_id="STU-001",
        period_id="PER-001",
        event_type=EngagementEventType.LMS_LOGIN,
        platform="canvas",
        observed_at=_ts(1),
        available_at=_ts(0.5),
        source_system="lms_canvas",
    )
    defaults.update(overrides)
    return EngagementEvent(**defaults)


def _make_support(**overrides) -> StudentSupport:
    defaults = dict(
        support_id="SUP-001",
        student_id="STU-001",
        period_id="PER-001",
        support_type=SupportType.TUTORING,
        status="active",
        observed_at=_ts(24),
        available_at=_ts(12),
        source_system="manual",
    )
    defaults.update(overrides)
    return StudentSupport(**defaults)


def _make_intervention(**overrides) -> Intervention:
    defaults = dict(
        intervention_id="INT-001",
        student_id="STU-001",
        period_id="PER-001",
        intervention_type=InterventionType.ADVISOR_OUTREACH,
        triggered_by="risk_score",
        outcome=InterventionOutcome.COMPLETED,
        observed_at=_ts(24),
        available_at=_ts(12),
        source_system="advisor_tool",
    )
    defaults.update(overrides)
    return Intervention(**defaults)


# ---------------------------------------------------------------------------
# DataAvailability tests
# ---------------------------------------------------------------------------

class TestDataAvailability:
    def test_is_available_before_true(self) -> None:
        record = _make_enrollment(available_at=_ts(24))
        assert record.is_available_before(_ts(12)) is True

    def test_is_available_before_false(self) -> None:
        record = _make_enrollment(available_at=_ts(12))
        assert record.is_available_before(_ts(24)) is False

    def test_is_available_before_exact(self) -> None:
        ts = _ts(12)
        record = _make_enrollment(available_at=ts)
        assert record.is_available_before(ts) is True


# ---------------------------------------------------------------------------
# Student tests
# ---------------------------------------------------------------------------

class TestStudent:
    def test_create_minimal(self) -> None:
        s = _make_student()
        assert s.student_id == "STU-001"
        assert s.status == StudentStatus.ACTIVE

    def test_external_ids(self) -> None:
        s = _make_student(external_ids={"sis_co": "12345", "lms": "user-1"})
        assert s.external_ids["sis_co"] == "12345"

    def test_empty_student_id_fails(self) -> None:
        with pytest.raises(ValidationError):
            _make_student(student_id="")

    def test_serialization_roundtrip(self) -> None:
        s = _make_student()
        json_str = s.model_dump_json()
        s2 = Student.model_validate_json(json_str)
        assert s.student_id == s2.student_id
        assert s.status == s2.status

    def test_json_schema_has_external_ids(self) -> None:
        schema = Student.model_json_schema()
        assert "external_ids" in schema["properties"]


# ---------------------------------------------------------------------------
# Institution tests
# ---------------------------------------------------------------------------

class TestInstitution:
    def test_create(self) -> None:
        inst = _make_institution()
        assert inst.country_code == "US"

    def test_country_code_length(self) -> None:
        with pytest.raises(ValidationError):
            _make_institution(country_code="USA")

    def test_metadata_extensible(self) -> None:
        inst = _make_institution(metadata={"snies": "12345", "opeid": "001234"})
        assert inst.metadata["snies"] == "12345"

    def test_serialization_roundtrip(self) -> None:
        inst = _make_institution()
        json_str = inst.model_dump_json()
        inst2 = Institution.model_validate_json(json_str)
        assert inst.institution_id == inst2.institution_id


# ---------------------------------------------------------------------------
# AcademicPeriod tests
# ---------------------------------------------------------------------------

class TestAcademicPeriod:
    def test_create(self) -> None:
        p = _make_period()
        assert p.is_closed is False
        assert p.closed_at is None

    def test_closed_period(self) -> None:
        p = _make_period(is_closed=True, closed_at="2024-12-20T10:00:00Z")
        assert p.is_closed is True

    def test_empty_code_fails(self) -> None:
        with pytest.raises(ValidationError):
            _make_period(code="")

    def test_serialization_roundtrip(self) -> None:
        p = _make_period()
        json_str = p.model_dump_json()
        p2 = AcademicPeriod.model_validate_json(json_str)
        assert p.period_id == p2.period_id
        assert p.calendar_type == p2.calendar_type


# ---------------------------------------------------------------------------
# AcademicProgram tests
# ---------------------------------------------------------------------------

class TestAcademicProgram:
    def test_create(self) -> None:
        prog = _make_program()
        assert prog.total_credits is None

    def test_with_credits(self) -> None:
        prog = _make_program(total_credits=120.0, total_periods=10)
        assert prog.total_credits == 120.0

    def test_negative_credits_fails(self) -> None:
        with pytest.raises(ValidationError):
            _make_program(total_credits=-10)


# ---------------------------------------------------------------------------
# Enrollment tests
# ---------------------------------------------------------------------------

class TestEnrollment:
    def test_create(self) -> None:
        e = _make_enrollment()
        assert e.is_active is True
        assert e.exit_reason is None

    def test_dropout_enrollment(self) -> None:
        e = _make_enrollment(
            status=EnrollmentStatus.WITHDRAWN,
            is_active=False,
            exit_reason="retiro_voluntario",
            exit_date="2024-09-15",
        )
        assert e.is_active is False
        assert e.exit_reason == "retiro_voluntario"

    def test_serialization_roundtrip(self) -> None:
        e = _make_enrollment()
        json_str = e.model_dump_json()
        e2 = Enrollment.model_validate_json(json_str)
        assert e.enrollment_id == e2.enrollment_id
        assert e.available_at == e2.available_at

    def test_available_at_preserved_in_json(self) -> None:
        e = _make_enrollment()
        data = e.model_dump()
        assert "available_at" in data
        assert "observed_at" in data


# ---------------------------------------------------------------------------
# Course + CourseEnrollment tests
# ---------------------------------------------------------------------------

class TestCourse:
    def test_create(self) -> None:
        c = Course(
            course_id="CRS-001",
            institution_id="INST-01",
            program_id="PROG-01",
            period_id="PER-001",
            code="MATH101",
            name="Calculus I",
            credits=4.0,
        )
        assert c.credits == 4.0

    def test_serialization_roundtrip(self) -> None:
        c = Course(
            course_id="CRS-001",
            institution_id="INST-01",
            program_id="PROG-01",
            period_id="PER-001",
            code="MATH101",
            name="Calculus I",
        )
        json_str = c.model_dump_json()
        c2 = Course.model_validate_json(json_str)
        assert c.course_id == c2.course_id


class TestCourseEnrollment:
    def test_create(self) -> None:
        ce = CourseEnrollment(
            course_enrollment_id="CENR-001",
            student_id="STU-001",
            course_id="CRS-001",
            period_id="PER-001",
            enrollment_id="ENR-001",
            status=EnrollmentStatus.ENROLLED,
            observed_at=_ts(24),
            available_at=_ts(12),
            source_system="sis_us",
        )
        assert ce.is_active is True

    def test_with_grade(self) -> None:
        ce = CourseEnrollment(
            course_enrollment_id="CENR-001",
            student_id="STU-001",
            course_id="CRS-001",
            period_id="PER-001",
            enrollment_id="ENR-001",
            status=EnrollmentStatus.COMPLETED,
            final_grade=4.5,
            passed=True,
            observed_at=_ts(24),
            available_at=_ts(12),
            source_system="sis_us",
        )
        assert ce.final_grade == 4.5
        assert ce.passed is True


# ---------------------------------------------------------------------------
# GradeObservation tests
# ---------------------------------------------------------------------------

class TestGradeObservation:
    def test_create(self) -> None:
        g = _make_grade()
        assert g.score == 4.2

    def test_null_score(self) -> None:
        g = _make_grade(score=None, max_score=None, percentage=None)
        assert g.score is None

    def test_percentage_range(self) -> None:
        with pytest.raises(ValidationError):
            _make_grade(percentage=101.0)

    def test_serialization_roundtrip(self) -> None:
        g = _make_grade()
        json_str = g.model_dump_json()
        g2 = GradeObservation.model_validate_json(json_str)
        assert g.observation_id == g2.observation_id
        assert g.available_at == g2.available_at


# ---------------------------------------------------------------------------
# AttendanceObservation tests
# ---------------------------------------------------------------------------

class TestAttendanceObservation:
    def test_create_present(self) -> None:
        a = _make_attendance()
        assert a.status == AttendanceStatus.PRESENT

    def test_create_absent(self) -> None:
        a = _make_attendance(status=AttendanceStatus.ABSENT)
        assert a.status == AttendanceStatus.ABSENT

    def test_tardy_with_minutes(self) -> None:
        a = _make_attendance(status=AttendanceStatus.TARDY, minutes_late=15)
        assert a.minutes_late == 15

    def test_serialization_roundtrip(self) -> None:
        a = _make_attendance()
        json_str = a.model_dump_json()
        a2 = AttendanceObservation.model_validate_json(json_str)
        assert a.session_date == a2.session_date


# ---------------------------------------------------------------------------
# FinancialStatusRecord tests
# ---------------------------------------------------------------------------

class TestFinancialStatusRecord:
    def test_create_current(self) -> None:
        f = _make_financial()
        assert f.status == FinancialStatus.CURRENT

    def test_overdue(self) -> None:
        f = _make_financial(
            status=FinancialStatus.OVERDUE,
            amount_paid=0.0,
            has_outstanding_debt=True,
            consecutive_overdue_periods=3,
        )
        assert f.consecutive_overdue_periods == 3

    def test_negative_amount_fails(self) -> None:
        with pytest.raises(ValidationError):
            _make_financial(amount_due=-100)

    def test_currency_length(self) -> None:
        with pytest.raises(ValidationError):
            _make_financial(currency="US")

    def test_serialization_roundtrip(self) -> None:
        f = _make_financial()
        json_str = f.model_dump_json()
        f2 = FinancialStatusRecord.model_validate_json(json_str)
        assert f.amount_due == f2.amount_due


# ---------------------------------------------------------------------------
# EngagementEvent tests
# ---------------------------------------------------------------------------

class TestEngagementEvent:
    def test_create(self) -> None:
        e = _make_engagement()
        assert e.event_type == EngagementEventType.LMS_LOGIN

    def test_all_event_types(self) -> None:
        for et in EngagementEventType:
            e = _make_engagement(event_type=et)
            assert e.event_type == et

    def test_serialization_roundtrip(self) -> None:
        e = _make_engagement()
        json_str = e.model_dump_json()
        e2 = EngagementEvent.model_validate_json(json_str)
        assert e.event_id == e2.event_id


# ---------------------------------------------------------------------------
# StudentSupport tests
# ---------------------------------------------------------------------------

class TestStudentSupport:
    def test_create(self) -> None:
        s = _make_support()
        assert s.support_type == SupportType.TUTORING

    def test_all_support_types(self) -> None:
        for st in SupportType:
            s = _make_support(support_type=st)
            assert s.support_type == st

    def test_serialization_roundtrip(self) -> None:
        s = _make_support()
        json_str = s.model_dump_json()
        s2 = StudentSupport.model_validate_json(json_str)
        assert s.support_id == s2.support_id


# ---------------------------------------------------------------------------
# Intervention tests
# ---------------------------------------------------------------------------

class TestIntervention:
    def test_create(self) -> None:
        i = _make_intervention()
        assert i.intervention_type == InterventionType.ADVISOR_OUTREACH

    def test_with_risk_score(self) -> None:
        i = _make_intervention(risk_score_at_intervention=0.82)
        assert i.risk_score_at_intervention == 0.82

    def test_risk_score_out_of_range(self) -> None:
        with pytest.raises(ValidationError):
            _make_intervention(risk_score_at_intervention=1.5)

    def test_serialization_roundtrip(self) -> None:
        i = _make_intervention()
        json_str = i.model_dump_json()
        i2 = Intervention.model_validate_json(json_str)
        assert i.intervention_id == i2.intervention_id


# ---------------------------------------------------------------------------
# Cross-model consistency
# ---------------------------------------------------------------------------

class TestCrossModelConsistency:
    def test_student_in_institution(self) -> None:
        s = _make_student(institution_id="INST-01")
        i = _make_institution(institution_id="INST-01")
        assert s.institution_id == i.institution_id

    def test_enrollment_links_to_student_and_period(self) -> None:
        e = _make_enrollment(student_id="STU-001", period_id="PER-001")
        assert e.student_id == "STU-001"
        assert e.period_id == "PER-001"

    def test_grade_links_to_course_enrollment(self) -> None:
        g = _make_grade(course_enrollment_id="CENR-001")
        ce = CourseEnrollment(
            course_enrollment_id="CENR-001",
            student_id="STU-001",
            course_id="CRS-001",
            period_id="PER-001",
            enrollment_id="ENR-001",
            status=EnrollmentStatus.ENROLLED,
            observed_at=_ts(24),
            available_at=_ts(12),
            source_system="sis_us",
        )
        assert g.course_enrollment_id == ce.course_enrollment_id


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_unicode_student_id(self) -> None:
        s = _make_student(student_id="STU-Ñ-001")
        assert s.student_id == "STU-Ñ-001"

    def test_unicode_institution_name(self) -> None:
        i = _make_institution(name="Universidad Nacional de Colombia")
        assert "Colombia" in i.name

    def test_unicode_program_name(self) -> None:
        p = _make_program(name="Ingeniería de Sistemas")
        assert "Sistemas" in p.name

    def test_empty_metadata(self) -> None:
        i = _make_institution(metadata={})
        assert i.metadata == {}

    def test_large_external_ids(self) -> None:
        ids = {f"system_{i}": f"id_{i}" for i in range(50)}
        s = _make_student(external_ids=ids)
        assert len(s.external_ids) == 50

    def test_future_observed_at(self) -> None:
        from datetime import timedelta
        future = NOW + timedelta(days=365)
        g = _make_grade(observed_at=future, available_at=future)
        assert g.observed_at > NOW

    def test_available_before_observed(self) -> None:
        """Data can be available before the event is observed (e.g., pre-loaded)."""
        g = _make_grade(available_at=_ts(48), observed_at=_ts(24))
        assert g.available_at < g.observed_at


# ---------------------------------------------------------------------------
# JSON schema generation
# ---------------------------------------------------------------------------

class TestJsonSchema:
    def test_student_schema(self) -> None:
        schema = Student.model_json_schema()
        assert "properties" in schema
        assert "student_id" in schema["properties"]

    def test_enrollment_schema(self) -> None:
        schema = Enrollment.model_json_schema()
        assert "available_at" in schema["properties"]
        assert "observed_at" in schema["properties"]

    def test_all_contracts_have_schemas(self) -> None:
        contracts = [
            Student, Institution, AcademicPeriod, AcademicProgram,
            Enrollment, Course, CourseEnrollment,
            GradeObservation, AttendanceObservation, FinancialStatusRecord,
            EngagementEvent, StudentSupport, Intervention,
        ]
        for contract in contracts:
            schema = contract.model_json_schema()
            assert "properties" in schema, f"{contract.__name__} missing schema"
