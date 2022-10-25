import inspect
from typing import Type, List


class NotComplient(Exception):
    pass


def check_interface(cls: Type, inter: Type, throw=False):
    def throw_not_complient(msg):
        if throw:
            raise NotComplient(msg)

    for name, attr in inter.__dict__.items():
        if name.startswith("_"):
            continue
        if inspect.isroutine(attr):
            if not hasattr(cls, name):
                raise NotComplient(f"Method '{name}' not implemented")
            sig_inter = inspect.signature(attr)
            sig_cls = inspect.signature(getattr(cls, name))
            if sig_inter != sig_cls:
                throw_not_complient(f"Method '{name}' signature issue. interface:{sig_inter} obj:{sig_cls}")
                return False
        if isinstance(attr, property):
            if not hasattr(cls, name):
                throw_not_complient(f"Property '{name}' not implemented")
                return False
            cls_attr = getattr(cls, name)
            sig_inter = inspect.signature(attr.fget)
            sig_cls = inspect.signature(cls_attr.fget)
            if sig_inter != sig_cls:
                throw_not_complient(f"Property '{name}' type issue. interface:{sig_inter} obj:{sig_cls}")
                return False
            if attr.fset and not cls_attr.fset:
                throw_not_complient(f"Property '{name}' setter not implemented")
                return False
            if attr.fdel and not cls_attr.fdel:
                throw_not_complient(f"Property '{name}' del not implemented")
                return False
    return True


class implements:
    def __init__(self, *interfaces):
        self.__interfaces = interfaces

    def __call__(self, cls):
        cls.__interfaces__ = self.__interfaces
        cls.interfaces = property(fget=lambda o: o.__class__.__interfaces__)
        cls.implements = lambda self, inter: inter in self.interfaces
        for inter in self.__interfaces:
            check_interface(cls, inter, throw=True)
        return cls


class Inter:
    def func(self, i: int) -> int:
        pass

    def func2(self, j: int) -> str:
        pass


class Base:
    def func(self, i: int) -> int:
        pass


@implements(Inter)
class MyClass(Base):
    def func2(self, j: int) -> str:
        pass
