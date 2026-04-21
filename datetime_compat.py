"""Top-level shim for ``from datetime_compat import UTC``.

Agents and some app modules import this name as a **top-level** module. The
canonical implementation is ``shared_backend.datetime_compat``; this file
exists so ``PYTHONPATH=<repo-root>`` (as used by the requirement-parser
subprocess) resolves without relying on path order.

Do not remove while ``from datetime_compat import UTC`` appears under ``agents/``
or ``apps/``.
"""

from __future__ import annotations

from shared_backend.datetime_compat import UTC

__all__ = ["UTC"]
