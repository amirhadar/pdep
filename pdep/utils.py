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