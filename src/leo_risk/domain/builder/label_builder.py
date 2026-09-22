"""Label Builder — materializes actual outcomes from enrollment history.

This module converts longitudinal enrollment data into versioned
StudentOutcome records suitable for survival analysis and classification.

Key invariants:
- No label is assigned DROPPED_OUT if the observation period is not closed.
- Ambiguous cases resolve to UNKNOWN or PENDING, never forced to 0/1.
- Build is idempotent: same input produces identical output.
- Supports filtering by institution, period, or time range.
"""

from collections import defaultdict
from datetime import datetime

from leo_risk.contracts.core import AcademicPeriod
from leo_risk.contracts.enrollment import Enrollment
from leo_risk.domain.censorship import CensorshipType
from leo_risk.domain.enums import OutcomeStatus
from leo_risk.domain.exit_reason import ExitReason
from leo_risk.domain.label_contract import LabelContract
from leo_risk.domain.label_version import LabelVersion

from .report import LabelBuildReport


class LabelBuildResult:
    """Result of a label build run.

    Contains the generated outcomes, a summary report, and metadata
    about the build process.
    """

    def __init__(
        self,
        outcomes: list,
        report: LabelBuildReport,
        version: LabelVersion,
        contract: LabelContract,
    ) -> None:
        self.outcomes = outcomes
        self.report = report
        self.version = version
        self.contract = contract

    def __len__(self) -> int:
        return len(self.outcomes)

    def __iter__(self):
        return iter(self.outcomes)

    def __getitem__(self, index):
        return self.outcomes[index]


class LabelBuilder:
    """Builds versioned StudentOutcome records from enrollment history.

    Usage:
        builder = LabelBuilder(contract, version)
        result = builder.run(enrollments, periods)
        for outcome in result:
            print(outcome.status)

    The builder is stateless and reusable. Each run() call is independent.
    """

    def __init__(
        self,
        contract: LabelContract | None = None,
        version: LabelVersion | None = None,
    ) -> None:
        self.contract = contract or LabelContract(
            version="1.0.0",
            description="Default label contract",
        )
        self.version = version or LabelVersion(
            version="1.0.0",
            description="Default label version",
        )

    def run(
        self,
        enrollments: list[Enrollment],
        periods: list[AcademicPeriod],
        *,
        institution_id: str | None = None,
        period_ids: list[str] | None = None,
        date_range: tuple[datetime, datetime] | None = None,
        as_of: datetime | None = None,
    ) -> LabelBuildResult:
        """Build StudentOutcome records from enrollment history.

        Args:
            enrollments: All enrollment records.
            periods: All academic period definitions.
            institution_id: Optional filter — only process this institution.
            period_ids: Optional filter — only process these reference periods.
            date_range: Optional filter — only process periods within this range.
            as_of: Optional cutoff — treat periods not closed by this time as PENDING.

        Returns:
            LabelBuildResult with outcomes and report.
        """
        # Index periods by period_id for O(1) lookup
        period_map = {p.period_id: p for p in periods}

        # Group enrollments by (student_id, institution_id, program_id)
        enrollment_groups = self._group_enrollments(enrollments)

        # Sort periods chronologically by start_date
        sorted_periods = sorted(periods, key=lambda p: p.start_date)

        # Apply filters
        filtered_periods = self._filter_periods(
            sorted_periods,
            institution_id=institution_id,
            period_ids=period_ids,
            date_range=date_range,
        )

        # Generate outcomes
        outcomes = []
        for group_key, group_enrollments in enrollment_groups.items():
            student_id, inst_id, program_id = group_key

            # Skip if filtering by institution and this doesn't match
            if institution_id and inst_id != institution_id:
                continue

            # Index enrollments by period_id for this student
            enrollment_by_period: dict[str, Enrollment] = {}
            for e in group_enrollments:
                enrollment_by_period[e.period_id] = e

            # For each reference period T, find the next period T+1
            for ref_period in filtered_periods:
                ref_id = ref_period.period_id

                # Student must have enrollment in reference period
                if ref_id not in enrollment_by_period:
                    continue

                # Find the next period chronologically
                next_period = self._find_next_period(
                    ref_id, sorted_periods, period_map
                )
                if next_period is None:
                    continue

                next_id = next_period.period_id

                # Build the outcome for this (student, T, T+1) triple
                outcome = self._build_outcome(
                    student_id=student_id,
                    institution_id=inst_id,
                    program_id=program_id,
                    ref_period=ref_period,
                    next_period=next_period,
                    ref_enrollment=enrollment_by_period[ref_id],
                    next_enrollment=enrollment_by_period.get(next_id),
                    period_map=period_map,
                    as_of=as_of,
                )
                outcomes.append(outcome)

        # Sort outcomes deterministically
        outcomes.sort(
            key=lambda o: (o.student_id, o.reference_period, o.observation_period)
        )

        # Build report
        report = self._build_report(outcomes, {
            "institution_id": institution_id or "all",
            "period_ids": ",".join(period_ids) if period_ids else "all",
            "date_range": f"{date_range[0].isoformat()}-{date_range[1].isoformat()}" if date_range else "all",
            "as_of": as_of.isoformat() if as_of else "none",
        })

        return LabelBuildResult(
            outcomes=outcomes,
            report=report,
            version=self.version,
            contract=self.contract,
        )

    def _group_enrollments(
        self, enrollments: list[Enrollment]
    ) -> dict[tuple[str, str, str], list[Enrollment]]:
        """Group enrollments by (student_id, institution_id, program_id)."""
        groups: dict[tuple[str, str, str], list[Enrollment]] = defaultdict(list)
        for e in enrollments:
            groups[(e.student_id, e.institution_id, e.program_id)].append(e)
        return dict(groups)

    def _filter_periods(
        self,
        periods: list[AcademicPeriod],
        *,
        institution_id: str | None = None,
        period_ids: list[str] | None = None,
        date_range: tuple[datetime, datetime] | None = None,
    ) -> list[AcademicPeriod]:
        """Filter periods by institution, period IDs, or date range."""
        result = periods

        if institution_id:
            result = [p for p in result if p.institution_id == institution_id]

        if period_ids:
            period_id_set = set(period_ids)
            result = [p for p in result if p.period_id in period_id_set]

        if date_range:
            start, end = date_range
            result = [
                p for p in result
                if start <= datetime.fromisoformat(p.start_date) <= end
            ]

        return result

    def _find_next_period(
        self,
        current_period_id: str,
        sorted_periods: list[AcademicPeriod],
        period_map: dict[str, AcademicPeriod],
    ) -> AcademicPeriod | None:
        """Find the next chronological period after current_period_id."""
        current = period_map.get(current_period_id)
        if current is None:
            return None

        current_start = datetime.fromisoformat(current.start_date)

        # Find the period with the smallest start_date that is after current
        next_period = None
        for p in sorted_periods:
            if p.period_id == current_period_id:
                continue
            p_start = datetime.fromisoformat(p.start_date)
            if (p_start > current_start
                    and (next_period is None or p_start < datetime.fromisoformat(next_period.start_date))):
                next_period = p

        return next_period

    def _is_period_closed(
        self,
        period: AcademicPeriod,
        as_of: datetime | None = None,
    ) -> bool:
        """Check if a period is closed for analysis.

        A period is closed if:
        1. period.is_closed is True, OR
        2. as_of is provided and as_of > period.end_date
        """
        if period.is_closed:
            return True

        if as_of is not None:
            end_date = datetime.fromisoformat(period.end_date)
            # Normalize to timezone-naive for comparison
            if as_of.tzinfo is not None and end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=as_of.tzinfo)
            return as_of > end_date

        return False

    def _build_outcome(
        self,
        student_id: str,
        institution_id: str,
        program_id: str,
        ref_period: AcademicPeriod,
        next_period: AcademicPeriod,
        ref_enrollment: Enrollment,
        next_enrollment: Enrollment | None,
        period_map: dict[str, AcademicPeriod],
        as_of: datetime | None,
    ):
        """Build a single StudentOutcome for a (student, T, T+1) triple."""
        # Determine if the observation period (T+1) is closed
        next_closed = self._is_period_closed(next_period, as_of)

        # If observation period is not closed → PENDING
        if not next_closed:
            from leo_risk.domain.entities.student_outcome import StudentOutcome

            return StudentOutcome(
                student_id=student_id,
                institution_id=institution_id,
                program_id=program_id,
                reference_period=ref_period.period_id,
                observation_period=next_period.period_id,
                status=OutcomeStatus.PENDING,
                exit_reason=ExitReason.NONE,
                censorship_type=CensorshipType.NOT_CENSORABLE,
                calendar_type=ref_period.calendar_type,
                confidence_score=1.0,
            )

        # Observation period IS closed — determine outcome
        if (next_enrollment is not None
                and (next_enrollment.is_active or next_enrollment.status.value in (
                    "enrolled", "completed"
                ))):
            from leo_risk.domain.entities.student_outcome import StudentOutcome

            return StudentOutcome(
                student_id=student_id,
                institution_id=institution_id,
                program_id=program_id,
                reference_period=ref_period.period_id,
                observation_period=next_period.period_id,
                status=OutcomeStatus.CONTINUED,
                exit_reason=ExitReason.NONE,
                censorship_type=CensorshipType.RIGHT_CENSORED,
                calendar_type=ref_period.calendar_type,
                    confidence_score=1.0,
                )

        # Student does NOT have enrollment in T+1 (or enrollment is invalid)
        # Determine exit reason from T enrollment
        raw_reason = ref_enrollment.exit_reason
        exit_reason = self.contract.resolve_exit_reason(raw_reason)

        # Determine if this counts as dropout
        is_dropout = self.contract.is_dropout_exit(exit_reason)

        if is_dropout:
            from leo_risk.domain.entities.student_outcome import StudentOutcome

            return StudentOutcome(
                student_id=student_id,
                institution_id=institution_id,
                program_id=program_id,
                reference_period=ref_period.period_id,
                observation_period=next_period.period_id,
                status=OutcomeStatus.DROPPED_OUT,
                exit_reason=exit_reason,
                censorship_type=CensorshipType.OBSERVED,
                calendar_type=ref_period.calendar_type,
                confidence_score=1.0,
            )

        # Non-dropout exit (graduation, transfer, authorized leave)
        # or exit reason is NOT_REPORTED → UNKNOWN
        from leo_risk.domain.entities.student_outcome import StudentOutcome

        return StudentOutcome(
            student_id=student_id,
            institution_id=institution_id,
            program_id=program_id,
            reference_period=ref_period.period_id,
            observation_period=next_period.period_id,
            status=OutcomeStatus.UNKNOWN,
            exit_reason=ExitReason.NOT_REPORTED,
            censorship_type=CensorshipType.NOT_CENSORABLE,
            calendar_type=ref_period.calendar_type,
            confidence_score=0.5,
        )

    def _build_report(
        self,
        outcomes: list,
        filters: dict[str, str],
    ) -> LabelBuildReport:
        """Build a summary report from the generated outcomes."""
        counts_by_status: dict[str, int] = defaultdict(int)
        counts_by_censorship: dict[str, int] = defaultdict(int)
        counts_by_exit_reason: dict[str, int] = defaultdict(int)
        usable_survival = 0
        usable_classification = 0
        excluded = 0
        institutions: set[str] = set()
        students: set[str] = set()

        for o in outcomes:
            counts_by_status[o.status.value] += 1
            counts_by_censorship[o.censorship_type.value] += 1
            counts_by_exit_reason[o.exit_reason.value] += 1

            institutions.add(o.institution_id)
            students.add(o.student_id)

            if o.censorship_type != CensorshipType.NOT_CENSORABLE:
                usable_survival += 1

            if o.status in (OutcomeStatus.CONTINUED, OutcomeStatus.DROPPED_OUT):
                usable_classification += 1

            if o.status in (OutcomeStatus.PENDING, OutcomeStatus.UNKNOWN):
                excluded += 1

        return LabelBuildReport(
            total_pairs=len(outcomes),
            counts_by_status=dict(counts_by_status),
            counts_by_censorship=dict(counts_by_censorship),
            counts_by_exit_reason=dict(counts_by_exit_reason),
            usable_for_survival=usable_survival,
            usable_for_classification=usable_classification,
            excluded_from_ml=excluded,
            filters_applied=filters,
            institutions_processed=len(institutions),
            students_processed=len(students),
        )
