import json

import httpx
import pytest
from conftest import requirement

from data_access.gateway import DataGateway
from domain.common import AppError
from domain.requirements import Message
from requirements.nim import NimGateway


@pytest.mark.parametrize("status,code", [(401, "LLM_AUTH_FAILED"), (403, "LLM_AUTH_FAILED"), (429, "LLM_RATE_LIMITED"), (500, "LLM_UPSTREAM_ERROR"), (202, "LLM_PENDING")])
async def test_nim_errors_are_sanitized(settings, status, code):
    transport = httpx.MockTransport(lambda r: httpx.Response(status, text="SECRET UPSTREAM BODY"))
    with pytest.raises(AppError) as error:
        await NimGateway(settings, transport).extract(Message(id="m", text="Đi Nhật", received_at="2026-10-01T00:00:00Z"))
    assert error.value.code == code and "SECRET" not in error.value.message


async def test_nim_truncation_rejected(settings):
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={"choices": [{"finish_reason": "length", "message": {"content": "{}"}}]}))
    with pytest.raises(AppError, match="schema"):
        await NimGateway(settings, transport).extract(Message(id="m", text="Đi Nhật", received_at="2026-10-01T00:00:00Z"))


async def test_nim_request_uses_configured_model_and_no_tools(settings):
    def handle(request):
        body = json.loads(request.content)
        assert body["model"] == "nvidia/nemotron-3-super-120b-a12b"
        assert "tools" not in body and body["stream"] is False
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}]})
    result, metrics = await NimGateway(settings, httpx.MockTransport(handle)).extract(
        Message(id="m", text="Không cần hotel", received_at="2026-10-01T00:00:00Z"))
    assert result.conditions == [] and metrics["model"] == settings.nvidia_nim_model


async def test_unapproved_url_never_reaches_upstream(settings):
    from domain.requirements import Requirement, Target
    r = Requirement(id="r", revision=1, mode="compare_urls", targets=[Target(target_id="a", url="http://127.0.0.1/secret"),
        Target(target_id="b", url="http://169.254.169.254/latest/meta-data")])
    gateway = DataGateway(settings, transport=httpx.MockTransport(lambda r: pytest.fail("must not call upstream")))
    result = await gateway.collect(r, "2026-10-01T04:00:00Z")
    assert len(result.source_results) == 2
    assert all(s.reason_code == "SOURCE_NOT_APPROVED" for s in result.source_results)


async def test_crawler_bad_request_id_rejected(settings):
    from data_access.fixtures import fixture_registry
    settings.data_provider = "http"
    settings.crawler_url = "https://crawler.test/crawl"
    def handler(request):
        return httpx.Response(200, json={"schema_version": "1.0", "request_id": "wrong", "origin": "source", "source_results": []})
    gateway = DataGateway(settings, registry=fixture_registry(), transport=httpx.MockTransport(handler))
    with pytest.raises(AppError) as e:
        await gateway.collect(requirement(), "2026-10-01T04:00:00Z")
    assert e.value.code == "CRAWLER_INVALID_OUTPUT"
