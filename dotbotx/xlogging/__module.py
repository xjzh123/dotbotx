import logging
from typing import Callable, Optional
from ..core import Context
from ..xcore import XChatter


def apply_logging(
    chatter: XChatter,
    logger: Optional[logging.Logger] = None,
    log_on_message: Optional[Callable[[logging.Logger, Context], None]] = None,
    log_on_send: Optional[Callable[[logging.Logger, str], None]] = None,
):
    if logger is None:
        logger = logging.getLogger(
            f"chatter.{chatter.nick}|{chatter.channel}|{str(id(chatter))[-3:]}"
        )
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "[%(asctime)s %(name)s:%(levelname)s] %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    def _log_on_message(ctx: Context):
        if log_on_message is None:
            logger.info(f"Received message: {ctx.message.raw_data}")
        else:
            log_on_message(logger, ctx)

    chatter.register_callback(_log_on_message)

    def send_hook(message: str):
        if log_on_send is None:
            logger.info(f"Sent data: {message}")
        else:
            log_on_send(logger, message)

    chatter.connector.send_hooks.append(send_hook)

    return chatter
