"""Data availability auditor.

Calculates what data actually exists per institution.
Distinguishes: students, snapshots, events, outcomes.
"""

from collections import defaultdict

from leo_risk.contracts.core import AcademicPeriod
from leo_risk.contracts.enrollment import Enrollment
from leo_risk.contracts.interventions import Intervention
from leo_risk.contracts.observations import (
    AttendanceObservation,
    FinancialStatusRecord,
    GradeObservation,
)
from leo_risk.contracts.support import EngagementEvent, StudentSupport
from leo_risk.domain.audit.report import AuditReport, InstitutionAudit


class DataAuditor:
    """Audits data availability across institutions.

    Usage:
        auditor = DataAuditor()
        report = auditor.audit(
            enrollments=enrollments,
            periods=periods,
            outcomes=outcomes,
            grade_observations=grades,
            attendance_observations=attendance,
            financial_records=financial,
            engagement_events=engagement,
            support_records=supports,
            interventions=interventions,
        )
        print(report.summary())
    """

    def audit(
        self,
        enrollments: list[Enrollment],
        periods: list[AcademicPeriod],
        outcomes: list,
        *,
        grade_observations: list[GradeObservation] | None = None,
        attendance_observations: list[AttendanceObservation] | None = None,
        financial_records: list[FinancialStatusRecord] | None = None,
        engagement_events: list[EngagementEvent] | None = None,
        support_records: list[StudentSupport] | None = None,
        interventions: list[Intervention] | None = None,
    ) -> AuditReport:
        """Run a full data availability audit.

        Args:
            enrollments: All enrollment records.
            periods: All academic period definitions.
            outcomes: Labeled StudentOutcome records from LabelBuilder.
            grade_observations: Optional grade observation events.
            attendance_observations: Optional attendance observation events.
            financial_records: Optional financial status records.
            engagement_events: Optional engagement events.
            support_records: Optional support service records.
            interventions: Optional intervention records.

        Returns:
            AuditReport with per-institution and aggregate metrics.
        """
        grade_observations = grade_observations or []
        attendance_observations = attendance_observations or []
        financial_records = financial_records or []
        engagement_events = engagement_events or []
        support_records = support_records or []
        interventions = interventions or []

        # Index periods
        period_map = {p.period_id: p for p in periods}

        # Build student → institution mapping from enrollments
        student_to_institution: dict[str, str] = {}
        for e in enrollments:
            student_to_institution[e.student_id] = e.institution_id

        # Group enrollments and outcomes by institution
        inst_enrollments = self._group_by_field(enrollments, "institution_id")
        inst_outcomes = self._group_by_field(outcomes, "institution_id")

        # Build student sets for each observation type (institution-agnostic)
        students_with_grades = {g.student_id for g in grade_observations}
        students_with_attendance = {a.student_id for a in attendance_observations}
        students_with_financial = {f.student_id for f in financial_records}
        students_with_engagement = {e.student_id for e in engagement_events}
        students_with_supports = {s.student_id for s in support_records}
        students_with_interventions = {i.student_id for i in interventions}

        # Get all institution IDs
        all_institution_ids = set(inst_enrollments.keys()) | set(inst_outcomes.keys())

        # Build per-institution audits
        institution_audits = []
        for inst_id in sorted(all_institution_ids):
            audit = self._audit_institution(
                institution_id=inst_id,
                enrollments=inst_enrollments.get(inst_id, []),
                outcomes=inst_outcomes.get(inst_id, []),
                students_with_grades=students_with_grades,
                students_with_attendance=students_with_attendance,
                students_with_financial=students_with_financial,
                students_with_engagement=students_with_engagement,
                students_with_supports=students_with_supports,
                students_with_interventions=students_with_interventions,
                grade_observations=grade_observations,
                attendance_observations=attendance_observations,
                financial_records=financial_records,
                engagement_events=engagement_events,
                support_records=support_records,
                interventions=interventions,
                period_map=period_map,
            )
            institution_audits.append(audit)

        # Build aggregate
        aggregate = self._audit_institution(
            institution_id="__aggregate__",
            enrollments=enrollments,
            outcomes=outcomes,
            students_with_grades=students_with_grades,
            students_with_attendance=students_with_attendance,
            students_with_financial=students_with_financial,
            students_with_engagement=students_with_engagement,
            students_with_supports=students_with_supports,
            students_with_interventions=students_with_interventions,
            grade_observations=grade_observations,
            attendance_observations=attendance_observations,
            financial_records=financial_records,
            engagement_events=engagement_events,
            support_records=support_records,
            interventions=interventions,
            period_map=period_map,
        )

        # Compute summary numbers
        total_dropouts = sum(i.outcomes_dropped_out for i in institution_audits)
        total_usable = sum(
            i.outcomes_continued + i.outcomes_dropped_out for i in institution_audits
        )
        total_excluded = sum(
            i.outcomes_pending + i.outcomes_unknown for i in institution_audits
        )

        return AuditReport(
            institutions=institution_audits,
            aggregate=aggregate,
            total_real_dropouts=total_dropouts,
            total_usable_outcomes=total_usable,
            total_excluded_outcomes=total_excluded,
        )

    def _group_by_field(self, records: list, field: str) -> dict[str, list]:
        """Group records by a field value."""
        groups: dict[str, list] = defaultdict(list)
        for r in records:
            val = getattr(r, field, None)
            if val is not None:
                groups[str(val)].append(r)
        return dict(groups)

    def _audit_institution(
        self,
        institution_id: str,
        enrollments: list[Enrollment],
        outcomes: list,
        students_with_grades: set[str],
        students_with_attendance: set[str],
        students_with_financial: set[str],
        students_with_engagement: set[str],
        students_with_supports: set[str],
        students_with_interventions: set[str],
        grade_observations: list,
        attendance_observations: list,
        financial_records: list,
        engagement_events: list,
        support_records: list,
        interventions: list,
        period_map: dict,
    ) -> InstitutionAudit:
        """Compute audit metrics for a single institution."""
        # Students
        students = {e.student_id for e in enrollments}
        students_from_outcomes = {o.student_id for o in outcomes}
        all_students = students | students_from_outcomes

        # Periods
        periods_with_enrollments = {e.period_id for e in enrollments}

        # Cohorts: (program_id, period_id) pairs
        cohorts = {(e.program_id, e.period_id) for e in enrollments}

        # Snapshots: (student_id, period_id) pairs
        snapshots = {(e.student_id, e.period_id) for e in enrollments}

        # Outcome counts
        outcome_counts = defaultdict(int)
        for o in outcomes:
            outcome_counts[o.status.value] += 1

        outcomes_continued = outcome_counts.get("continued", 0)
        outcomes_dropped_out = outcome_counts.get("dropped_out", 0)
        outcomes_pending = outcome_counts.get("pending", 0)
        outcomes_unknown = outcome_counts.get("unknown", 0)
        outcomes_total = outcomes_continued + outcomes_dropped_out + outcomes_pending + outcomes_unknown

        # Dropout rate: only among determinable outcomes
        determinable = outcomes_continued + outcomes_dropped_out
        dropout_rate = outcomes_dropped_out / determinable if determinable > 0 else 0.0

        # Coverage: % of students with at least one observation
        n_students = len(all_students) if all_students else 1  # avoid division by zero

        coverage_grades = len(students_with_grades & all_students) / n_students
        coverage_attendance = len(students_with_attendance & all_students) / n_students
        coverage_financial = len(students_with_financial & all_students) / n_students
        coverage_engagement = len(students_with_engagement & all_students) / n_students
        coverage_supports = len(students_with_supports & all_students) / n_students
        coverage_interventions = len(students_with_interventions & all_students) / n_students

        # Event counts: filter by students in this institution
        # For aggregate (institution_id == "__aggregate__"), count all events
        if institution_id == "__aggregate__":
            grade_events = len(grade_observations)
            attendance_events = len(attendance_observations)
            financial_events = len(financial_records)
            engagement_events_count = len(engagement_events)
            support_events = len(support_records)
            intervention_events = len(interventions)
        else:
            grade_events = sum(1 for g in grade_observations if g.student_id in all_students)
            attendance_events = sum(1 for a in attendance_observations if a.student_id in all_students)
            financial_events = sum(1 for f in financial_records if f.student_id in all_students)
            engagement_events_count = sum(1 for e in engagement_events if e.student_id in all_students)
            support_events = sum(1 for s in support_records if s.student_id in all_students)
            intervention_events = sum(1 for i in interventions if i.student_id in all_students)

        # Temporal depth: avg periods per student
        student_period_counts = defaultdict(set)
        for e in enrollments:
            student_period_counts[e.student_id].add(e.period_id)
        avg_temporal_depth = (
            sum(len(ps) for ps in student_period_counts.values()) / len(student_period_counts)
            if student_period_counts
            else 0.0
        )

        # Avg observations per student
        total_events = (
            len(grade_observations)
            + len(attendance_observations)
            + len(financial_records)
            + len(engagement_events)
            + len(support_records)
            + len(interventions)
        )
        avg_observations = total_events / n_students if n_students > 0 else 0.0

        # Period range
        period_dates = []
        for pid in periods_with_enrollments:
            p = period_map.get(pid)
            if p:
                period_dates.append((p.start_date, p.end_date))

        earliest = min((d[0] for d in period_dates), default=None)
        latest = max((d[1] for d in period_dates), default=None)

        return InstitutionAudit(
            institution_id=institution_id,
            cohorts=len(cohorts),
            students_unique=len(all_students),
            periods=len(periods_with_enrollments),
            snapshots=len(snapshots),
            outcomes_total=outcomes_total,
            outcomes_continued=outcomes_continued,
            outcomes_dropped_out=outcomes_dropped_out,
            outcomes_pending=outcomes_pending,
            outcomes_unknown=outcomes_unknown,
            dropout_rate=dropout_rate,
            coverage_grades=coverage_grades,
            coverage_attendance=coverage_attendance,
            coverage_financial=coverage_financial,
            coverage_engagement=coverage_engagement,
            coverage_supports=coverage_supports,
            coverage_interventions=coverage_interventions,
            grade_events=grade_events,
            attendance_events=attendance_events,
            financial_events=financial_events,
            engagement_events=engagement_events_count,
            support_events=support_events,
            intervention_events=intervention_events,
            avg_temporal_depth=avg_temporal_depth,
            avg_observations_per_student=avg_observations,
            earliest_period=earliest,
            latest_period=latest,
        )
