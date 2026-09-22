from pydantic import BaseModel, Field


class LabelBuildReport(BaseModel):
    """Summary of label build results.

    Provides counts by outcome status, censorship type, and usability
    for ML training. Generated after each LabelBuilder.run() call.
    """

    total_pairs: int = Field(default=0, description="Total (student, period) pairs processed")
    counts_by_status: dict[str, int] = Field(
        default_factory=dict,
        description="Count of outcomes per OutcomeStatus value",
    )
    counts_by_censorship: dict[str, int] = Field(
        default_factory=dict,
        description="Count of outcomes per CensorshipType value",
    )
    counts_by_exit_reason: dict[str, int] = Field(
        default_factory=dict,
        description="Count of outcomes per ExitReason value",
    )
    usable_for_survival: int = Field(
        default=0,
        description="Outcomes usable for survival analysis (censorship != NOT_CENSORABLE)",
    )
    usable_for_classification: int = Field(
        default=0,
        description="Outcomes usable for binary classification (CONTINUED or DROPPED_OUT only)",
    )
    excluded_from_ml: int = Field(
        default=0,
        description="Outcomes excluded from ML (PENDING or UNKNOWN)",
    )
    filters_applied: dict[str, str] = Field(
        default_factory=dict,
        description="Filters applied to this build run",
    )
    institutions_processed: int = Field(
        default=0,
        description="Number of unique institutions in the output",
    )
    students_processed: int = Field(
        default=0,
        description="Number of unique students in the output",
    )

    @property
    def utilization_rate_survival(self) -> float:
        """Percentage of outcomes usable for survival analysis."""
        if self.total_pairs == 0:
            return 0.0
        return self.usable_for_survival / self.total_pairs

    @property
    def utilization_rate_classification(self) -> float:
        """Percentage of outcomes usable for binary classification."""
        if self.total_pairs == 0:
            return 0.0
        return self.usable_for_classification / self.total_pairs

    def summary(self) -> str:
        """Human-readable summary of the build report."""
        lines = [
            "Label Build Report",
            f"  Total pairs: {self.total_pairs}",
            f"  Usable for survival: {self.usable_for_survival} ({self.utilization_rate_survival:.1%})",
            f"  Usable for classification: {self.usable_for_classification}"
            f" ({self.utilization_rate_classification:.1%})",
            f"  Excluded from ML: {self.excluded_from_ml}",
            f"  Institutions: {self.institutions_processed}",
            f"  Students: {self.students_processed}",
            "",
            "  By status:",
        ]
        for status, count in sorted(self.counts_by_status.items()):
            lines.append(f"    {status}: {count}")
        lines.append("")
        lines.append("  By censorship:")
        for censorship, count in sorted(self.counts_by_censorship.items()):
            lines.append(f"    {censorship}: {count}")
        lines.append("")
        lines.append("  By exit reason:")
        for reason, count in sorted(self.counts_by_exit_reason.items()):
            lines.append(f"    {reason}: {count}")
        if self.filters_applied:
            lines.append("")
            lines.append("  Filters applied:")
            for key, value in self.filters_applied.items():
                lines.append(f"    {key}: {value}")
        return "\n".join(lines)
