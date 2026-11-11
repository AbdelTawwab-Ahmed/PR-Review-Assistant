from app.application.caching import analysis_key, get_or_compute, pr_diff_key
from app.infrastructure.cache.memory_cache import InMemoryCache


def test_repo_name_is_case_insensitive_in_keys() -> None:
    assert pr_diff_key("Org/Repo", "abc") == pr_diff_key("org/repo", "abc")


def test_analysis_key_changes_with_version() -> None:
    assert analysis_key("o/r", "abc", "security", "v1") != analysis_key(
        "o/r", "abc", "security", "v2"
    )


async def test_producer_runs_once() -> None:
    cache = InMemoryCache()
    calls = 0

    async def producer() -> dict[str, int]:
        nonlocal calls
        calls += 1
        return {"x": 1}

    assert await get_or_compute(cache, "k", producer) == {"x": 1}
    assert await get_or_compute(cache, "k", producer) == {"x": 1}
    assert calls == 1


async def test_none_results_are_not_cached() -> None:
    cache = InMemoryCache()
    calls = 0

    async def producer() -> None:
        nonlocal calls
        calls += 1

    await get_or_compute(cache, "k", producer)
    await get_or_compute(cache, "k", producer)
    assert calls == 2
