import json

import httpx
import pytest
import respx

from agent.auth import clear_bearer_token_cache, get_bearer_token


@pytest.mark.asyncio
async def test_get_bearer_token_posts_expected_payload() -> None:
    base_url = "http://ghostfolio:3333"
    clear_bearer_token_cache(base_url)

    with respx.mock(assert_all_called=True) as router:
        route = router.post(f"{base_url}/api/v1/auth/anonymous").mock(
            return_value=httpx.Response(200, json={"authToken": "jwt-token"})
        )
        token = await get_bearer_token(base_url=base_url, access_token="security-token")

    assert token == "jwt-token"
    assert route.call_count == 1
    request_payload = json.loads(route.calls[0].request.content.decode("utf-8"))
    assert request_payload == {"accessToken": "security-token"}


@pytest.mark.asyncio
async def test_get_bearer_token_uses_cache_until_cleared() -> None:
    base_url = "http://ghostfolio:3333"
    clear_bearer_token_cache(base_url)

    with respx.mock(assert_all_called=True) as router:
        route = router.post(f"{base_url}/api/v1/auth/anonymous").mock(
            side_effect=[
                httpx.Response(200, json={"authToken": "jwt-token-1"}),
                httpx.Response(200, json={"authToken": "jwt-token-2"}),
            ]
        )
        first = await get_bearer_token(base_url=base_url, access_token="security-token")
        second = await get_bearer_token(base_url=base_url, access_token="security-token")
        clear_bearer_token_cache(base_url)
        third = await get_bearer_token(base_url=base_url, access_token="security-token")

    assert first == "jwt-token-1"
    assert second == "jwt-token-1"
    assert third == "jwt-token-2"
    assert route.call_count == 2


@pytest.mark.asyncio
async def test_get_bearer_token_requires_env_or_explicit_access_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_url = "http://ghostfolio:3333"
    clear_bearer_token_cache(base_url)
    monkeypatch.delenv("GHOSTFOLIO_ACCESS_TOKEN", raising=False)

    with pytest.raises(ValueError, match="GHOSTFOLIO_ACCESS_TOKEN is required"):
        await get_bearer_token(base_url=base_url)
