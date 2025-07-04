# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "topgun",
#     "rich",
# ]
# ///

import asyncio
from contextlib import suppress

import topgun

with suppress(ImportError):
    from rich import print


async def main():
    async with topgun.Client() as client:
        store = topgun.OKXDataStore()

        await client.ws_connect(
            "wss://ws.okx.com:8443/ws/v5/public",
            send_json={
                "op": "subscribe",
                "args": [{"channel": "books", "instId": "BTC-USDT"}],
            },
            hdlr_json=store.onmessage,
        )

        while True:
            orderbook = store.books.sorted(limit=2)
            print(orderbook)

            await store.books.wait()


if __name__ == "__main__":
    with suppress(KeyboardInterrupt):
        asyncio.run(main())
