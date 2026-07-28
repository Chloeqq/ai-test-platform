"""Reusable implementation for the EvieAi code-quality gate."""

from .model import Comparison, Violation, compare_violations

__all__ = ["Comparison", "Violation", "compare_violations"]
