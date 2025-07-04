from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.test_utils import TestServer
from yarl import URL

import topgun
from topgun.helpers.bitbank import subscribe, subscribe_with_callback
from topgun.helpers.gmocoin import GMOCoinHelper
from topgun.request import ClientRequest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from typing import Awaitable, Callable, Type

    import aiohttp
    from aiohttp.typedefs import StrOrURL


@pytest_asyncio.fixture
async def topgun_client(
    aiohttp_client_cls: Type[aiohttp.ClientSession],
    monkeypatch: pytest.MonkeyPatch,
):
    # From https://github.com/aio-libs/pytest-aiohttp/blob/v1.0.4/pytest_aiohttp/plugin.py#L139

    clients = []

    async def go(app, **kwargs):
        server = TestServer(app)
        aiohttp_client = aiohttp_client_cls(server)
        aiohttp_client._session._request_class = ClientRequest

        await aiohttp_client.start_server()
        clients.append(aiohttp_client)

        def dummy_request(method: str, str_or_url: StrOrURL, **kwargs):
            return aiohttp_client._request(method, URL(str_or_url).path_qs, **kwargs)

        _topgun_client = topgun.Client(**kwargs)
        monkeypatch.setattr(
            _topgun_client._session,
            _topgun_client._session._request.__name__,
            dummy_request,
        )
        return _topgun_client

    yield go

    while clients:
        await clients.pop().close()


async def create_access_token(request: web.Request):
    return web.json_response(
        {
            "status": 0,
            "data": "xxxxxxxxxxxxxxxxxxxx",
            "responsetime": "2019-03-19T02:15:06.102Z",
        }
    )


async def extend_access_token(request: web.Request):
    return web.json_response(
        {
            "status": 0,
            "responsetime": "2019-03-19T02:15:06.102Z",
        }
    )


async def create_access_token_error(request: web.Request):
    return web.json_response(
        {
            "status": 5,
            "messages": [
                {
                    "message_code": "ERR-5201",
                    "message_string": "MAINTENANCE. Please wait for a while",
                }
            ],
        }
    )


async def extend_access_token_error(request: web.Request):
    return web.json_response(
        {
            "status": 1,
            "messages": [
                {
                    "message_code": "ERR-5106",
                    "message_string": "Invalid request parameter.",
                }
            ],
            "responsetime": "2024-05-11T02:02:40.501Z",
        }
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "base_url, extend_access_handler, create_access_handler, expected_token",
    [
        (
            "",
            extend_access_token,
            create_access_token,
            "aaaaaaaaaa",
        ),
        (
            "https://api.coin.z.com",
            extend_access_token,
            create_access_token,
            "aaaaaaaaaa",
        ),
        (
            "https://api.coin.z.com",
            extend_access_token_error,
            create_access_token,
            "xxxxxxxxxxxxxxxxxxxx",
        ),
        (
            "https://api.coin.z.com",
            extend_access_token_error,
            create_access_token_error,
            "aaaaaaaaaa",
        ),
    ],
)
async def test_gmo_manage_ws_token(
    extend_access_handler: Callable[..., Awaitable[web.Response]],
    create_access_handler: Callable[..., Awaitable[web.Response]],
    topgun_client: Callable[..., Awaitable[topgun.Client]],
    base_url: str,
    expected_token: str,
    monkeypatch: pytest.MonkeyPatch,
):
    async def sleep_canceller(delay):
        raise asyncio.CancelledError()

    app = web.Application()
    app.router.add_put("/private/v1/ws-auth", extend_access_handler)
    app.router.add_post("/private/v1/ws-auth", create_access_handler)
    client = await topgun_client(app, base_url=base_url)

    token = "aaaaaaaaaa"
    url = f"wss://api.coin.z.com/ws/private/v1/{token}"
    m_ws = AsyncMock()
    m_ws.url = url

    helper = GMOCoinHelper(client)
    with monkeypatch.context() as m, suppress(asyncio.CancelledError):
        m.setattr(asyncio, asyncio.sleep.__name__, sleep_canceller)
        await helper.manage_ws_token(
            m_ws,
            token,
            300.0,
        )

    assert m_ws.url == f"wss://api.coin.z.com/ws/private/v1/{expected_token}"


@pytest_asyncio.fixture
async def server_bitbank() -> AsyncGenerator[str]:
    routes = web.RouteTableDef()

    @routes.get("/v1/user/subscribe")
    async def channel_and_token(request: web.Request) -> web.Response:
        return web.json_response(
            {
                "success": 1,
                "data": {
                    "pubnub_channel": "1234567890",
                    "pubnub_token": "xxxxxxxxxx",
                },
            }
        )

    app = web.Application()
    app.add_routes(routes)

    async with TestServer(app) as server:
        yield str(server.make_url(URL()))


@pytest_asyncio.fixture
async def server_bitbank_error() -> AsyncGenerator[str]:
    routes = web.RouteTableDef()

    @routes.get("/v1/user/subscribe")
    async def channel_and_token(request: web.Request) -> web.Response:
        return web.json_response({"success": 0, "data": {"code": 20003}})

    app = web.Application()
    app.add_routes(routes)

    async with TestServer(app) as server:
        yield str(server.make_url(URL()))


@pytest_asyncio.fixture
async def server_pubnub() -> AsyncGenerator[str]:
    routes = web.RouteTableDef()

    @routes.get("/v2/subscribe/sub-c-ecebae8e-dd60-11e6-b6b1-02ee2ddab7fe/1234567890/0")
    async def subscribe(request: web.Request) -> web.Response:
        if request.query.get("tt") is None:
            return web.json_response({"t": {"t": "1231312313123", "r": 33}, "m": []})
        else:
            return web.json_response(
                {
                    "t": {"t": "1231312313123", "r": 33},
                    "m": [
                        {
                            "a": "3",
                            "f": 0,
                            "i": "bitbank-prod",
                            "p": {"t": "1231312313123", "r": 33},
                            "k": "sub-c-ecebae8e-dd60-11e6-b6b1-02ee2ddab7fe",
                            "c": "1234567890",
                            "d": {
                                "method": "spot_order_new",
                                "params": [
                                    {
                                        "average_price": "0.000",
                                        "executed_amount": "0.0000",
                                        "order_id": 44280998810,
                                        "ordered_at": 1742546617276,
                                        "pair": "xrp_jpy",
                                        "price": "359.412",
                                        "remaining_amount": "0.0002",
                                        "side": "buy",
                                        "start_amount": "0.0002",
                                        "status": "UNFILLED",
                                        "type": "limit",
                                        "expire_at": 1758098617276,
                                        "post_only": True,
                                        "user_cancelable": True,
                                    }
                                ],
                            },
                        }
                    ],
                }
            )

    app = web.Application()
    app.add_routes(routes)

    async with TestServer(app) as server:
        yield str(server.make_url(URL()))


@pytest_asyncio.fixture
async def server_pubnub_error() -> AsyncGenerator[str]:
    routes = web.RouteTableDef()

    @routes.get("/v2/subscribe/sub-c-ecebae8e-dd60-11e6-b6b1-02ee2ddab7fe/1234567890/0")
    async def subscribe(request: web.Request) -> web.Response:
        return web.json_response(
            {"error": True, "status": 403, "service": "Access Manager"},
            status=403,
        )

    app = web.Application()
    app.add_routes(routes)

    async with TestServer(app) as server:
        yield str(server.make_url(URL()))


@pytest_asyncio.fixture
async def server_pubnub_expired() -> AsyncGenerator[str]:
    routes = web.RouteTableDef()

    @routes.get("/v2/subscribe/sub-c-ecebae8e-dd60-11e6-b6b1-02ee2ddab7fe/1234567890/0")
    async def subscribe(request: web.Request) -> web.Response:
        if request.query.get("auth") == "expired":
            return web.json_response(
                {
                    "error": True,
                    "status": 403,
                    "service": "Access Manager",
                    "message": "Token is expired.",
                },
                status=403,
            )
        else:
            return web.json_response({"t": {"t": "1231312313123", "r": 33}, "m": []})

    app = web.Application()
    app.add_routes(routes)

    async with TestServer(app) as server:
        yield str(server.make_url(URL()))


@pytest.mark.asyncio
async def test_bitbank_subscribe_with_callback(
    server_bitbank: str, server_pubnub: str
) -> None:
    queue = asyncio.Queue[object]()

    async with topgun.Client() as client:
        task = asyncio.create_task(
            subscribe_with_callback(
                client,
                lambda x: queue.put_nowait(x),
                bitbank_server=server_bitbank,
                pubnub_server=server_pubnub,
            )
        )

        item = await asyncio.wait_for(queue.get(), timeout=5.0)

        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    assert item == {
        "method": "spot_order_new",
        "params": [
            {
                "average_price": "0.000",
                "executed_amount": "0.0000",
                "order_id": 44280998810,
                "ordered_at": 1742546617276,
                "pair": "xrp_jpy",
                "price": "359.412",
                "remaining_amount": "0.0002",
                "side": "buy",
                "start_amount": "0.0002",
                "status": "UNFILLED",
                "type": "limit",
                "expire_at": 1758098617276,
                "post_only": True,
                "user_cancelable": True,
            }
        ],
    }


@pytest.mark.asyncio
async def test_bitbank_subscribe_bitbank_error(
    server_bitbank_error: str, server_pubnub: str
) -> None:
    async with topgun.Client() as client:
        with pytest.raises(ValueError):
            await (
                subscribe(
                    client,
                    bitbank_server=server_bitbank_error,
                    pubnub_server=server_pubnub,
                )
                .__aiter__()
                .__anext__()
            )


@pytest.mark.asyncio
async def test_bitbank_subscribe_pubnub_error(
    server_bitbank: str, server_pubnub_error: str
) -> None:
    async with topgun.Client() as client:
        with pytest.raises(ValueError):
            await (
                subscribe(
                    client,
                    bitbank_server=server_bitbank,
                    pubnub_server=server_pubnub_error,
                )
                .__aiter__()
                .__anext__()
            )


@pytest.mark.asyncio
async def test_bitbank_subscribe_pubnub_expired(
    server_bitbank: str, server_pubnub_expired: str
) -> None:
    async with topgun.Client() as client:
        message = (
            await subscribe(
                client,
                channel="1234567890",
                token="expired",
                bitbank_server=server_bitbank,
                pubnub_server=server_pubnub_expired,
            )
            .__aiter__()
            .__anext__()
        )

    assert message == {"t": {"t": "1231312313123", "r": 33}, "m": []}
