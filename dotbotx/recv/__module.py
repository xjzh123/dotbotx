from typing import List
import asyncio

from ..core import Context
from ..xcore import XChatter

queues: List[asyncio.Queue[Context]] = []


async def recv_ctx():
    queue: asyncio.Queue[Context] = asyncio.Queue()

    queues.append(queue)

    ctx = await queue.get()
    queues.remove(queue)

    return ctx


async def recv_msg():
    return (await recv_ctx()).message


async def recv_unwrap():
    ctx = await recv_ctx()
    return ctx.chatter, ctx.message


async def receiver(ctx: Context):
    for queue in queues:
        await queue.put(ctx)


def apply_recv(chatter: XChatter):
    chatter.register_callback(receiver)
