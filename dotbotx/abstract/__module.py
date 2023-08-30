from __future__ import annotations

import abc
from typing import Callable, List, Optional

import websocket


class AbstractUserInfo(abc.ABC):
    @abc.abstractmethod
    def __init__(self, *dicts):
        self.nick: Optional[str]
        self.trip: Optional[str]
        self.color: Optional[str]
        self.level: Optional[str]
        self.utype: Optional[str]
        self.hash: Optional[str]


class AbstractMsg(abc.ABC):
    @abc.abstractmethod
    def __init__(self, message) -> None:
        self.raw_data: str
        self.data: dict
        self.extras: dict
        self.type: str
        self.is_feedback: bool
        self.raw_text: Optional[str]
        self.text: Optional[str]
        self.time: Optional[int]
        self.user_info: Optional[AbstractUserInfo]
        self.users: Optional[tuple[AbstractUserInfo]]
        self.sender: Optional[AbstractUserInfo]


class AbstractConnector(abc.ABC):
    @abc.abstractmethod
    def __init__(self, url: str, site: str) -> None:
        self.url: str
        self.site: str
        self.is_running: bool
        self.send_hooks: List[Callable[[str], None]]

    def set_chatter(self, chatter):
        ...

    @abc.abstractmethod
    def start(self, channel: str, nick: str, password: Optional[str] = None):
        ...

    @abc.abstractmethod
    def wait(self):
        ...

    @abc.abstractmethod
    def run_forever(self, channel: str, nick: str, password: Optional[str] = None):
        ...

    @abc.abstractmethod
    def quit(self):
        ...

    @abc.abstractmethod
    def send_chat(self, text: str):
        ...

    @abc.abstractmethod
    def send_whisper(self, text: str, nick: str):
        ...

    @abc.abstractmethod
    def send_emote(self, text: str):
        ...

    @abc.abstractmethod
    def send_dict(self, message: dict):
        ...

    @abc.abstractmethod
    def send_string(self, message: str):
        ...

    @abc.abstractmethod
    def parse_message(self, message: str) -> AbstractMsg:
        ...
