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
        store = topgun.BitMEXDataStore()

        await client.ws_connect(
            "wss://ws.bitmex.com/realtime",
            send_json={
                "op": "subscribe",
                "args": ["orderBookL2_25:XBTUSD"],
            },
            hdlr_json=store.onmessage,
        )

        while True:
            orderbook = store.orderbook.sorted(limit=2)
            print(orderbook)

            await store.orderbook.wait()


if __name__ == "__main__":
    with suppress(KeyboardInterrupt):
        asyncio.run(main())
