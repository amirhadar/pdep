import time
import copy
import dataclasses
import functools
import importlib
import inspect
import logging
from pathlib import Path



class DynamicDataContainer:

    def __init__(self, parent=None, name="$"):
        self.__parent = parent
        self.__name = name
        self.__path = f"{parent.path}.{name}" if parent else name

    @property
    def path(self):
        return self.__path

    @property
    def name(self):
        return self.__name

    @property
    def parent(self):
        return self.__parent

    def __getattr__(self, name):
        if name not in self.__dict__:
            super().__setattr__(name, DynamicDataContainer(self, name))
        return super().__getattribute__(name)

    def __repr__(self):
        attrs = ""
        for name, value in self.__dict__.items():
            if not name.startswith("_"):
                attrs += f"{name}={str(value)}, "
        return f"{self.__class__.__name__}({attrs})"

    def items(self):
        containers = [self]
        for container in containers:
            for name, value in container.__dict__.items():
                if name.startswith("_"):
                    continue
                if type(value) == DynamicDataContainer:
                    containers.append(value)
                elif type(value) == list:
                    for i, list_val in enumerate(value):
                        yield f"{container.path}.{name}[{i}]", value[i]
                else:
                    yield f"{container.path}.{name}", value

    def from_path(self, path):
        if not path.startswith(self.path + "."):
            raise Exception(f"invalid path:'{path}' for container path:'{self.path}'")
        rel_path = path[len(self.path) + 1:]
        if '.' in rel_path:
            attr_name, rest = rel_path.split(".", 1)
            c = self.__dict__[attr_name]
            return c.from_path(path)
        if '[' in rel_path:
            pos = rel_path.find('[')
            name = rel_path[:pos]
            range_str = rel_path[pos:]
            attr = self.__dict__[name]
            return eval(f"attr{range_str}")
        else:
            return self.__dict__[rel_path]

    def to_dict(self):
        ret = {}
        for name, value in self.__dict__.items():
            if name.startswith("_"):
                continue
            if type(value) == DynamicDataContainer:
                ret[name] = value.to_dict()
            else:
                ret[name] = value
        return ret

    def from_dict(self, d):
        for name, value in d.items():
            if type(value) == dict:
                c = DynamicDataContainer(self, name)
                c.from_dict(value)
                self.__dict__[name] = c
            else:
                self.__dict__[name] = value


class dict_to_class(object):
    def __init__(self, my_dict):
        for key in my_dict:
            setattr(self, key, my_dict[key])

    def __repr__(self):
        s = f"cdict("
        for key, value in self.__dict__.items():
            if not key.startswith("_"):
                s += f"{key}={str(value)}"
        s += ")"
        return s


class log_func:
    ABOVE_DEBUG = 15

    def __init__(self, level=15):
        self.__level = level

    def __log(self, logger, func, msg):
        fn, lno, func_, sinfo = logger.findCaller(stack_info=False, stacklevel=2)
        record = logger.makeRecord(logger.name, self.__level, fn, lno, msg, args={},
                                   exc_info=None, func=func.__name__, extra=None, sinfo=sinfo)
        logger.handle(record)

    def __call__(self, func):

        @functools.wraps(func)
        def log_func(his_self, *args, **kwargs):
            logger = his_self.logger
            spec = inspect.getfullargspec(func)
            skwargs = {key: str(value) for key, value in kwargs.items()}

            if len(spec.args) <= len(args):
                msg = f"Method:{func.__qualname__} missing positional args, method called with{args}: while spec:{spec.args}"
                raise Exception(msg)
            for i, arg in enumerate(args):
                skwargs[spec.args[i + 1]] = str(arg)
            self.__log(logger, func, f"{func.__qualname__}({skwargs})")
            ret = func(his_self, *args, **kwargs)
            self.__log(logger, func, f"{func.__qualname__} -> {str(ret)}")
            return ret

        return log_func


def convert_dict_values(d, conv_func):
    new_d = {}
    for key, value in d.items():
        if dataclasses.is_dataclass(value):
            new_d[key] = convert_dataclass_values(value, conv_func)
        elif type(value) == list:
            new_d[key] = convert_list_values(value, conv_func)
        else:
            new_d[key] = conv_func(value)
    return new_d


def convert_list_values(l, conv_func):
    new_l = []
    for value in l:
        if dataclasses.is_dataclass(value):
            new_l.append(convert_dataclass_values(value, conv_func))
        elif type(value) == list:
            new_l.append(convert_list_values(value, conv_func))
        else:
            new_l.append(conv_func(value))
    return new_l


def convert_dataclass_values(dc, conv_func):
    for field in dc.__dataclass_fields__:
        value = getattr(dc, field)
        setattr(dc, field, convert_something_values(value, conv_func))
    return dc


def convert_something_values(something, conv_func):
    if dataclasses.is_dataclass(something):
        new_something = convert_dataclass_values(something, conv_func)
    elif type(something) == list:
        new_something = convert_list_values(something, conv_func)
    elif type(something) == dict:
        new_something = convert_dict_values(something, conv_func)
    else:
        new_something = conv_func(something)
    return new_something


def load_class_from_str(cls_full_name):
    mod_name, cls_name = cls_full_name.rsplit('.', 1)
    mod = importlib.import_module(mod_name)
    cls = mod.__dict__[cls_name]
    return cls


def setup_logging(log_path=".", component_name="pdep", console_level=logging.INFO, file_level=logging.DEBUG):
    log_path = Path(log_path)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    format_str = "%(asctime).19s [%(levelname)8s][%(threadName)12s][{component:12s}][%(name)55s][%(funcName)25s]: %(message)s".format(
        component=component_name
    )
    log_formatter = logging.Formatter(format_str)
    file_handler = logging.FileHandler(
        log_path.joinpath(f'{component_name}.log'),
        encoding='utf-8'
    )
    file_handler.setFormatter(log_formatter)
    file_handler.setLevel(file_level)
    root_logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    console_handler.setLevel(console_level)
    root_logger.addHandler(console_handler)


def _aws_tags_to_dict(aws_tags):
    tags = {}
    for pair in aws_tags:
        tags[pair['Key']] = pair['Value']
    return tags


def _dict_to_aws_tags(d, additional={}):
    d = copy.deepcopy(d)
    d.update(additional)
    tags = [
        {
            'Key': key,
            'Value': str(value)
        }
        for key, value in d.items()
    ]
    return tags


def unused(*args):
    for arg in args:
        del arg


def do_with_timeout(predicate, timeout, sleep=5):
    start_t = time.time()
    while predicate():
        if time.time() - start_t > timeout:
            raise Exception(f"timeout")
        time.sleep(sleep)
