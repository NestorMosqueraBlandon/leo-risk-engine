"""Export audit reports to various formats.

Supports: console (print), JSON, CSV, Parquet.
"""

import json
from pathlib import Path

from leo_risk.domain.audit.report import AuditReport


def export_console(report: AuditReport) -> None:
    """Print audit report to console."""
    print(report.summary())


def export_json(report: AuditReport, path: str | Path) -> Path:
    """Export audit report as JSON.

    Args:
        report: The audit report.
        path: Output file path.

    Returns:
        Path to the written file.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = json.loads(report.model_dump_json(indent=2))
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    return path


def export_csv(report: AuditReport, path: str | Path) -> Path:
    """Export per-institution audit as CSV.

    Args:
        report: The audit report.
        path: Output file path (without extension). Creates {path}_institutions.csv.

    Returns:
        Path to the written file.
    """
    import csv

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    csv_path = path.with_suffix(".csv") if path.suffix != ".csv" else path

    if not report.institutions:
        csv_path.write_text("institution_id\n")
        return csv_path

    # Get field names from first institution
    fieldnames = list(report.institutions[0].model_fields.keys())

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for inst in report.institutions:
            writer.writerow(inst.model_dump())

    return csv_path


def export_parquet(report: AuditReport, path: str | Path) -> Path:
    """Export per-institution audit as Parquet.

    Requires: pip install pyarrow or fastparquet.

    Args:
        report: The audit report.
        path: Output file path.

    Returns:
        Path to the written file.
    """
    try:
        import polars as pl
    except ImportError:
        raise ImportError(
            "Parquet export requires polars. Install with: pip install polars"
        ) from None

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not report.institutions:
        # Write empty dataframe
        df = pl.DataFrame({"institution_id": []})
        df.write_parquet(path)
        return path

    # Convert to polars DataFrame
    data = [inst.model_dump() for inst in report.institutions]
    df = pl.DataFrame(data)
    df.write_parquet(path)

    return path
