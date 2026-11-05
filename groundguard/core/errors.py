"""Typed errors shared by GroundGuard library code."""

from __future__ import annotations


class GroundGuardError(Exception):
    """Base class for all GroundGuard library errors."""


class InvalidInput(GroundGuardError):
    """The caller supplied input the library cannot evaluate."""
