"""Local OpenCode conversation eval. Skips when the configured service is absent."""

import pytest

from backend.agent.service import AgentService
from backend.data.sessions import SessionStore
from backend.settings import Settings


@pytest.mark.asyncio
async def test_local_agent_builds_a_reviewable_brief_without_querying_tours(tmp_path):
    settings = Settings.load().model_copy(
        update={"database_url": f"sqlite:///{tmp_path / 'agent-eval.db'}"}
    )
    if not settings.opencode_server_url.strip():
        pytest.skip("needs a configured local OpenCode service")
    service = AgentService(settings, SessionStore(settings.database_url))
    if not service.available:
        pytest.skip("needs the local OpenCode CLI and service")

    owner = service.store.create_session(3600)["id"]
    agent_session_id = service.create_session(owner)["agent_session_id"]
    result = await service.message(
        owner,
        agent_session_id,
        "Tìm tour Phú Quốc 4 ngày, khởi hành từ Sài Gòn. Ngân sách tối đa 15 triệu VND/người; "
        "tôi thích có công viên giải trí.",
    )
    assert result["assistant_text"]
    assert result["decision_draft"]["conditions"]
    assert any(call["name"] == "draft_requirement" for call in result["tool_calls"])
    assert not any(call["name"] == "query_tours" for call in result["tool_calls"])
    service.store.close()
