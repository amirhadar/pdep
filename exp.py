import inspect
from dataclasses import dataclass
from functools import wraps

from dataclasses_json import dataclass_json
from typing import TypeVar, Generic, get_args
self.__class__.__bases__[0].__bases__[0].__bases__[0]
self.__class__.__bases__[0].__bases__

class LazyProperty:
    def __init__(self, obj, func):
        self.__obj = obj
        self.__func = func
        self.__value = None
        self.__resolved = False

    @property
    def obj(self):
        return self.__obj

    @property
    def name(self):
        return self.__name

    @property
    def value(self):
        if not self.__resolved:
            self.__value = self.__func(self.__obj)
            self.__resolved = True
        return self.__value

    def __str__(self):
        return self.value

    def __int__(self):
        return self.value


def lazy_property(prop_func):
    @wraps(prop_func)
    def func(self):
        return LazyProperty(self, prop_func)

    return func


class A:
    def __init__(self):
        self.__p = "213"

    @property
    @lazy_property
    def prop(self):
        print("called")
        return self.__p


def print_caller():
    print(type(inspect.stack()[1].function))

class Foo:
    def hello(self, amir):
        print(amir)
        print_caller()


f = Foo()

f.hello("hello")
