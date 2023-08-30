import asyncio
from collections import defaultdict
import threading
from typing import Awaitable, DefaultDict, List, Optional, Union

from ..core import Chatter, Context, MessageCallback
from ..module import Module


class XChatter(Chatter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.callbacks: List[MessageCallback] = []
        self.typed_callbacks: DefaultDict[str, List[MessageCallback]] = defaultdict(
            list
        )

        def message_callback(ctx: Context):
            for callback in self.callbacks:
                self.__call(callback, ctx)

            for callback in self.typed_callbacks[ctx.message.type]:
                self.__call(callback, ctx)

        self.message_callback = message_callback

    def __call(self, func: MessageCallback, ctx: Context):
        ret = func(ctx)
        if isinstance(ret, Awaitable):
            asyncio.run_coroutine_threadsafe(ret, self.loop)

    def start(self):
        self.loop = asyncio.get_event_loop()
        threading.Thread(
            target=lambda: self.connector.run_forever(
                self.channel, self.nick, self.password
            ),
            daemon=True,
        ).start()

    def wait(self):
        self.loop.run_forever()

    def run(self):
        self.start()
        self.wait()

    def set_message_callback(self, callback: MessageCallback):
        self.register_callback(callback)

    def register_callback(
        self,
        callback: MessageCallback,
        message_type: Optional[Union[str, List[str]]] = None,
    ):
        if message_type is None:
            self.callbacks.append(callback)
        elif isinstance(message_type, str):
            self.typed_callbacks[message_type].append(callback)
        else:
            for i in message_type:
                self.typed_callbacks[i].append(callback)

    def on(self, *message_types: str):
        def deco(func: MessageCallback):
            if len(message_types) == 0:
                self.register_callback(func)
            else:
                for i in message_types:
                    self.register_callback(func, i)
            return func

        return deco

    def apply(self, module: Module):
        if hasattr(module, "before_apply"):
            module.before_apply(self)  # type: ignore
        for callback in module.callbacks:
            self.register_callback(callback)
        for message_type, callbacks in module.typed_callbacks.items():
            for callback in callbacks:
                self.register_callback(callback, message_type)
        if hasattr(module, "after_apply"):
            module.after_apply(self)  # type: ignore
