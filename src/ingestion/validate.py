"""
validate.py - Schema validation and data quality checks for Bronze CSVs.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from src.config import (
    DATE_COLUMNS,
    EXPECTED_FILES,
    EXPECTED_SCHEMAS,
    NOT_NULL_COLUMNS,
    BRONZE_PATH,
)
from src.ingestion.download import get_latest_bronze_folder

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@dataclass
class ValidationReport:
    file_name: str
    status: str                          # "PASS" | "FAIL" | "CRITICAL"
    row_count: int = 0
    checks_passed: list[str] = field(default_factory=list)
    checks_failed: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def is_ok(self) -> bool:
        return self.status == "PASS"

    def summary(self) -> str:
        return (
            f"[{self.status}] {self.file_name} | "
            f"rows={self.row_count} | "
            f"passed={len(self.checks_passed)} | "
            f"failed={len(self.checks_failed)}"
        )


def validate_file(csv_path: Path, file_name: str) -> ValidationReport:
    """Run all checks on a single CSV file. Returns a ValidationReport."""
    report = ValidationReport(file_name=file_name, status="PASS")

    if not csv_path.exists():
        report.status = "CRITICAL"
        report.checks_failed.append("file_exists")
        report.details["file_exists"] = f"File not found: {csv_path}"
        logger.critical("CRITICAL — File not found: %s", csv_path)
        raise FileNotFoundError(f"Expected CSV not found: {csv_path}")

    report.checks_passed.append("file_exists")

    try:
        df = pd.read_csv(csv_path, low_memory=False)
    except Exception as exc:
        report.status = "CRITICAL"
        report.checks_failed.append("csv_readable")
        report.details["csv_readable"] = str(exc)
        raise RuntimeError(f"Cannot read {csv_path}: {exc}") from exc

    report.row_count = len(df)
    report.checks_passed.append("csv_readable")

    if len(df) == 0:
        report.status = "CRITICAL"
        report.checks_failed.append("row_count_gt_zero")
        report.details["row_count"] = 0
        raise ValueError(f"Empty file: {file_name}")

    report.checks_passed.append("row_count_gt_zero")
    report.details["row_count"] = len(df)

    expected_cols = set(EXPECTED_SCHEMAS.get(file_name, {}).keys())
    actual_cols = set(df.columns.str.strip())
    df.columns = df.columns.str.strip()

    if expected_cols:
        missing_cols = expected_cols - actual_cols
        extra_cols = actual_cols - expected_cols

        if missing_cols:
            report.status = "CRITICAL"
            report.checks_failed.append("column_names_match")
            report.details["missing_columns"] = sorted(missing_cols)
            report.details["extra_columns"] = sorted(extra_cols)
            raise ValueError(
                f"{file_name}: missing expected columns {missing_cols}"
            )

        if extra_cols:
            logger.warning("%s has extra columns (non-critical): %s", file_name, extra_cols)
            report.details["extra_columns"] = sorted(extra_cols)

        report.checks_passed.append("column_names_match")

    key_cols = NOT_NULL_COLUMNS.get(file_name, [])
    null_issues = {}
    for col in key_cols:
        if col not in df.columns:
            continue
        null_count = int(df[col].isna().sum())
        if null_count > 0:
            null_issues[col] = null_count

    if null_issues:
        report.status = "FAIL"
        report.checks_failed.append("no_key_nulls")
        report.details["null_counts"] = null_issues
        logger.warning("%s — null values in key columns: %s", file_name, null_issues)
    else:
        report.checks_passed.append("no_key_nulls")

    dup_count = int(df.duplicated().sum())
    report.details["duplicate_rows"] = dup_count
    if dup_count > 0:
        logger.warning("%s — %d duplicate rows found", file_name, dup_count)
        report.checks_failed.append("no_full_duplicates")
    else:
        report.checks_passed.append("no_full_duplicates")

    date_cols = DATE_COLUMNS.get(file_name, [])
    unparseable = []
    for col in date_cols:
        if col not in df.columns:
            continue
        non_null = df[col].dropna()
        if non_null.empty:
            continue
        try:
            pd.to_datetime(non_null, errors="raise")
        except Exception:
            bad_count = int(pd.to_datetime(non_null, errors="coerce").isna().sum())
            unparseable.append(f"{col} ({bad_count} unparseable)")

    if unparseable:
        report.status = "FAIL"
        report.checks_failed.append("date_columns_parseable")
        report.details["unparseable_dates"] = unparseable
        logger.warning("%s — unparseable date values: %s", file_name, unparseable)
    else:
        report.checks_passed.append("date_columns_parseable")

    # Final status update
    if report.checks_failed and report.status == "PASS":
        report.status = "FAIL"

    return report


def validate_bronze(bronze_folder: Path | None = None) -> list[ValidationReport]:
    """
    Validate all expected CSVs in the given bronze folder.
    Uses the latest bronze folder if none provided.
    """
    if bronze_folder is None:
        bronze_folder = get_latest_bronze_folder(BRONZE_PATH)

    logger.info("Validating bronze data in: %s", bronze_folder)
    reports = []

    for file_name in EXPECTED_FILES:
        csv_path = bronze_folder / file_name
        logger.info("--- Validating %s ---", file_name)
        try:
            report = validate_file(csv_path, file_name)
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            report = ValidationReport(
                file_name=file_name,
                status="CRITICAL",
                checks_failed=["critical_error"],
                details={"error": str(exc)},
            )

        logger.info(report.summary())
        reports.append(report)

    passed = sum(1 for r in reports if r.is_ok())
    logger.info(
        "Validation complete: %d/%d files passed", passed, len(reports)
    )
    return reports


if __name__ == "__main__":
    reports = validate_bronze()
    for r in reports:
        print(r.summary())
