from src.utils.backoff import backoff_delay, backoff_schedule


def test_backoff_grows_exponentially():
    assert backoff_delay(1, base_seconds=2, cap_seconds=300) == 2
    assert backoff_delay(2, base_seconds=2, cap_seconds=300) == 4
    assert backoff_delay(3, base_seconds=2, cap_seconds=300) == 8
    assert backoff_delay(4, base_seconds=2, cap_seconds=300) == 16


def test_backoff_is_capped():
    assert backoff_delay(20, base_seconds=2, cap_seconds=300) == 300


def test_schedule():
    assert backoff_schedule(3, 2, 300) == [2, 4, 8]
