from dataclasses import dataclass
from functools import wraps

from dataclasses_json import dataclass_json
import json
from hashlib import md5
from pathlib import Path
from typing import TypeVar, Generic, get_args, Union, Dict, Any
from uuid import UUID

import boto3

from pdep.inter import implements
from pdep.utils import DynamicDataContainer, dict_to_class

zstr = Union[str, None]


class ResourceManager:

    def get_state(self, uuid: UUID | str, from_delete=False) -> dict | None:
        pass

    def set_state(self, uuid: UUID | str, state: dict) -> None:
        pass

    def mark_destroy(self, uuid: UUID | str, state: dict) -> None:
        pass

    def delete_state(self, uuid: UUID | str, from_delete=False) -> None:
        pass


@implements(ResourceManager)
class FileResourceManager:

    def __init__(self, path: str | Path):
        self.__path = Path(path)
        self.__state = {"to_destroy": {}}

    def get_state(self, uuid: UUID | str, from_delete=False) -> dict | None:
        uuid = str(uuid)
        if not self.__path.exists():
            return None

        with self.__path.open('r') as fp:
            self.__state = json.load(fp)
            fp.close()
        state = self.__state
        if from_delete:
            state = self.__state["to_destroy"]
        if uuid in state:
            return state[uuid]
        else:
            return None

    def set_state(self, uuid: UUID | str, state: dict) -> None:
        if self.__path.exists():
            with self.__path.open('r') as fp:
                self.__state = json.load(fp)
                fp.close()

        self.__state[str(uuid)] = state

        with self.__path.open('w') as fp:
            json.dump(self.__state, fp, indent=4)
            fp.close()

    def mark_destroy(self, uuid: UUID | str, state: dict) -> None:
        self.__state["to_destroy"][str(uuid)] = state
        with self.__path.open('w') as fp:
            json.dump(self.__state, fp, indent=4)
            fp.close()

    def delete_state(self, uuid: UUID | str, from_delete=False) -> None:
        if self.__path.exists():
            with self.__path.open('r') as fp:
                self.__state = json.load(fp)
                fp.close()

        if from_delete:
            if str(uuid) in self.__state["to_destroy"]:
                del self.__state["to_destroy"][str(uuid)]
        else:
            if str(uuid) in self.__state:
                del self.__state[str(uuid)]

        with self.__path.open('w') as fp:
            json.dump(self.__state, fp, indent=4)
            fp.close()


class AwsLocalStackProvider:
    def __init__(self):
        self.__session = boto3.Session(
            aws_access_key_id="test",
            aws_secret_access_key="test"
        )
        self.__endpoints = {
            "apigateway": "http://localhost:4566",
            "apigatewayv2": "http://localhost:4566",
            "cloudformation": "http://localhost:4566",
            "cloudwatch": "http://localhost:4566",
            "dynamodb": "http://localhost:4566",
            "ec2": "http://localhost:4566",
            "es": "http://localhost:4566",
            "elasticache": "http://localhost:4566",
            "firehose": "http://localhost:4566",
            "iam": "http://localhost:4566",
            "kinesis": "http://localhost:4566",
            "lambda": "http://localhost:4566",
            "rds": "http://localhost:4566",
            "redshift": "http://localhost:4566",
            "route53": "http://localhost:4566",
            "s3": "http://s3.localhost.localstack.cloud:4566",
            "secretsmanager": "http://localhost:4566",
            "ses": "http://localhost:4566",
            "sns": "http://localhost:4566",
            "sqs": "http://localhost:4566",
            "ssm": "http://localhost:4566",
            "stepfunctions": "http://localhost:4566",
            "sts": "http://localhost:4566",
        }

    @property
    def session(self):
        return self.__session

    def get_endpoint(self, name):
        return self.__endpoints[name]

    def create_resource(self, name):
        return self.__session.resource(name, endpoint_url=self.get_endpoint(name))

    def create_client(self, name):
        return self.__session.client(name, endpoint_url=self.get_endpoint(name))


T = TypeVar('T')


class Connector(Generic[T]):
    def __init__(self, obj, func):
        self.__obj = obj
        self.__func = func
        self.__value = None
        self.__resolved = False

    @property
    def obj(self):
        return self.__obj

    @property
    def value(self) -> T:
        self.resolve()
        return self.__value

    def resolve(self):
        if not self.__resolved:
            self.__value = self.__func(self.__obj)
            self.__resolved = True


def output_property(prop_func):
    @wraps(prop_func)
    def func(self):
        return Connector(self, prop_func)

    return func


StateT = TypeVar('StateT')


class BaseResource(Generic[StateT]):

    def __init__(self, *args, **kwargs):
        self.__type_t = get_args(self.__orig_bases__[0])[0]
        self.__uuid: UUID | None = None
        self.__path: str = "$"
        self.__state: StateT = None
        if self.__type_t != StateT:
            self.__state: StateT = self.__type_t()
        self.__depends = set()
        self.__supports = set()
        self._applied = False
        self.__plan: 'BasePlan' = None

    def __post__init__(self):
        pass

    @property
    def uuid(self):
        return self.__uuid

    @uuid.setter
    def uuid(self, uuid: UUID):
        self.__uuid = uuid

    @property
    def path(self):
        return self.__path

    @path.setter
    def path(self, value):
        self.__path = value

    @property
    def plan(self):
        return self.__plan

    @plan.setter
    def plan(self, plan: 'BasePlan'):
        self.__plan = plan

    @property
    def inputs(self):
        return dict_to_class(self.__inputs__)

    @property
    def state(self) -> StateT:
        return self.__state

    @property
    def applied(self):
        return self._applied

    def reset_apply_state(self):
        self._applied = False

    def resolve_connector(self, path):
        raise Exception(f"Only plan have resource path and this is a single resource")

    def depends_on(self, res: 'BaseResource'):
        self.__depends.add(res)
        res.__supports.add(self)

    def resolve_dependencies(self):
        for connector in self.__connectors__:
            self.depends_on(connector.obj)

    def __resolve_dependent_values_walk(self, parent, key, item):
        if type(item) == dict:
            for name, child in item.items():
                self.__resolve_dependent_values_walk(item, name, child)
        if type(item) == list:
            for i, child in enumerate(item):
                self.__resolve_dependent_values_walk(item, i, child)
        if type(item) == Connector:
            parent[key] = item.value

    def resolve_dependent_values(self):
        for name, item in self.__inputs__.items():
            self.__resolve_dependent_values_walk(self.__inputs__, name, item)

    def __create_state_dict(self, state, inputs):
        return {
            'state': state.to_dict() if state else None,
            'inputs': inputs,
            'class': f"{self.__class__.__module__}.{self.__class__.__name__}",
            'path': self.path,
            'uuid': str(self.uuid),
            'plan': f"{self.__plan.__class__.__module__}.{self.__plan.__class__.__name__}" if self.plan else None,
            'plan_uuid': str(self.__plan.uuid) if self.plan else None
        }

    def mark_destroy(self, resource_manager: ResourceManager, env_state, env_inputs):
        if env_state is None:
            return
        state_dict = self.__create_state_dict(env_state, env_inputs)
        resource_manager.mark_destroy(self.uuid, state_dict)

    def __read_state(self, resource_manager: ResourceManager, from_deleted=False):
        state_dict = resource_manager.get_state(self.uuid, from_deleted)
        state_obj = self.__type_t.from_dict(state_dict['state']) if state_dict and state_dict['state'] else None
        inputs = state_dict['inputs'] if state_dict else None
        return inputs, state_obj

    def apply(self, resource_manager: ResourceManager, provider, dry=False):
        if self._applied:
            return
        for res in self.__depends:
            res.apply(resource_manager, provider, dry)
        inputs, state_obj = self.__read_state(resource_manager)
        self.resolve_dependent_values()
        if dry:
            self.do_apply_dry(state_obj, inputs, resource_manager, provider)
        else:
            self.do_apply(state_obj, inputs, resource_manager, provider)
        state_dict = self.__create_state_dict(self.state, self.__inputs__)
        resource_manager.set_state(self.uuid, state_dict)
        self._applied = True

    def do_apply(self, env_state: T, inputs: Dict[str, Any], resource_manager, provider):
        print(f"Default do_apply for:{self.__class__.__name__} uuid:{self.uuid}")

    def do_apply_dry(self, env_state: T, inputs: Dict[str, Any], resource_manager, provider):
        print(f"Default do_apply_dry for:{self.__class__.__name__} uuid:{self.uuid}")

    def destroy(self, resource_manager: ResourceManager, provider, dry=False, from_deleted=False):
        if self._applied:
            return
        if not from_deleted:
            for res in self.__supports:
                if res != self.__plan:
                    res.destroy(resource_manager, provider, dry)
        inputs, state_obj = self.__read_state(resource_manager, from_deleted)
        self.resolve_dependent_values()
        if dry:
            self.do_destroy_dry(state_obj, inputs, resource_manager, provider)
        else:
            self.do_destroy(state_obj, inputs, resource_manager, provider)
        resource_manager.delete_state(self.uuid, from_deleted)

    def do_destroy(self, env_state: T, inputs: Dict[str, Any], resource_manager, provider):
        print(f"Default do_destroy for:{self.__class__.__name__} uuid:{self.uuid}")

    def do_destroy_dry(self, env_state: T, inputs: Dict[str, Any], resource_manager, provider):
        print(f"Default do_destroy_dry for:{self.__class__.__name__} uuid:{self.uuid}")


class resource:
    def __init__(self):
        pass

    def __call__(self, cls):
        org_init = cls.__init__

        def __new__init__(self, *args, **kwargs):
            connectors = []
            self.__inputs__ = kwargs
            if len(args):
                raise Exception("No positional args are allowed in resource init ")
            for name, arg in kwargs.items():
                if type(arg) == Connector:
                    connectors.append(arg)
            self.__connectors__ = connectors
            self.__inputs__ = kwargs
            org_init(self, *args, **kwargs)
            self.__post__init__()

        assert issubclass(cls, BaseResource)
        cls.__init__ = __new__init__
        return cls


def sub_uuid(uuid: UUID, name: str):
    md = md5()
    md.update(f"{uuid}.{name}".encode('utf-8'))
    return UUID(md.hexdigest())


class BasePlan(BaseResource[StateT]):
    def __init__(self, uuid):
        super().__init__()
        self.__res = DynamicDataContainer()
        self.uuid = uuid
        self.plan = None

    def __post__init__(self):
        for path, value in self.__res.items():
            if isinstance(value, BaseResource):
                value.uuid = sub_uuid(self.uuid, path)
                value.path = path
                value.plan = self
                self.depends_on(value)

    @property
    def resources(self):
        return self.__res

    def resolve_connector(self, path):
        return self.__res.from_path(path)

    def reset_apply_state(self):
        super().reset_apply_state()
        for path, res in self.__res.items():
            res.reset_apply_state()

    def resolve_dependencies(self):
        super().resolve_dependencies()
        for path, res in self.__res.items():
            res.resolve_dependencies()

    def apply(self, resource_manager: ResourceManager, provider, dry=False):
        self.resolve_dependencies()
        self.reset_apply_state()
        super().apply(resource_manager, provider, dry)

    def destroy(self, resource_manager: ResourceManager, provider, dry=False, from_deleted=False):
        assert not from_deleted
        self.resolve_dependencies()
        self.reset_apply_state()
        for path, res in self.__res.items():
            res.destroy(resource_manager, provider, dry)
        resource_manager.delete_state(self.uuid)
        self._applied = True
