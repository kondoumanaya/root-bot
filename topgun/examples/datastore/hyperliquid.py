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
        store = topgun.HyperliquidDataStore()

        await client.ws_connect(
            "wss://api.hyperliquid.xyz/ws",
            send_json={
                "method": "subscribe",
                "subscription": {"type": "l2Book", "coin": "ETH"},
            },
            hdlr_json=store.onmessage,
        )

        while True:
            orderbook = store.l2_book.sorted(limit=2)
            print(orderbook)

            await store.l2_book.wait()


if __name__ == "__main__":
    with suppress(KeyboardInterrupt):
        asyncio.run(main())
