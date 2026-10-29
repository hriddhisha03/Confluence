import httpx
import pytest

from app.clients.intelligence_client import IntelligenceClient

OK_BODY = {
    "schema_version": 3,
    "registered": [{"name": "campaign", "type": "string"}],
    "existing": [],
    "rejected": [],
}


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def make_client(handler, clock=None):
    clock = clock or Clock()
    http = httpx.AsyncClient(base_url="http://intel", transport=httpx.MockTransport(handler))
    return IntelligenceClient("http://intel", 2.0, 10.0, clock=clock, client=http), clock


async def test_success_returns_parsed_result():
    seen = {}

    def handler(request):
        seen["path"] = request.url.path
        seen["body"] = request.read()
        return httpx.Response(200, json=OK_BODY)

    client, _ = make_client(handler)
    result = await client.infer({"campaign": ["fall"]})
    assert seen["path"] == "/v1/infer"
    assert b'"samples"' in seen["body"]
    assert result.schema_version == 3
    assert result.registered[0].name == "campaign"


async def test_server_error_returns_none_and_starts_cooldown():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(500)

    client, clock = make_client(handler)
    assert await client.infer({"a": [1]}) is None
    assert await client.infer({"a": [1]}) is None  # blocked, no HTTP call
    assert len(calls) == 1
    clock.now += 11
    await client.infer({"a": [1]})
    assert len(calls) == 2


async def test_connection_error_returns_none():
    def handler(request):
        raise httpx.ConnectError("down")

    client, _ = make_client(handler)
    assert await client.infer({"a": [1]}) is None


async def test_invalid_json_body_returns_none():
    client, _ = make_client(lambda r: httpx.Response(200, content=b"not json"))
    assert await client.infer({"a": [1]}) is None


async def test_unexpected_shape_returns_none():
    client, _ = make_client(lambda r: httpx.Response(200, json={"foo": 1}))
    assert await client.infer({"a": [1]}) is None


async def test_infer_before_start_raises():
    client = IntelligenceClient("http://intel", 2.0, 10.0)
    with pytest.raises(RuntimeError):
        await client.infer({"a": [1]})