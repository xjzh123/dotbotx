import functools
from typing import Callable, Union


def tryit(
    handler: Callable, exceptions: Union[type[Exception], tuple[type[Exception]]]
):
    def deco(func: Callable):
        @functools.wraps(func)
        def inner(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                handler(e, *args, **kwargs)

        return inner

    return deco
