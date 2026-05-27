"""Runtime compatibility helpers for the containerized web service.

This project still needs to run in environments that expose Python 3.10.
Python 3.11 added ``datetime.UTC``; several modules import it directly.
Make that symbol available early so those imports keep working without
touching every call site.
"""

from datetime import timezone
import datetime as _datetime

if not hasattr(_datetime, "UTC"):
    _datetime.UTC = timezone.utc  # type: ignore[attr-defined]
