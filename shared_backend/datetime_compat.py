"""Backward-compatible UTC constant for Python < 3.11."""

from __future__ import annotations

import datetime
import sys

if sys.version_info >= (3, 11):
    UTC = datetime.UTC
else:
    UTC = datetime.timezone.utc
