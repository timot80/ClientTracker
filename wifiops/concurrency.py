from __future__ import annotations

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TypeVar


T = TypeVar("T")
R = TypeVar("R")


def run_bounded(
    items: Sequence[T],
    worker: Callable[[T], R],
    concurrency: int,
) -> list[R | Exception]:
    max_workers = max(1, min(max(1, concurrency), len(items) or 1))
    results: list[R | Exception | None] = [None] * len(items)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(worker, item): index for index, item in enumerate(items)}
        for future in as_completed(futures):
            index = futures[future]
            try:
                results[index] = future.result()
            except Exception as exc:
                results[index] = exc
    return [result for result in results if result is not None]
