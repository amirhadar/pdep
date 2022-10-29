import copy
import dataclasses
import importlib
import inspect
import logging
import uuid
from dataclasses import dataclass
from functools import wraps
import json
from hashlib import md5
from pathlib import Path
from typing import TypeVar, Generic, get_args, Union, Dict, Any, List
from uuid import UUID

import boto3
from dataclasses_json import dataclass_json

from pdep.inter import implements
from pdep.utils import DynamicDataContainer, dict_to_class, log_func, load_class_from_str, convert_somthing_values

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

    def get_to_destroy(self) -> List[Dict[str, Any]]:
        pass


@implements(ResourceManager)
class FileResourceManager:

    def __init__(self, logger, path: str | Path):
        self.__logger = logger if logger else logging.getLogger(self.full_name)
        self.__path = Path(path)
        self.__state = {"to_destroy": []}

    @property
    def logger(self):
        return self.__logger

    @property
    def full_name(self):
        return f"{self.__class__.__module__}.{self.__class__.__name__}({id(self)})"

    @log_func()
    def get_state(self, uuid: UUID | str, from_delete=False) -> dict | None:
        uuid = str(uuid)
        if not self.__path.exists():
            return None

        with self.__path.open('r') as fp:
            self.__state = json.load(fp)
            fp.close()
        state = self.__state
        if from_delete:
            state = {value['uuid']: value for value in self.__state["to_destroy"]}
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
        self.__state["to_destroy"].append(state)
        with self.__path.open('w') as fp:
            json.dump(self.__state, fp, indent=4)
            fp.close()

    def delete_state(self, uuid: UUID | str, from_delete=False) -> None:
        if self.__path.exists():
            with self.__path.open('r') as fp:
                self.__state = json.load(fp)
                fp.close()

        if from_delete:
            for i, state in enumerate(self.__state["to_destroy"]):
                if str(uuid) == state['uuid']:
                    del self.__state["to_destroy"][i]
                    break
        else:
            if str(uuid) in self.__state:
                del self.__state[str(uuid)]

        with self.__path.open('w') as fp:
            json.dump(self.__state, fp, indent=4)
            fp.close()

    def get_to_destroy(self) -> List[Dict[str, Any]]:
        if self.__path.exists():
            with self.__path.open('r') as fp:
                self.__state = json.load(fp)
                fp.close()
        else:
            return []

        return copy.deepcopy(self.__state['to_destroy'])


class AwsLocalStackProvider:
    def __init__(self, logger):
        self.__logger = logger if logger else logging.getLogger(self.full_name)
        self.__session = boto3.Session(
            aws_access_key_id="test",
            aws_secret_access_key="test",
            region_name='us-east-1'
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
    def logger(self):
        return self.__logger

    @property
    def full_name(self):
        return f"{self.__class__.__module__}.{self.__class__.__name__}({id(self)})"

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


class Connector:
    def __init__(self, obj, func, attr=None):
        self.__obj = obj
        self.__func = [func]
        self.__value = None
        self.__attr = attr
        self.__resolved = False

    @property
    def root_obj(self):
        return self.__obj if not isinstance(self.__obj, Connector) else self.__obj.root_obj

    @property
    def obj(self):
        return self.__obj

    @property
    def value(self) -> Any:
        return self.get_value()

    def get_value(self) -> Any:
        self.resolve()
        return self.__value

    def __conv_func(self, value):
        if isinstance(value, Connector):
            return value.value
        return value

    def resolve(self):
        if not self.__resolved:
            self.__value = self.__func[0](self.__obj)
            if self.__attr:
                self.__value = getattr(self.__value, self.__attr)
            self.__value = convert_somthing_values(self.__value, self.__conv_func)
            self.__resolved = True

    def __getattr__(self, name):
        if name.startswith("_") or name in ['resolve', 'value', 'obj', 'get_value']:
            return self.__getattribute__(name)
        return Connector(self, Connector.get_value, name)


def output_property(prop_func):
    @wraps(prop_func)
    def func(self):
        return Connector(self, prop_func)

    return func


def plan_output_property(prop_func):
    return prop_func


StateT = TypeVar('StateT')
InputT = TypeVar('InputT')
OutputT = TypeVar('OutputT')


@dataclass_json
@dataclass
class DefaultState:
    pass


class BaseBaseResource(Generic[StateT, InputT, OutputT]):
    MAGIC_UUID = 'a81054b2-bb57-4969-b3c5-308fee049e12'

    def __init__(self, logger, *args, **kwargs):
        self.__logger = logger if logger else logging.getLogger(self.full_name)
        self.__state_t = get_args(self.__orig_bases__[0])[0]
        self.__uuid: UUID | None = None
        self.__path: str = "$"
        self.__state: StateT = None
        if self.__state_t == StateT:
            self.__state_t = DefaultState
        self.__state: StateT = self.__state_t()
        self.__depends = set()
        self.__supports = set()
        self._applied = False
        self.__plan: 'BasePlan' = None

    def __post__init__(self):
        pass

    @property
    def system_tags(self):
        return {
            "pdep_uuid": str(self.uuid),
            "pdep_plan_uuid": str(self.plan.uuid) if self.plan else "None",
            "pdep_class": str(self.class_full_name),
            "pdep_plan_class": str(self.plan.class_full_name) if self.plan else "None",
            "pdep_root_plan_uuid": str(self.root_plan.uuid),
            "pdep_root_plan_class": str(self.root_plan.class_full_name)
        }

    @property
    def tags(self):
        the_tags = copy.deepcopy(self.inputs['tags'])
        the_tags.update(self.system_tags)
        return the_tags

    @property
    def logger(self):
        return self.__logger

    @property
    def class_full_name(self):
        return f"{self.__class__.__module__}.{self.__class__.__name__}"

    @property
    def full_name(self):
        return f"{self.__class__.__module__}.{self.__class__.__name__}({id(self)})"

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

    @property
    def root_plan(self):
        if self.__plan:
            return self.__plan.root_plan
        return self

    @plan.setter
    def plan(self, plan: 'BasePlan'):
        self.__plan = plan

    @property
    def inputs(self):
        return self.__inputs__

    @property
    def state(self) -> StateT:
        return self.__state

    @property
    def applied(self):
        return self._applied

    def _aws_tags_to_dict(self, aws_tags):
        tags = {}
        for pair in aws_tags:
            tags[pair['Key']] = pair['Value']
        return tags

    def _dict_to_aws_tags(self, d, additional={}):
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

    def reset_apply_state(self):
        self._applied = False

    def resolve_connector(self, path):
        raise Exception(f"Only plan have resource path and this is a single resource")

    def depends_on(self, res: 'BaseResource'):
        self.__depends.add(res)
        res.__supports.add(self)

    def resolve_dependencies(self):
        for connector in self.__connectors__:
            self.depends_on(connector.root_obj)

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

    def __create_state_dict(self, state, inputs, apply_uuid):
        json_inputs = {}
        for key, value in inputs.items():
            if dataclasses.is_dataclass(value):
                json_inputs[key] = {
                    'magic': self.MAGIC_UUID,
                    'class': f'{value.__class__.__module__}.{value.__class__.__name__}',
                    'value': value.to_dict()
                }
            else:
                json_inputs[key] = value

        return {
            'state': state.to_dict() if state else None,
            'inputs': json_inputs,
            'class': f"{self.__class__.__module__}.{self.__class__.__name__}",
            'path': self.path,
            'uuid': str(self.uuid),
            'plan': f"{self.__plan.__class__.__module__}.{self.__plan.__class__.__name__}" if self.plan else None,
            'plan_uuid': str(self.__plan.uuid) if self.plan else None,
            'apply_uuid': str(apply_uuid)
        }

    @log_func()
    def mark_destroy(self, resource_manager: ResourceManager, env_inputs, apply_uuid):
        if env_inputs is None:
            return
        state_dict = self.__create_state_dict(self.state, env_inputs, apply_uuid)
        resource_manager.mark_destroy(self.uuid, state_dict)

    def __scan_dataclasses(self, inputs):
        if inputs is None:
            return None
        new_inputs = {}
        for key, value in inputs.items():
            if type(value) == dict and 'magic' in value and value['magic'] == self.MAGIC_UUID:
                cls = load_class_from_str(value['class'])
                obj = cls.from_dict(value['value'])
                new_inputs[key] = obj
            else:
                new_inputs[key] = value
        return new_inputs

    def __read_state(self, resource_manager: ResourceManager, from_deleted=False):
        state_dict = resource_manager.get_state(self.uuid, from_deleted)
        state_obj = self.__state_t.from_dict(state_dict['state']) if state_dict and state_dict[
            'state'] else self.__state_t()
        inputs = state_dict['inputs'] if state_dict else None
        inputs = self.__scan_dataclasses(inputs)
        return inputs, state_obj

    @log_func()
    def apply(self, resource_manager: ResourceManager, provider, dry=False, apply_uuid=None):
        if self._applied:
            return

        first_apply = apply_uuid is None
        if not apply_uuid:
            apply_uuid = uuid.uuid4()
            self.logger.info(f"New Apply apply_uuid:{apply_uuid}")

        for res in self.__depends:
            res.apply(resource_manager, provider, dry, apply_uuid=apply_uuid)

        self.logger.debug(f"{self.full_name} apply dry:{dry}")
        inputs, self.__state = self.__read_state(resource_manager)
        self.resolve_dependent_values()
        self.do_apply(inputs, resource_manager, provider, apply_uuid=apply_uuid, dry=dry)
        state_dict = self.__create_state_dict(self.state, self.__inputs__, apply_uuid=apply_uuid)
        resource_manager.set_state(self.uuid, state_dict)

        self._applied = True
        if first_apply:
            self.logger.info(f"Apply Finished apply_uuid:{apply_uuid}")

    @log_func()
    def do_apply(self, inputs: Dict[str, Any], resource_manager, provider, apply_uuid, dry):
        pass

    @log_func()
    def destroy(self, resource_manager: ResourceManager, provider, dry=False, from_deleted=False, apply_uuid=None):
        if self._applied:
            return

        first_apply = apply_uuid is None
        if not apply_uuid:
            apply_uuid = uuid.uuid4()
            self.logger.info(f"New Destroy apply_uuid:{apply_uuid}")

        if not from_deleted:
            for res in self.__supports:
                if res != self.__plan:
                    res.destroy(resource_manager, provider, dry, apply_uuid=apply_uuid)
        state = self.__state
        inputs, self.__state = self.__read_state(resource_manager, from_deleted)
        self.resolve_dependent_values()
        self.do_destroy(inputs, resource_manager, provider, apply_uuid, dry=dry)
        resource_manager.delete_state(self.uuid, from_deleted)
        if from_deleted:
            self.__state = state
        self._applied = True
        if first_apply:
            self.logger.info(f"Destroy Finished")

    @log_func()
    def do_destroy(self, env_state: T, inputs: Dict[str, Any], resource_manager, provider, apply_uuid, dry):
        pass


class BaseResource(BaseBaseResource[StateT, InputT, OutputT]):
    def __init__(self, logger, input: InputT | Connector | None = None):
        super().__init__(logger)
        self.__output_t = get_args(self.__orig_bases__[0])[2]
        self.__input_t = get_args(self.__orig_bases__[0])[1]
        self._output = self.__output_t()
    @property
    def input(self) -> InputT:
        return self.input['intput']

    @property
    @output_property
    def output(self) -> OutputT:
        return self._output

    @output.setter
    def output(self, value: OutputT):
        self._output = value




class resource:
    def __init__(self):
        pass

    def __fill_defaults(self, kwargs):
        for key, default in self.__defaults.items():
            if key not in kwargs:
                kwargs[key] = default
        return kwargs

    def __call__(self, cls):
        org_init = cls.__init__
        self.__defaults = {}
        sig = inspect.signature(org_init)
        for k, v in sig.parameters.items():
            if k not in ['self', 'logger']:
                self.__defaults[k] = v.default

        def __new__init__(his_self, logger, *args, **kwargs):
            connectors = []
            his_self.__inputs__ = kwargs
            if len(args):
                raise Exception("No positional args are allowed in resource init ")
            for name, arg in kwargs.items():
                if type(arg) == Connector:
                    connectors.append(arg)
            his_self.__connectors__ = connectors
            his_self.__inputs__ = self.__fill_defaults(kwargs)
            org_init(his_self, logger, *args, **kwargs)
            his_self.__post__init__()

        assert issubclass(cls, BaseBaseResource)
        cls.__init__ = __new__init__
        return cls


def sub_uuid(uuid: UUID, name: str):
    md = md5()
    md.update(f"{uuid}.{name}".encode('utf-8'))
    return UUID(md.hexdigest())


class BasePlan(BaseBaseResource[StateT, InputT, OutputT]):
    def __init__(self, logger, uuid):
        super().__init__(logger)
        self.__res = DynamicDataContainer()
        self.uuid = uuid
        self.plan = None

    def __post__init__(self):
        for path, value in self.__res.items():
            if isinstance(value, BaseResource):
                value.uuid = sub_uuid(self.uuid, path)
                value.path = path
                value.plan = self

    @property
    def resources(self):
        return self.__res

    @log_func()
    def resolve_connector(self, path):
        return self.__res.from_path(path)

    @log_func()
    def reset_apply_state(self):
        super().reset_apply_state()
        for path, res in self.__res.items():
            res.reset_apply_state()

    @log_func()
    def resolve_dependencies(self):
        super().resolve_dependencies()
        for path, res in self.__res.items():
            res.resolve_dependencies()

    @log_func()
    def apply(self, resource_manager: ResourceManager, provider, dry=False, apply_uuid=None):
        if self._applied:
            return

        first_apply = apply_uuid is None
        if not apply_uuid:
            apply_uuid = uuid.uuid4()
            self.logger.info(f"New Apply apply_uuid:{apply_uuid}")

        self.resolve_dependencies()
        self.reset_apply_state()

        for path, value in self.__res.items():
            if isinstance(value, BaseResource):
                value.apply(resource_manager, provider, dry, apply_uuid)
        super().apply(resource_manager, provider, dry, apply_uuid=apply_uuid)
        if apply_uuid:
            self._clean_to_destroy(resource_manager, provider, dry, apply_uuid)

        self._applied = True
        if first_apply:
            self.logger.info(f"Apply Finished apply_uuid:{apply_uuid}")

    @log_func()
    def destroy(self, resource_manager: ResourceManager, provider, dry=False, apply_uuid=None):
        if self._applied:
            return

        first_apply = apply_uuid is None
        if not apply_uuid:
            apply_uuid = uuid.uuid4()
            self.logger.info(f"New Destroy apply_uuid:{apply_uuid}")

        self.resolve_dependencies()
        self.reset_apply_state()
        for path, res in self.__res.items():
            res.destroy(resource_manager, provider, dry, apply_uuid=apply_uuid)
        resource_manager.delete_state(self.uuid)
        self._applied = True
        if first_apply:
            self.logger.info(f"Destroy Finished apply_uuid:{apply_uuid}")

    @log_func()
    def _clean_to_destroy(self, resource_manager: ResourceManager, provider, dry, apply_uuid):
        to_destroy = resource_manager.get_to_destroy()
        for state in reversed(to_destroy):
            cls = load_class_from_str(state['class'])
            self.logger.info(f"Destroying class:{cls} uuid:{state['uuid']}")
            res = cls(self.logger, **state['inputs'])
            res.uuid = state['uuid']
            res.destroy(resource_manager, provider, dry, from_deleted=True, apply_uuid=apply_uuid)
            self.logger.info(f"Destroying class:{cls} uuid:{state['uuid']} - Done")
