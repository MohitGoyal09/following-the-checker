from datetime import datetime, timezone

from sourced.wayback import in_window, snapshot_url, to_wayback_ts


def _ms(y, m, d):
    return int(datetime(y, m, d, tzinfo=timezone.utc).timestamp() * 1000)


def test_timestamp_format():
    assert to_wayback_ts(_ms(2026, 3, 9)) == "20260309000000"


def test_window_is_7_days_before_to_30_days_after_note():
    note = _ms(2026, 3, 10)
    assert in_window("20260303000000", note)       # exactly 7 days before
    assert in_window("20260409000000", note)       # exactly 30 days after
    assert not in_window("20260302235959", note)   # just over 7 days before
    assert not in_window("20260409000001", note)   # just over 30 days after
    assert not in_window(None, note)


def test_snapshot_url_asks_for_original_bytes_without_toolbar():
    assert snapshot_url("20260310120000", "https://a.com/x?y=1") == \
        "https://web.archive.org/web/20260310120000id_/https://a.com/x?y=1"
