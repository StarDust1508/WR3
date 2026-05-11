import pytest

from audit_engine.pipeline import AuditPipeline, PipelineEvent


@pytest.mark.asyncio
async def test_pipeline_emits_error_without_source() -> None:
    pipe = AuditPipeline(network="base")
    events: list[PipelineEvent] = []
    async for ev in pipe.run(address="0xnope"):
        events.append(ev)

    assert events[0].stage == "queued"
    assert events[-1].stage == "error"


@pytest.mark.asyncio
async def test_pipeline_runs_with_inline_source() -> None:
    src = "pragma solidity ^0.8.0;\ncontract Empty {}\n"
    pipe = AuditPipeline(network="base", triage_enabled=False)
    stages = [ev.stage async for ev in pipe.run(address="0xabc", source=src)]

    # We expect at least: queued -> static -> triage -> ... -> done
    assert "queued" in stages
    assert stages[-1] == "done"


@pytest.mark.asyncio
async def test_pipeline_baseline_finds_tx_origin_when_triage_disabled() -> None:
    """End-to-end: baseline analyzer must produce findings even without LLM."""
    src = """
    pragma solidity ^0.8.0;
    contract A {
        address owner;
        function withdraw() external {
            require(tx.origin == owner, "no");
        }
    }
    """
    pipe = AuditPipeline(network="base", triage_enabled=False)
    events = []
    async for ev in pipe.run(address="0xfeed", source=src):
        events.append(ev)
    assert events[-1].stage == "done"
    result = pipe.result()
    titles = [f["title"] for f in result["findings"]]
    assert any("tx.origin" in t for t in titles)
