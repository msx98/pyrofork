#  Pyrofork - Telegram MTProto API Client Library for Python
#  Copyright (C) 2017-present Dan <https://github.com/delivrance>
#  Copyright (C) 2022-present Mayuri-Chan <https://github.com/Mayuri-Chan>
#
#  This file is part of Pyrofork.
#
#  Pyrofork is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Lesser General Public License as published
#  by the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Pyrofork is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with Pyrofork.  If not, see <http://www.gnu.org/licenses/>.

import inspect
import logging
import traceback
import typing
import os
from datetime import datetime
from enum import Enum
from json import dumps

import pyrogram

PYROGRAM_UNSAFE_PARSE = os.environ.get("PYROGRAM_UNSAFE_PARSE", "0") == "1"

class ObjectMeta(type):
    def __init__(cls, name, bases, namespace):
        super().__init__(name, bases, namespace)
        if ('_parse' in namespace) and not PYROGRAM_UNSAFE_PARSE:
            original = namespace['_parse']
            original_func = original.__func__ if isinstance(original, staticmethod) else original

            def _make_safe(func, klass):
                if inspect.iscoroutinefunction(func):
                    async def _parse(*args, **kwargs):
                        try:
                            return await func(*args, **kwargs)
                        except Exception:
                            logging.error(
                                f"Error parsing {klass.__name__}:\n" + traceback.format_exc()
                            )
                            return None
                else:
                    def _parse(*args, **kwargs):
                        try:
                            return func(*args, **kwargs)
                        except Exception:
                            logging.error(
                                f"Error parsing {klass.__name__}:\n" + traceback.format_exc()
                            )
                            return None
                return staticmethod(_parse)

            cls._parse = _make_safe(original_func, cls)


class Object(metaclass=ObjectMeta):
    def __init__(self, client: "pyrogram.Client" = None):
        self._client = client

    def bind(self, client: "pyrogram.Client"):
        """Bind a Client instance to this and to all nested Pyrogram objects.

        Parameters:
            client (:obj:`~pyrogram.types.Client`):
                The Client instance to bind this object with. Useful to re-enable bound methods after serializing and
                deserializing Pyrogram objects with ``repr`` and ``eval``.
        """
        self._client = client

        for i in self.__dict__:
            o = getattr(self, i)

            if isinstance(o, Object):
                o.bind(client)

    @staticmethod
    def default(obj: "Object"):
        if isinstance(obj, bytes):
            return repr(obj)

        # https://t.me/pyrogramchat/167281
        # Instead of re.Match, which breaks for python <=3.6
        if isinstance(obj, typing.Match):
            return repr(obj)

        if isinstance(obj, Enum):
            return str(obj)

        if isinstance(obj, datetime):
            return str(obj)

        attributes_to_hide = [
            "raw"
        ]

        filtered_attributes = {
            attr: ("*" * 9 if attr == "phone_number" else getattr(obj, attr))
            for attr in filter(
                lambda x: not x.startswith("_") and x not in attributes_to_hide,
                obj.__dict__,
            )
            if getattr(obj, attr) is not None
        }

        return {
            "_": obj.__class__.__name__,
            **filtered_attributes
        }

    def __str__(self) -> str:
        return dumps(self, indent=4, default=Object.default, ensure_ascii=False)

    def __repr__(self) -> str:
        return "pyrogram.types.{}({})".format(
            self.__class__.__name__,
            ", ".join(
                f"{attr}={repr(getattr(self, attr))}"
                for attr in filter(lambda x: not x.startswith("_"), self.__dict__)
                if getattr(self, attr) is not None
            )
        )

    def __eq__(self, other: "Object") -> bool:
        for attr in self.__dict__:
            try:
                if attr.startswith("_"):
                    continue

                if getattr(self, attr) != getattr(other, attr):
                    return False
            except AttributeError:
                return False

        return True

    def __setstate__(self, state):
        for attr in state:
            obj = state[attr]

            # Maybe a better alternative would be https://docs.python.org/3/library/inspect.html#inspect.signature
            if isinstance(obj, tuple) and len(obj) == 2 and obj[0] == "dt":
                state[attr] = datetime.fromtimestamp(obj[1])

        self.__dict__ = state

    def __getstate__(self):
        state = self.__dict__.copy()
        state.pop("_client", None)

        for attr in state:
            obj = state[attr]

            if isinstance(obj, datetime):
                state[attr] = ("dt", obj.timestamp())

        return state
