"""Errors raised by the benchmark harness."""

from __future__ import annotations

from groundguard.core.errors import GroundGuardError


class BenchmarkError(GroundGuardError):
    """Base class for benchmark harness errors."""


class DatasetError(BenchmarkError):
    """A dataset is missing, malformed, or fails schema validation."""


class RunFileError(BenchmarkError):
    """A benchmark run file is missing, malformed, or incompatible."""
