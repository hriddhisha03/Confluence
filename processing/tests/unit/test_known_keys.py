from datetime import datetime, timezone

from app.models.schemas import RawEvent
from app.services.known_keys import KnownKeysCache
from app.services.validator import build_clean_event

FIXED_NOW = datetime(2026, 10, 11, 12, 0, 0, tzinfo=timezone.utc)


def make_loader(result=None, error=None):
    calls = {"n": 0}

    async def loader():
        calls["n"] += 1
        if error is not None:
            raise error
        return result

    return loader, calls


async def test_refresh_replaces_keys_from_registry():
    loader, _ = make_loader({"browser", "referrer", "campaign"})
    cache = KnownKeysCache(loader, fallback={"browser"}, refresh_seconds=10)
    await cache.refresh()
    assert cache.get() == {"browser", "referrer", "campaign"}


async def test_fallback_used_before_first_refresh():
    loader, _ = make_loader({"x"})
    cache = KnownKeysCache(loader, fallback={"browser", "referrer"}, refresh_seconds=10)
    assert cache.get() == {"browser", "referrer"}


async def test_failed_refresh_keeps_previous_keys():
    loader, _ = make_loader(error=ConnectionError("postgres down"))
    cache = KnownKeysCache(loader, fallback={"browser"}, refresh_seconds=10)
    await cache.refresh()
    assert cache.get() == {"browser"}


async def test_empty_registry_keeps_previous_keys():
    loader, _ = make_loader(set())
    cache = KnownKeysCache(loader, fallback={"browser"}, refresh_seconds=10)
    await cache.refresh()
    assert cache.get() == {"browser"}


async def test_get_returns_a_copy():
    loader, _ = make_loader({"a"})
    cache = KnownKeysCache(loader, fallback={"browser"}, refresh_seconds=10)
    cache.get().add("mutated")
    assert cache.get() == {"browser"}


async def test_newly_registered_key_stops_being_unknown():
    raw = RawEvent.model_validate({
        "event_id": "e1", "event_type": "click", "user_id": "u", "session_id": "s",
        "url": "https://x.com", "timestamp": "2026-10-11T10:00:00Z",
        "properties": {"campaign": "fall"},
    })
    loader, _ = make_loader({"browser", "campaign"})
    cache = KnownKeysCache(loader, fallback={"browser"}, refresh_seconds=10)

    before = build_clean_event(raw, cache.get(), now=FIXED_NOW)
    assert before.unknown_keys == ["campaign"]

    await cache.refresh()
    after = build_clean_event(raw, cache.get(), now=FIXED_NOW)
    assert after.unknown_keys == []