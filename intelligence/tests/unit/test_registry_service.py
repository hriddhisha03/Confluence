from app.services.registry_service import RegisterResult, infer_and_register


class FakeRepo:
    def __init__(self, registry=None, version=1, race_existing=None):
        self.registry = dict(registry or {})
        self.version = version
        self.race_existing = race_existing or {}
        self.register_calls = []

    async def get_registry(self):
        return dict(self.registry)

    async def current_version(self):
        return self.version

    async def register_fields(self, fields, description):
        self.register_calls.append((dict(fields), description))
        existing = {n: t for n, t in self.race_existing.items() if n in fields}
        inserted = {n: t for n, t in fields.items() if n not in existing}
        self.version += 1
        self.registry.update(inserted)
        return RegisterResult(version=self.version, inserted=inserted, existing=existing)


async def run(samples, repo, max_new=50, max_total=200):
    return await infer_and_register(samples, repo, max_new_fields=max_new, max_total_fields=max_total)


async def test_new_field_is_registered_with_inferred_type():
    repo = FakeRepo({"browser": "string"})
    resp = await run({"age": [30, 41]}, repo)
    assert [(f.name, f.type) for f in resp.registered] == [("age", "int")]
    assert resp.schema_version == 2
    assert repo.register_calls[0][0] == {"age": "int"}


async def test_existing_field_keeps_registered_type_and_is_not_rewritten():
    repo = FakeRepo({"plan": "string"})
    resp = await run({"plan": [42]}, repo)  # sample looks like int, registry says string
    assert [(f.name, f.type) for f in resp.existing] == [("plan", "string")]
    assert resp.registered == []
    assert repo.register_calls == []
    assert resp.schema_version == 1


async def test_mixed_new_and_existing():
    repo = FakeRepo({"plan": "string"})
    resp = await run({"plan": ["pro"], "score": [1.5]}, repo)
    assert [f.name for f in resp.registered] == ["score"]
    assert [f.name for f in resp.existing] == ["plan"]


async def test_invalid_and_reserved_names_are_rejected_not_registered():
    repo = FakeRepo()
    resp = await run({"Bad Name": ["x"], "event_id": ["x"], "good": ["x"]}, repo)
    reasons = {r.name: r.reason for r in resp.rejected}
    assert reasons == {"Bad Name": "invalid_name", "event_id": "reserved_name"}
    assert [f.name for f in resp.registered] == ["good"]
    assert list(repo.register_calls[0][0]) == ["good"]


async def test_nothing_new_makes_no_write():
    repo = FakeRepo({"a": "string"}, version=3)
    resp = await run({"a": ["x"]}, repo)
    assert repo.register_calls == []
    assert resp.schema_version == 3


async def test_per_request_limit_rejects_the_overflow():
    repo = FakeRepo()
    samples = {f"k{i}": ["v"] for i in range(5)}
    resp = await run(samples, repo, max_new=2)
    assert len(resp.registered) == 2
    assert [r.reason for r in resp.rejected] == ["field_limit_reached"] * 3


async def test_total_limit_rejects_when_registry_is_full():
    repo = FakeRepo({f"f{i}": "string" for i in range(5)})
    resp = await run({"new1": ["v"], "new2": ["v"]}, repo, max_total=5)
    assert resp.registered == []
    assert {r.name for r in resp.rejected} == {"new1", "new2"}
    assert repo.register_calls == []


async def test_total_limit_allows_only_remaining_capacity():
    repo = FakeRepo({f"f{i}": "string" for i in range(4)})
    resp = await run({"new1": ["v"], "new2": ["v"]}, repo, max_total=5)
    assert len(resp.registered) == 1
    assert len(resp.rejected) == 1


async def test_race_loser_reports_the_winner_type_as_existing():
    repo = FakeRepo(race_existing={"plan": "string"})
    resp = await run({"plan": [5], "extra": [1]}, repo)
    assert [(f.name, f.type) for f in resp.existing] == [("plan", "string")]
    assert [f.name for f in resp.registered] == ["extra"]