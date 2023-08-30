from collections import defaultdict
from typing import DefaultDict, List, Optional, Union

from ..core import MessageCallback


class Module():
    def __init__(self):
        self.callbacks: List[MessageCallback] = []
        self.typed_callbacks: DefaultDict[str, List[MessageCallback]] = defaultdict(
            list
        )

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
