from __future__ import annotations

from typing import Any, Callable, Coroutine, Optional, Union

from ..abstract import AbstractUserInfo, AbstractConnector, AbstractMsg


class Chatter:
    def __init__(
        self,
        connector: AbstractConnector,
        channel: str,
        nick: str,
        password: str = "",
    ):
        self.connector = connector
        self.nick = nick
        self.password = password
        self.channel = channel
        self.message_callback: Optional[MessageCallback] = None

        self.connector.set_chatter(self)

    def set_message_callback(self, callback: MessageCallback):
        self.message_callback = callback

    @property
    def is_running(self) -> bool:
        return self.connector.is_running

    def start(self):
        self.connector.start(self.channel, self.nick, self.password)

    def wait(self):
        self.connector.wait()

    def run(self):
        self.connector.run_forever(self.channel, self.nick, self.password)

    def quit(self):
        self.connector.quit()

    def set_parameters(self, channel: Optional[str] = None, nick: Optional[str] = None, password: Optional[str] = None):
        if channel is not None:
            self.channel = channel
        if nick is not None:
            self.nick = nick
        if password is not None:
            self.password = password

    def chat(self, text: str):
        self.connector.send_chat(text)

    def whisper(self, text: str, to: str):
        self.connector.send_whisper(text, to)

    def me(self, text: str):
        self.connector.send_emote(text)


class Context:
    def __init__(self, chatter: Chatter, message: AbstractMsg):
        self.chatter = chatter
        self.message = message

    def reply(self, text: str):
        if self.message.type == "whisper":
            self.chatter.whisper(text, self.message.user_info.nick)  # type: ignore
        else:
            self.chatter.chat(text)


MessageCallback = Callable[[Context], Union[None, Coroutine[Any, Any, None]]]
