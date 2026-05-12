"""LLMRouter.embed_batch — protocol tests against api.navy's contract.

We don't hit api.navy in tests. respx mocks the /embeddings endpoint and
we assert that the router:
  - sends a single POST with `input` as a list
  - passes the model name through
  - returns embeddings in the original order even when the provider
    returns them out-of-order (provider's `index` field is the source of
    truth)
  - bare embed() is just embed_batch([t])[0]
"""

from __future__ import annotations

import httpx
import respx

from audit_engine.llm.router import LLMRouter


BASE_URL = "https://api.navy/v1"


def _router() -> LLMRouter:
    return LLMRouter(
        navyai_key="test_key",
        navyai_base_url=BASE_URL,
    )


def _resp(embeddings: list[list[float]], indices: list[int] | None = None) -> dict:
    """Build an OpenAI-shape embeddings response."""
    ix = indices or list(range(len(embeddings)))
    return {
        "object": "list",
        "data": [
            {"object": "embedding", "index": i, "embedding": e}
            for i, e in zip(ix, embeddings)
        ],
        "model": "text-embedding-3-small",
        "usage": {"prompt_tokens": 3, "total_tokens": 3},
    }


async def test_embed_batch_sends_list_input() -> None:
    captured: dict = {}
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post("/embeddings").mock(
            return_value=httpx.Response(200, json=_resp([[0.1, 0.2], [0.3, 0.4]]))
        )
        result = await _router().embed_batch(["a", "b"])

    assert route.called
    request = route.calls[0].request
    import json as j
    body = j.loads(request.content.decode())
    assert body["input"] == ["a", "b"]
    assert body["model"] == "text-embedding-3-small"
    assert request.headers["Authorization"] == "Bearer test_key"
    assert result == [[0.1, 0.2], [0.3, 0.4]]


async def test_embed_batch_sorts_by_index() -> None:
    """If the provider returns out-of-order, we MUST re-sort by `index`."""
    with respx.mock(base_url=BASE_URL) as mock:
        mock.post("/embeddings").mock(
            return_value=httpx.Response(
                200,
                # Same embeddings, but reversed in transit
                json=_resp([[0.3, 0.4], [0.1, 0.2]], indices=[1, 0]),
            )
        )
        result = await _router().embed_batch(["a", "b"])

    assert result == [[0.1, 0.2], [0.3, 0.4]]


async def test_embed_batch_empty_input_is_no_op() -> None:
    """No texts → no network call → empty list. Saves a wasted round-trip
    for scans with no high/critical findings.

    We use `assert_all_called=False` to allow the embeddings route to be
    declared-but-unused; the assertion that matters is "no HTTP call was
    made at all", which respx enforces by raising on any unmatched
    outbound request.
    """
    with respx.mock(base_url=BASE_URL, assert_all_called=False) as mock:
        route = mock.post("/embeddings").mock(
            return_value=httpx.Response(200, json=_resp([]))
        )
        result = await _router().embed_batch([])
    assert result == []
    assert not route.called


async def test_embed_uses_embed_batch_under_the_hood() -> None:
    """The single-string `embed()` must be a thin wrapper. If it ever drifts
    into a separate code path, threshold calibration done on one won't
    apply to the other — and that's a subtle data-quality bug."""
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post("/embeddings").mock(
            return_value=httpx.Response(200, json=_resp([[0.5, 0.6]]))
        )
        emb = await _router().embed("hello")

    assert emb == [0.5, 0.6]
    assert route.called
    import json as j
    body = j.loads(route.calls[0].request.content.decode())
    # API received list-form input even though caller passed a single string
    assert body["input"] == ["hello"]
