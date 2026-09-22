"""Data availability audit models.

Structured reports that answer: "What data do we actually have?"
"""

from pydantic import BaseModel, Field


class InstitutionAudit(BaseModel):
    """Audit metrics for a single institution."""

    institution_id: str

    # Entity counts
    cohorts: int = Field(default=0, description="Number of distinct (program, period) cohorts")
    students_unique: int = Field(default=0, description="Unique students with at least one enrollment")
    periods: int = Field(default=0, description="Distinct academic periods with enrollments")
    snapshots: int = Field(default=0, description="(student, period) enrollment pairs")

    # Outcome counts
    outcomes_total: int = Field(default=0, description="Total labeled outcomes")
    outcomes_continued: int = Field(default=0, description="CONTINUED outcomes")
    outcomes_dropped_out: int = Field(default=0, description="DROPPED_OUT outcomes (real observed dropouts)")
    outcomes_pending: int = Field(default=0, description="PENDING outcomes (period not closed)")
    outcomes_unknown: int = Field(default=0, description="UNKNOWN outcomes (ambiguous data)")

    # Rates
    dropout_rate: float = Field(
        default=0.0,
        description="Dropout rate = dropped_out / (continued + dropped_out). "
        "Excludes PENDING and UNKNOWN.",
    )

    # Coverage: % of students with at least one observation
    coverage_grades: float = Field(default=0.0, ge=0.0, le=1.0, description="Grade coverage")
    coverage_attendance: float = Field(default=0.0, ge=0.0, le=1.0, description="Attendance coverage")
    coverage_financial: float = Field(default=0.0, ge=0.0, le=1.0, description="Financial coverage")
    coverage_engagement: float = Field(default=0.0, ge=0.0, le=1.0, description="Engagement coverage")
    coverage_supports: float = Field(default=0.0, ge=0.0, le=1.0, description="Support coverage")
    coverage_interventions: float = Field(default=0.0, ge=0.0, le=1.0, description="Intervention coverage")

    # Event counts (raw, not unique students)
    grade_events: int = Field(default=0, description="Total grade observation events")
    attendance_events: int = Field(default=0, description="Total attendance observation events")
    financial_events: int = Field(default=0, description="Total financial status records")
    engagement_events: int = Field(default=0, description="Total engagement events")
    support_events: int = Field(default=0, description="Total support records")
    intervention_events: int = Field(default=0, description="Total intervention records")

    # Temporal depth
    avg_temporal_depth: float = Field(
        default=0.0,
        description="Average number of periods per student (enrollment depth)",
    )
    avg_observations_per_student: float = Field(
        default=0.0,
        description="Average total observations (grades + attendance + financial + "
        "engagement + supports + interventions) per student",
    )

    # Period range
    earliest_period: str | None = Field(default=None, description="Earliest period start_date")
    latest_period: str | None = Field(default=None, description="Latest period end_date")


class AuditReport(BaseModel):
    """Complete data availability audit report."""

    # Per-institution breakdown
    institutions: list[InstitutionAudit] = Field(default_factory=list)

    # Aggregate (all institutions combined)
    aggregate: InstitutionAudit = Field(default_factory=lambda: InstitutionAudit(institution_id="__aggregate__"))

    # Key summary numbers
    total_real_dropouts: int = Field(
        default=0,
        description="DROPPED_OUT outcomes across all institutions. "
        "This is the most important number for training.",
    )
    total_usable_outcomes: int = Field(
        default=0,
        description="Outcomes usable for ML (CONTINUED + DROPPED_OUT only)",
    )
    total_excluded_outcomes: int = Field(
        default=0,
        description="Outcomes excluded from ML (PENDING + UNKNOWN)",
    )

    def summary(self) -> str:
        """Human-readable summary for console output."""
        lines = [
            "=" * 72,
            "DATA AVAILABILITY AUDIT REPORT",
            "=" * 72,
            "",
            "CRITICAL NUMBER:",
            f"  Real observed dropouts for training: {self.total_real_dropouts}",
            f"  Usable outcomes (continued + dropped_out): {self.total_usable_outcomes}",
            f"  Excluded outcomes (pending + unknown): {self.total_excluded_outcomes}",
            "",
        ]

        if self.institutions:
            lines.append("PER-INSTITUTION BREAKDOWN:")
            lines.append("-" * 72)
            for inst in self.institutions:
                lines.extend(self._format_institution(inst))
            lines.append("")

        lines.append("AGGREGATE (all institutions):")
        lines.append("-" * 72)
        lines.extend(self._format_institution(self.aggregate))
        lines.append("")
        lines.append("=" * 72)

        return "\n".join(lines)

    def _format_institution(self, inst: InstitutionAudit) -> list[str]:
        lines = [
            f"  Institution: {inst.institution_id}",
            f"    Cohorts: {inst.cohorts}",
            f"    Students: {inst.students_unique}",
            f"    Periods: {inst.periods}",
            f"    Snapshots (student×period): {inst.snapshots}",
            "",
            "    Outcomes:",
            f"      Total: {inst.outcomes_total}",
            f"      Continued: {inst.outcomes_continued}",
            f"      Dropped out: {inst.outcomes_dropped_out}",
            f"      Pending: {inst.outcomes_pending}",
            f"      Unknown: {inst.outcomes_unknown}",
            f"      Dropout rate: {inst.dropout_rate:.1%}",
            "",
            "    Coverage (% students with ≥1 observation):",
            f"      Grades: {inst.coverage_grades:.1%}",
            f"      Attendance: {inst.coverage_attendance:.1%}",
            f"      Financial: {inst.coverage_financial:.1%}",
            f"      Engagement: {inst.coverage_engagement:.1%}",
            f"      Supports: {inst.coverage_supports:.1%}",
            f"      Interventions: {inst.coverage_interventions:.1%}",
            "",
            "    Event counts:",
            f"      Grade events: {inst.grade_events}",
            f"      Attendance events: {inst.attendance_events}",
            f"      Financial events: {inst.financial_events}",
            f"      Engagement events: {inst.engagement_events}",
            f"      Support events: {inst.support_events}",
            f"      Intervention events: {inst.intervention_events}",
            "",
            "    Temporal:",
            f"      Avg periods per student: {inst.avg_temporal_depth:.1f}",
            f"      Avg observations per student: {inst.avg_observations_per_student:.1f}",
        ]
        if inst.earliest_period and inst.latest_period:
            lines.append(f"      Period range: {inst.earliest_period} → {inst.latest_period}")
        return lines
