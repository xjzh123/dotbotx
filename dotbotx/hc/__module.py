from __future__ import annotations

import json
import re
import threading
from typing import Callable, Optional, Literal

import websocket

from ..abstract import AbstractConnector, AbstractMsg, AbstractUserInfo
from ..core import Chatter, Context


WSMessageCallback = Callable[[websocket.WebSocketApp, str], None]


class HCConnector(AbstractConnector):
    def __init__(self, url: str = "wss://hack.chat/chat-ws", site: str = "HC"):
        self.url = url
        self.site = site
        self.ws = websocket.WebSocketApp(self.url)
        self.send_hooks: list[Callable[[str], None]] = []

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

    def set_chatter(self, chatter: Chatter):
        self.chatter: Chatter = chatter

        def message_callback(ws: websocket.WebSocketApp, data: str):
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

        def ws_on_open(ws: websocket.WebSocketApp):
            self.join(channel, nick, password)

        self.ws.on_open = ws_on_open

    def wait(self):
        try:
            self._thread.join()
        except (AttributeError, RuntimeError):
            raise RuntimeError("Connection is not started yet. Use start() first.")

    def run_forever(self, channel: str, nick: str, password: Optional[str] = None):
        self.__start(channel, nick, password)
        self.ws.run_forever()

    def join(self, channel: str, nick: str, password: Optional[str] = None):
        payload = {"cmd": "join", "channel": channel, "nick": nick}
        if password:
            payload["pass"] = password
        self.send_dict(payload)

    def quit(self):
        self.ws.close()

    def send_chat(self, text: str):
        if "$" in text and "\\rule" in text:
            text = text.replace("\\rule", "&#92;rule")
        self.send_dict({"cmd": "chat", "text": text})

    def send_whisper(self, text: str, nick: str):
        self.send_dict({"cmd": "whisper", "nick": nick, "text": text})

    def send_emote(self, text: str):
        self.send_dict({"cmd": "emote", "text": text})

    def send_dict(self, message: dict):
        self.send_string(json.dumps(message))

    def send_string(self, message: str):
        if not self.ws.keep_running:
            raise RuntimeError("WebSocket is not connected.")
        for func in self.send_hooks:
            func(message)
        self.ws.send(message)

    def parse_message(self, message: str) -> HCMsg:
        return HCMsg(message)


def parse_hc_message(message: str) -> HCMsg:
    return HCMsg(message)


MessageType = Literal[
    "chat",
    "emote",
    "warn",
    "onlineSet",
    "onlineAdd",
    "onlineRemove",
    "captcha",
    "updateUser",
    "whisper",
    "invite",
    "info",
    "changeNick",
    "unknown",
]


class HCMsg(AbstractMsg):
    def __init__(self, data: str) -> None:
        self.raw_data = data
        self.data: dict = json.loads(data)
        self.extras: dict = {}
        self.type: MessageType

        cmd: Optional[str] = self.data.get("cmd")
        if cmd in [
            "chat",
            "emote",
            "warn",
            "onlineSet",
            "onlineAdd",
            "onlineRemove",
            "captcha",
            "updateUser",
        ]:
            self.type = cmd  # type: ignore
        elif cmd == "info":
            if self.data.get("type") in ["whisper", "invite", "emote"]:
                # `"cmd": "info", "type": "emote"` seems to be a legacy format of message, which may be replaced by `"cmd": "emote"` in HC now.
                self.type = self.data.get("type", "unknown")
            elif self.raw_text and re.match(r"(.+?) is now (.+?)", self.raw_text):
                match_: re.Match[str] = re.match(r"(.+?) is now (.+?)", self.raw_text)  # type: ignore
                self.type = "changeNick"
                self.extras["oldNick"] = match_.group(1)
                self.extras["newNick"] = match_.group(2)
            else:
                self.type = "info"
        else:
            self.type = "unknown"

    @property
    def is_feedback(self) -> bool:
        if not self.raw_text:
            return False

        if self.type == "whisper":
            if re.match(r"You whispered to @.+?: ", self.raw_text):
                return True

        elif self.type == "invite":
            if re.match(r"You invited .+? to \?", self.raw_text):
                return True

        return False

    @property
    def raw_text(self) -> Optional[str]:
        return self.data.get("text")

    @property
    def text(self) -> Optional[str]:
        if not self.raw_text:
            return None

        if self.type == "whisper":
            #fmt: off
            return re.match(
                r"(?:You whispered to @.+?: |.+? whispered: )(.+)", self.raw_text
            ).group(1)  # type: ignore
            # fmt: on

        elif self.type == "emote":
            return re.match(r"(?:@.+? )(.+)", self.raw_text).group(1)  # type: ignore

        else:
            return self.raw_text

    @property
    def time(self) -> Optional[int]:
        return self.data.get("time")

    @property
    def user_info(self) -> Optional[HCUserInfo]:
        if self.type in ["chat", "emote", "onlineAdd", "onlineRemove", "updateUser"]:
            # chat has almost full, emote and updateUser has some, onlineAdd has full, onlineRemove only has nick.
            return HCUserInfo(self.data)

        elif self.type in ["whisper", "invite"]:
            # whisper has almost full user info, while invite only has nick. however, both feedbacks have no user info.
            if self.is_feedback:
                return

            return HCUserInfo(self.data, {"nick": self.data.get("from")})

    @property
    def users(self) -> Optional[tuple[HCUserInfo]]:
        if "users" not in self.data:
            raise KeyError('"users" not found in raw message.')

        return tuple(map(HCUserInfo, self.data["users"]))

    @property
    def sender(self) -> Optional[HCUserInfo]:
        if self.type in ["chat", "emote", "whisper", "invite"]:
            return self.user_info


class HCChatMsg(HCMsg):
    @property
    def raw_text(self) -> str:
        return self.data.get("text")  # type: ignore


class HCUserInfo(AbstractUserInfo):
    def __init__(self, *dicts):
        self._data = {}
        for dct in dicts:
            self._data.update(dct)

    @property
    def nick(self) -> Optional[str]:
        return self._data.get("nick")

    @property
    def trip(self) -> Optional[str]:
        return self._data.get("trip")

    @property
    def color(self) -> Optional[str]:
        return self._data.get("color")

    @property
    def level(self) -> Optional[str]:
        return self._data.get("level")

    @property
    def utype(self) -> Optional[str]:
        return self._data.get("utype")

    @property
    def hash(self) -> Optional[str]:
        return self._data.get("hash")
