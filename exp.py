import inspect
from dataclasses import dataclass, field
from functools import wraps
from pprint import pprint

from dataclasses_json import dataclass_json
from typing import TypeVar, Generic, get_args

from pdep import zstr
from pdep.utils import convert_something_values


class My:
    def __init__(self, i):
        self.i = i


@dataclass_json
@dataclass
class DataC2:
    other: zstr = None


@dataclass_json
@dataclass
class DataC:
    something: zstr = None
    my: My | None = None
    other: DataC2 = field(default_factory=DataC2)


dc = DataC(
    something="amir",
    my=My(5),
    other=DataC2(
        other="other"
    )
)


def conv(value):
    if isinstance(value, My):
        return value.i
    return value


new_dc = convert_something_values(dc, conv)

pprint(dc)
pprint(new_dc)