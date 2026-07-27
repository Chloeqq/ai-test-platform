from __future__ import annotations

from app.services.evie_ai.logging_guard import NaturalLanguageLoggingGuard


def test_logging_guard_suppresses_evie_ai_body_preview() -> None:
    preview = NaturalLanguageLoggingGuard().execute(
        path="/api/evie-ai/test-security",
        payload_preview='{"natural_steps":["secret request body"]}',
    )

    assert preview == "[EvieAi request body suppressed]"
    assert "secret request body" not in preview


def test_logging_guard_keeps_non_evie_ai_preview_unchanged() -> None:
    preview = NaturalLanguageLoggingGuard().execute(
        path="/api/auth/login",
        payload_preview='{"username":"tester"}',
    )

    assert preview == '{"username":"tester"}'
