import json
from datetime import datetime, timezone

from app.models.schemas import CleanEvent, FieldResult, InferResult, RejectedField
from app.services.known_keys import KnownKeysCache
from app.services.schema_resolver import SchemaResolver


def make_event(unknown, props=None):
    return CleanEvent(
        event_id="e1", event_type="click", user_id="u", session_id="s",
        url="https://x.test", timestamp=datetime.now(timezone.utc),
        properties=props if props is not None else {k: "v" for k in unknown},
        unknown_keys=unknown, processed_at=datetime.now(timezone.utc),
    )


class Harness:
    def __init__(self, result, max_rejected=100, infer_raises=None):
        self.result = result
        self.infer_raises = infer_raises
        self.infer_calls = []
        self.published = []
        self.cache = KnownKeysCache(loader=lambda: None, fallback={"browser"}, refresh_seconds=10)
        self.resolver = SchemaResolver(self._infer, self._publish, self.cache, "schema_updates", max_rejected)

    async def _infer(self, samples):
        self.infer_calls.append(samples)
        if self.infer_raises:
            raise self.infer_raises
        return self.result

    async def _publish(self, topic, key, value):
        self.published.append((topic, key, json.loads(value)))


def registered(name="campaign", type_="string", version=2):
    return InferResult(schema_version=version, registered=[FieldResult(name=name, type=type_)])


async def test_registered_field_published_and_cached():
    h = Harness(registered())
    await h.resolver.resolve(make_event(["campaign"]))
    assert h.infer_calls == [{"campaign": ["v"]}]
    assert "campaign" in h.cache.get()
    topic, key, body = h.published[0]
    assert topic == "schema_updates" and key is None
    assert body["schema_version"] == 2
    assert body["fields"] == [{"name": "campaign", "type": "string"}]


async def test_existing_field_cached_but_not_published():
    h = Harness(InferResult(schema_version=2, existing=[FieldResult(name="campaign", type="string")]))
    await h.resolver.resolve(make_event(["campaign"]))
    assert "campaign" in h.cache.get()
    assert h.published == []


async def test_infer_unavailable_does_nothing():
    h = Harness(None)
    await h.resolver.resolve(make_event(["campaign"]))
    assert h.published == []
    assert "campaign" not in h.cache.get()


async def test_infer_exception_is_swallowed():
    h = Harness(None, infer_raises=RuntimeError("boom"))
    await h.resolver.resolve(make_event(["campaign"]))
    assert h.published == []


async def test_publish_exception_is_swallowed():
    h = Harness(registered())

    async def bad_publish(*a):
        raise RuntimeError("kafka down")

    h.resolver._publish = bad_publish
    await h.resolver.resolve(make_event(["campaign"]))


async def test_rejected_keys_not_asked_again():
    h = Harness(InferResult(schema_version=1, rejected=[RejectedField(name="Bad-Name", reason="invalid")]))
    await h.resolver.resolve(make_event(["Bad-Name"]))
    await h.resolver.resolve(make_event(["Bad-Name"]))
    assert len(h.infer_calls) == 1


async def test_only_non_rejected_keys_are_sent():
    h = Harness(InferResult(schema_version=1, rejected=[RejectedField(name="Bad", reason="x")]))
    await h.resolver.resolve(make_event(["Bad"]))
    h.result = registered("good")
    await h.resolver.resolve(make_event(["Bad", "good"]))
    assert list(h.infer_calls[1]) == ["good"]


async def test_rejected_memory_is_bounded():
    h = Harness(None, max_rejected=2)
    for n in ["a", "b", "c"]:
        h.resolver._remember_rejected(n)
    assert list(h.resolver._rejected) == ["b", "c"]