"""conftest.py — Sets JAVA_HOME before any tests run (required for PySpark)."""
import src.config  # noqa: F401 — triggers JAVA_HOME bootstrap as a side effect
