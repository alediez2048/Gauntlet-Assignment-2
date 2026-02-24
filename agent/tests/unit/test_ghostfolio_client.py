import httpx
import pytest
import respx

from agent.auth import clear_bearer_token_cache
from agent.clients.ghostfolio_client import GhostfolioClient, GhostfolioClientError

BASE_URL = "http://ghostfolio:3333"
ACCESS_TOKEN = "security-token"
AUTH_URL = f"{BASE_URL}/api/v1/auth/anonymous"
PERFORMANCE_URL = f"{BASE_URL}/api/v2/portfolio/performance"

PERFORMANCE_PAYLOAD = {
    "firstOrderDate": "2024-01-15T00:00:00.000Z",
    "hasErrors": False,
    "performance": {"netPerformance": 100.0},
}


@pytest.mark.asyncio
async def test_get_portfolio_performance_happy_path_uses_bearer_token() -> None:
    clear_bearer_token_cache(BASE_URL)

    async with httpx.AsyncClient() as http_client:
        client = GhostfolioClient(BASE_URL, ACCESS_TOKEN, client=http_client)
        with respx.mock(assert_all_called=True) as router:
            auth_route = router.post(AUTH_URL).mock(
                return_value=httpx.Response(200, json={"authToken": "jwt-token"})
            )
            perf_route = router.get(PERFORMANCE_URL).mock(
                return_value=httpx.Response(200, json=PERFORMANCE_PAYLOAD)
            )
            result = await client.get_portfolio_performance("ytd")

    assert result == PERFORMANCE_PAYLOAD
    assert auth_route.call_count == 1
    assert perf_route.call_count == 1
    assert perf_route.calls[0].request.headers["Authorization"] == "Bearer jwt-token"
    assert perf_route.calls[0].request.url.params["range"] == "ytd"


@pytest.mark.asyncio
async def test_client_refreshes_token_on_401_and_retries_once() -> None:
    clear_bearer_token_cache(BASE_URL)

    async with httpx.AsyncClient() as http_client:
        client = GhostfolioClient(BASE_URL, ACCESS_TOKEN, client=http_client)
        with respx.mock(assert_all_called=True) as router:
            auth_route = router.post(AUTH_URL).mock(
                side_effect=[
                    httpx.Response(200, json={"authToken": "jwt-token-1"}),
                    httpx.Response(200, json={"authToken": "jwt-token-2"}),
                ]
            )
            perf_route = router.get(PERFORMANCE_URL).mock(
                side_effect=[
                    httpx.Response(401, json={"message": "Unauthorized"}),
                    httpx.Response(200, json=PERFORMANCE_PAYLOAD),
                ]
            )
            result = await client.get_portfolio_performance("ytd")

    assert result == PERFORMANCE_PAYLOAD
    assert auth_route.call_count == 2
    assert perf_route.call_count == 2
    assert perf_route.calls[0].request.headers["Authorization"] == "Bearer jwt-token-1"
    assert perf_route.calls[1].request.headers["Authorization"] == "Bearer jwt-token-2"


@pytest.mark.asyncio
async def test_client_raises_auth_failed_after_second_401() -> None:
    clear_bearer_token_cache(BASE_URL)

    async with httpx.AsyncClient() as http_client:
        client = GhostfolioClient(BASE_URL, ACCESS_TOKEN, client=http_client)
        with respx.mock(assert_all_called=True) as router:
            router.post(AUTH_URL).mock(
                side_effect=[
                    httpx.Response(200, json={"authToken": "jwt-token-1"}),
                    httpx.Response(200, json={"authToken": "jwt-token-2"}),
                ]
            )
            router.get(PERFORMANCE_URL).mock(
                side_effect=[
                    httpx.Response(401, json={"message": "Unauthorized"}),
                    httpx.Response(401, json={"message": "Unauthorized"}),
                ]
            )
            with pytest.raises(GhostfolioClientError) as raised_error:
                await client.get_portfolio_performance("ytd")

    assert raised_error.value.error_code == "AUTH_FAILED"


@pytest.mark.asyncio
async def test_client_translates_timeout_to_api_timeout() -> None:
    clear_bearer_token_cache(BASE_URL)

    async with httpx.AsyncClient() as http_client:
        client = GhostfolioClient(BASE_URL, ACCESS_TOKEN, client=http_client)
        with respx.mock(assert_all_called=True) as router:
            router.post(AUTH_URL).mock(return_value=httpx.Response(200, json={"authToken": "jwt-token"}))
            router.get(PERFORMANCE_URL).mock(side_effect=httpx.TimeoutException("Timed out"))

            with pytest.raises(GhostfolioClientError) as raised_error:
                await client.get_portfolio_performance("ytd")

    assert raised_error.value.error_code == "API_TIMEOUT"


@pytest.mark.asyncio
async def test_client_translates_http_status_errors_to_api_error() -> None:
    clear_bearer_token_cache(BASE_URL)

    async with httpx.AsyncClient() as http_client:
        client = GhostfolioClient(BASE_URL, ACCESS_TOKEN, client=http_client)
        with respx.mock(assert_all_called=True) as router:
            router.post(AUTH_URL).mock(return_value=httpx.Response(200, json={"authToken": "jwt-token"}))
            router.get(PERFORMANCE_URL).mock(
                return_value=httpx.Response(500, json={"message": "Internal Server Error"})
            )

            with pytest.raises(GhostfolioClientError) as raised_error:
                await client.get_portfolio_performance("ytd")

    assert raised_error.value.error_code == "API_ERROR"
    assert raised_error.value.status == 500


@pytest.mark.asyncio
async def test_client_validates_date_range_before_request() -> None:
    clear_bearer_token_cache(BASE_URL)

    async with httpx.AsyncClient() as http_client:
        client = GhostfolioClient(BASE_URL, ACCESS_TOKEN, client=http_client)

        with pytest.raises(GhostfolioClientError) as raised_error:
            await client.get_portfolio_performance("INVALID")

    assert raised_error.value.error_code == "INVALID_TIME_PERIOD"
