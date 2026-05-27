"""download.py - Ingest raw CSVs into the Bronze layer."""

import logging
import shutil
from datetime import date
from pathlib import Path

from src.config import ARCHIVE_DIR, BRONZE_PATH, EXPECTED_FILES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def ingest_to_bronze(
    archive_dir: Path = ARCHIVE_DIR,
    bronze_path: Path = BRONZE_PATH,
    run_date: date | None = None,
) -> Path:
    """
    Copy CSVs from archive_dir into bronze_path/{run_date}/.

    Returns the destination folder path.
    Raises FileNotFoundError if any expected source file is missing.
    """
    if run_date is None:
        run_date = date.today()

    dest_folder = bronze_path / str(run_date)

    # --- Idempotency check ---
    if dest_folder.exists() and any(dest_folder.iterdir()):
        logger.info("Bronze folder %s already populated — skipping ingestion.", dest_folder)
        return dest_folder

    # --- Validate source directory ---
    if not archive_dir.exists():
        raise FileNotFoundError(f"Archive directory not found: {archive_dir}")

    logger.info("Starting ingestion from %s → %s", archive_dir, dest_folder)

    # --- Check all expected files exist before copying anything ---
    missing = []
    for fname in EXPECTED_FILES:
        src = archive_dir / fname
        if not src.exists():
            missing.append(fname)

    if missing:
        raise FileNotFoundError(
            f"Missing {len(missing)} expected file(s) in archive: {missing}"
        )

    # --- Create destination and copy ---
    dest_folder.mkdir(parents=True, exist_ok=True)

    copied = 0
    for fname in EXPECTED_FILES:
        src = archive_dir / fname
        dst = dest_folder / fname
        shutil.copy2(src, dst)
        file_size_kb = src.stat().st_size / 1024
        logger.info("  Copied %-55s  (%.1f KB)", fname, file_size_kb)
        copied += 1

    logger.info("Ingestion complete. %d files written to %s", copied, dest_folder)
    return dest_folder


def get_latest_bronze_folder(bronze_path: Path = BRONZE_PATH) -> Path:
    """Return the most recent date-partitioned bronze folder."""
    dated_folders = sorted(
        [f for f in bronze_path.iterdir() if f.is_dir()],
        key=lambda p: p.name,
        reverse=True,
    )
    if not dated_folders:
        raise FileNotFoundError(f"No bronze folders found in {bronze_path}")
    latest = dated_folders[0]
    logger.info("Latest bronze folder: %s", latest)
    return latest


if __name__ == "__main__":
    folder = ingest_to_bronze()
    print(f"Bronze data available at: {folder}")
