from audit_engine.knowledge.solodit import SoloditClient, SoloditEntry


def test_parse_results_envelope() -> None:
    c = SoloditClient()
    out = c._parse(
        {
            "results": [
                {
                    "title": "Reentrancy in withdraw",
                    "severity": "high",
                    "body": "External call before state update",
                    "audit_firm": "Trail of Bits",
                    "url": "https://example/r/1",
                },
                {
                    "title": "Integer underflow",
                    "risk": "Medium",
                    "description": "Old solc",
                    "protocol": "FooDAO",
                },
            ]
        },
        limit=5,
    )
    assert len(out) == 2
    assert out[0].severity == "high"
    assert out[0].source_firm == "Trail of Bits"
    assert out[1].project == "FooDAO"


def test_parse_bare_list() -> None:
    c = SoloditClient()
    out = c._parse(
        [{"title": "x", "severity": "low", "body": ""}],
        limit=10,
    )
    assert out == [SoloditEntry(title="x", severity="low", body="", source_firm=None, project=None, url=None)]


def test_parse_empty() -> None:
    c = SoloditClient()
    assert c._parse({}, limit=5) == []
    assert c._parse({"results": []}, limit=5) == []
    assert c._parse("garbage", limit=5) == []  # type: ignore[arg-type]
