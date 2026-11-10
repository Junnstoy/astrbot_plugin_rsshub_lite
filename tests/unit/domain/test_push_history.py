from __future__ import annotations

import pytest
from astrbot_plugin_rsshub_lite.src.domain.entities.push_history import (
    MAX_FAIL_REASON_LENGTH,
    PushHistory,
)


def _make_history() -> PushHistory:
    return PushHistory(
        sub_id=1,
        user_id="user-1",
        feed_id=10,
    )


@pytest.mark.parametrize(
    ("method_name", "expected_retry_count"),
    [
        ("record_first_failure", 0),
        ("record_retry_failure", 1),
        ("mark_failed", 0),
        ("mark_stopped", 0),
    ],
)
def test_push_history_failure_reason_writers_truncate_overlong_values(
    method_name: str, expected_retry_count: int
):
    history = _make_history()
    overlong_reason = "x" * (MAX_FAIL_REASON_LENGTH + 128)

    getattr(history, method_name)(overlong_reason)

    assert history.fail_reason is not None
    assert history.fail_reason != overlong_reason
    assert len(history.fail_reason) <= MAX_FAIL_REASON_LENGTH
    assert history.retry_count == expected_retry_count


@pytest.mark.parametrize(
    "method_name",
    [
        "record_first_failure",
        "record_retry_failure",
        "mark_failed",
        "mark_stopped",
    ],
)
def test_push_history_failure_reason_writers_use_fallback_for_empty_values(
    method_name: str,
):
    history = _make_history()

    getattr(history, method_name)("   ")

    assert history.fail_reason is None


def test_push_history_agent_source_allows_null_sub_and_feed():
    history = PushHistory(
        source_type="agent",
        source_key="agent:test",
        sub_id=None,
        user_id="user-1",
        feed_id=None,
        raw_xml="<entry><p>Hello</p></entry>",
    )

    assert history.is_agent_source() is True
    assert history.sub_id is None
    assert history.feed_id is None
    assert history.raw_xml == "<entry><p>Hello</p></entry>"


def test_push_history_agent_source_default_false_for_feed():
    history = _make_history()

    assert history.is_agent_source() is False


def test_mark_success_keeps_empty_fail_reason_empty():
    history = _make_history()

    history.mark_success()

    assert history.fail_reason is None


def test_mark_success_clears_previous_fail_reason():
    history = _make_history()
    history.record_first_failure("timeout")

    history.mark_success()

    assert history.fail_reason is None
