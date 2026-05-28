from wifiops.concurrency import run_bounded


def test_run_bounded_returns_results_in_input_order():
    results = run_bounded([3, 1, 2], lambda value: value * 10, concurrency=2)

    assert results == [30, 10, 20]


def test_run_bounded_captures_exceptions_in_input_order():
    def worker(value):
        if value == 2:
            raise RuntimeError("failed")
        return value

    results = run_bounded([1, 2, 3], worker, concurrency=2)

    assert results[0] == 1
    assert isinstance(results[1], RuntimeError)
    assert str(results[1]) == "failed"
    assert results[2] == 3


def test_run_bounded_uses_at_least_one_worker():
    assert run_bounded([1], lambda value: value, concurrency=0) == [1]
