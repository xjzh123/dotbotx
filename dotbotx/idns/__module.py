from __future__ import annotations

import json
import threading
import time
from typing import Callable, List, Optional, Literal, Union
import warnings

import websocket

from ..abstract import AbstractConnector, AbstractMsg, AbstractUserInfo
from ..core import Chatter, Context


WSMessageCallback = Callable[[websocket.WebSocketApp, str], None]


class IDNSConnector(AbstractConnector):
    def __init__(
        self,
        country: str,
        user_agent: str,
        url: str = "ws://ws.idnsportal.com:444/",
        site: str = "IDNS",
    ):
        self.url = url
        self.site = site
        self.country = country
        self.user_agent = user_agent
        self.ws = websocket.WebSocketApp(self.url, header={"User-Agent": user_agent})
        self.send_hooks: List[Callable[[str], None]] = []

        self.init_finished = False
        self._last_message_id = -1

        self.ws.on_message = self.__basic_message_callback

        # def ws_on_open(ws: websocket.WebSocketApp):
        #     ...

        # def ws_on_message(ws: websocket.WebSocketApp, data: str):
        #     ...

        # def ws_on_error(ws: websocket.WebSocketApp, exception: Exception):
        #     ...

        # def ws_on_cont_message(ws: websocket.WebSocketApp, data: str, data_type: int):
        #     ...

        # def ws_on_data(ws: websocket.WebSocketApp, data: str, data_type: int, continue_flag: int):
        #     ...

    def __basic_message_callback(self, ws: websocket.WebSocketApp, data: str):
        message = self.parse_message(data)

        if message.type == "initFinished" and message.data.get("data") == True:
            self.init_finished = True

        if message.message:
            self._last_message_id = message.message.get("messageId")

    def set_chatter(self, chatter: Chatter):
        self.chatter: Chatter = chatter

        def message_callback(ws: websocket.WebSocketApp, data: str):
            self.__basic_message_callback(ws, data)

            message = self.parse_message(data)

            context = Context(self.chatter, message)
            if self.chatter.message_callback:
                self.chatter.message_callback(context)

        self.ws.on_message = message_callback

    @property
    def message_callback(self) -> Optional[WSMessageCallback]:
        return self.ws.on_message

    @property
    def is_running(self):
        return self.ws.keep_running

    def start(self, channel: str, nick: str, password: Optional[str] = None):
        self.__start(channel, nick, password)

        self._thread = threading.Thread(target=self.run_forever, daemon=True)
        self._thread.start()

    def __start(self, channel: str, nick: str, password: Optional[str]):
        if self.ws.keep_running:
            raise RuntimeError("Already running")

        if password:
            warnings.warn(
                "IDNS Connectors doesn't support passwords! Passwords will be ignored."
            )

        self.channel = channel
        self.nick = nick

        def ping():
            while True:
                self.send_dict({"type": "ping", "group": self.channel})
                time.sleep(30)

        def ws_on_open(ws: websocket.WebSocketApp):
            self.join(channel, nick)

            threading.Thread(target=ping, daemon=True).start()

        self.ws.on_open = ws_on_open

    def wait(self):
        try:
            self._thread.join()
        except (AttributeError, RuntimeError):
            raise RuntimeError("Connection is not started yet. Use start() first.")

    def run_forever(self, channel: str, nick: str, password: Optional[str]):
        self.__start(channel, nick, password)
        self.ws.run_forever()

    def join(self, channel: str, nick: str):
        payload = {
            "type": "init",
            "group": channel,
            "name": nick,
            "country": self.country,
            "userAgent": self.user_agent,
            "lastMessageId": self._last_message_id,
        }
        self.send_dict(payload)

    def quit(self):
        self.ws.close()

    def send_chat(self, text: str):
        self.send_dict(
            {
                "type": "message",
                "group": self.channel,
                "name": self.nick,
                "text": text,
                "date": int(time.time() * 1000),
                "lastMessageId": self._last_message_id,
            }
        )

    def send_whisper(self, text: str, nick: str):
        warnings.warn(
            "IDNS Chatters doesn't support whispering. Will fallback to send_chat, with a @<nick> mention."
        )
        self.send_chat(f"@{nick} {text}")

    def send_emote(self, text: str):
        warnings.warn(
            "IDNS Chatters doesn't support emoting. Will fallback to send_chat."
        )
        self.send_chat(f"*{self.nick} {text}")

    def send_dict(self, message: dict):
        self.send_string(json.dumps(message))

    def send_string(self, message: str):
        if not self.ws.keep_running:
            raise RuntimeError("WebSocket is not connected.")
        for func in self.send_hooks:
            func(message)
        self.ws.send(message)

    def parse_message(self, message: str) -> IDNSMsg:
        return IDNSMsg(message, not self.init_finished)


MessageType = Literal[
    "message",
    "pong",
    "online",
    "command",
    "initFinished",
]


class IDNSMsg(AbstractMsg):
    def __init__(self, data: str, is_history: bool) -> None:
        self.raw_data = data
        self.data: dict = json.loads(data)
        self.is_history = is_history

        if "message" in self.data:
            self.message: Optional[dict[str, Union[str, int]]] = self.data["message"]
        else:
            self.message = None

        self.extras: dict = {}
        self.type: MessageType

        type_: str = self.data.get("type", "unknown")
        if type_ in ["message", "pong"]:
            self.type = type_  # type: ignore
        elif type_ == "command":
            self.type = self.data.get("name", "command")
        else:
            self.type = type_  # type: ignore

    @property
    def is_feedback(self) -> bool:
        if self.message:
            return self.message.get("type") == "sent"
        return False

    @property
    def raw_text(self) -> Optional[str]:
        if self.message:
            return self.message.get("text")  # type: ignore

    @property
    def text(self) -> Optional[str]:
        return self.raw_text

    @property
    def time(self) -> Optional[int]:
        return None

    @property
    def user_info(self) -> Optional[IDNSUserInfo]:
        if self.message:
            return IDNSUserInfo(self.message)

    @property
    def users(self) -> Optional[tuple[IDNSUserInfo]]:
        raise KeyError('"users" not available for IDNS Message.')

    @property
    def sender(self) -> Optional[IDNSUserInfo]:
        return self.user_info


class IDNSUserInfo(AbstractUserInfo):
    def __init__(self, *dicts):
        self._data = {}
        for dct in dicts:
            self._data.update(dct)

        self.trip = None
        self.color = None
        self.level = None
        self.utype = None
        self.hash = None

    @property
    def nick(self) -> Optional[str]:
        return self._data.get("name")

    @property
    def avatar(self) -> Optional[str]:
        return self._data.get("avatar")
