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
from pdep.utils import DynamicDataContainer, dict_to_class, log_func, load_class_from_str, convert_something_values, \
    unused

zstr = Union[str, None, Any]


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
class FileResourceManager(ResourceManager):

    def __init__(self, path: str | Path, logger=None):
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
        unused(uuid)
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
    def __init__(self, logger=None):
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
    def root_objs(self):
        objs = [self.__obj]
        if isinstance(self.__obj, Connector):
            objs = self.__obj.root_objs
        return objs

    @property
    def value(self) -> Any:
        return self.get_value()

    def get_value(self) -> Any:
        self.resolve()
        return self.__value

    def resolve(self):
        def visitor(value):
            if isinstance(value, Connector):
                return value.value
            return value

        if not self.__resolved:
            self.__value = self.__func[0](self.__obj)
            if self.__attr:
                self.__value = getattr(self.__value, self.__attr)
            self.__value = convert_something_values(self.__value, visitor)
            self.__resolved = True

    def __getattr__(self, name):
        if name.startswith("_") or name in ['resolve', 'value', 'root_objs', 'get_value']:
            return self.__getattribute__(name)
        return Connector(self, Connector.get_value, name)


class CalcConnector(Connector):
    def __init__(self, *args, **kwargs):
        super().__init__(None, None)
        self.__args = args

        self.__func = [self.calc]
        if 'func' in kwargs:
            self.__func = [kwargs['func']]

        self.__kwargs = kwargs
        self.__root_objs = []
        self.__value = None
        self.__resolved = False
        for arg in self.__args:
            if isinstance(arg, Connector):
                self.__root_objs += arg.root_objs
        for key, arg in self.__kwargs.items():
            if isinstance(arg, Connector):
                self.__root_objs += arg.root_objs

    @property
    def root_objs(self):
        return self.__root_objs

    @property
    def value(self) -> Any:
        return self.get_value()

    def get_value(self) -> Any:
        self.resolve()
        return self.__value

    def resolve(self):
        def visitor(value):
            if isinstance(value, Connector):
                return value.value
            return value

        if not self.__resolved:
            args = []
            for arg in self.__args:
                if isinstance(arg, Connector):
                    value = convert_something_values(arg.value, visitor)
                    args.append(value)
                else:
                    args.append(arg)

            kwargs = {}
            for key, arg in self.__kwargs.items():
                if isinstance(arg, Connector):
                    value = convert_something_values(arg.value, visitor)
                    kwargs[key] = value
                else:
                    kwargs[key] = arg

            self.__value = self.__func[0](*args, **kwargs)
            self.__value = convert_something_values(self.__value, visitor)
            self.__resolved = True

    def calc(self, *args, **kwargs):
        pass

    def __getattr__(self, name):
        if name.startswith("_") or name in ['resolve', 'value', 'calc', 'root_objs', 'get_value']:
            return self.__getattribute__(name)
        return Connector(self, Connector.get_value, name)


def output_property(prop_func):
    @wraps(prop_func)
    def func(self):
        return Connector(self, prop_func)

    return func


def plan_output_property(prop_func):
    return prop_func


InputT = TypeVar('InputT')
OutputT = TypeVar('OutputT')


@dataclass_json
@dataclass
class DefaultState:
    pass


class BaseBaseResource(Generic[InputT, OutputT]):

    def __init__(self, input: InputT = None, logger=None):

        self.__input_t = get_args(self.__orig_bases__[0])[0]
        self.__output_t = get_args(self.__orig_bases__[0])[1]

        self.__logger = logger if logger else logging.getLogger(self.full_name)
        self._input: InputT = input
        self._output: OutputT = self.__output_t()

        self.__uuid: UUID | None = None
        self.__path: str = "$"
        self.__depends = set()
        self._supports = set()
        self._applied = False
        self.__plan: Union['BasePlan', None] = None

        self.__scan_input_for_dependencies()

    def __scan_input_for_dependencies(self):
        def visit(value):
            if isinstance(value, Connector):
                for obj in value.root_objs:
                    self.depends_on(obj)
            return value

        convert_something_values(self._input, visit)

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

    def _set_uuid(self, uuid: UUID):
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
    def input(self):
        return self._input

    @property
    @output_property
    def output(self):
        return self._output

    @property
    def applied(self):
        return self._applied

    def reset_apply_state(self):
        self._applied = False

    def depends_on(self, res: 'BaseResource'):
        self.__depends.add(res)
        res._supports.add(self)

    def resolve_dependent_values(self):
        def visitor(item):
            if isinstance(item, Connector):
                return item.value
            return item

        self._input = convert_something_values(self._input, visitor)

    def _create_state_dict(self, output, input, apply_uuid):
        return {
            'output': output.to_dict(),
            'input': input.to_dict() if input else None,
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
        state_dict = self._create_state_dict(self._output, env_inputs, apply_uuid)
        resource_manager.mark_destroy(self.uuid, state_dict)

    def _read_state(self, resource_manager: ResourceManager, from_deleted=False):
        input = None
        output = self.__output_t()

        state_dict = resource_manager.get_state(self.uuid, from_deleted)
        if state_dict:
            input = self.__input_t.from_dict(state_dict['input']) if state_dict['input'] else None
            output = self.__output_t.from_dict(state_dict['output'])

        return input, output

    @log_func()
    def apply(self, resource_manager: ResourceManager, provider, dry=False, check_dirft=True, apply_uuid=None):
        if self._applied:
            return

        first_apply = apply_uuid is None
        if not apply_uuid:
            apply_uuid = uuid.uuid4()
            self.logger.info(f"New Apply apply_uuid:{apply_uuid}")

        for res in self.__depends:
            res.apply(resource_manager, provider, dry, check_dirft, apply_uuid=apply_uuid)

        self.logger.debug(f"{self.full_name} apply dry:{dry}")
        input, self._output = self._read_state(resource_manager)
        self.resolve_dependent_values()
        self.do_apply(input, resource_manager, provider, dry, check_dirft, apply_uuid)
        state_dict = self._create_state_dict(self._output, self._input, apply_uuid=apply_uuid)
        resource_manager.set_state(self.uuid, state_dict)

        self._applied = True
        self.logger.info(f"Apply {self.full_name} Done, output:{self._output}")

        if first_apply:
            self.logger.info(f"Apply Finished apply_uuid:{apply_uuid}")

    @log_func()
    def do_apply(self, inputs: Dict[str, Any], resource_manager, provider, dry, check_drift, apply_uuid):
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
            for res in self._supports:
                if res != self.__plan:
                    res.destroy(resource_manager, provider, dry, apply_uuid=apply_uuid)
        org_output = self._output
        input, self._output = self._read_state(resource_manager, from_deleted)
        self.resolve_dependent_values()
        self.do_destroy(input, resource_manager, provider, apply_uuid, dry=dry)
        resource_manager.delete_state(self.uuid, from_deleted)
        if from_deleted:
            self._output = org_output
        self._applied = True
        if first_apply:
            self.logger.info(f"Destroy Finished")

    @log_func()
    def do_destroy(self, env_state: T, inputs: Dict[str, Any], resource_manager, provider, apply_uuid, dry):
        pass


class BaseResource(BaseBaseResource[InputT, OutputT]):
    pass


def sub_uuid(uuid: UUID, obj: Any, name: str):
    md = md5()
    md.update(f"{uuid}.{obj.__class__.__name__}.{name}".encode('utf-8'))
    return UUID(md.hexdigest())


class BasePlan(BaseBaseResource[InputT, OutputT]):
    def __init__(self, input: InputT, uuid=None, logger=None):
        super().__init__(input, logger)
        self.__res = DynamicDataContainer()
        self._set_uuid(uuid)
        self.plan = None
        self.do_init_resources()
        if uuid:
            self._propagate_info_sub_resources()

    def _propagate_info_sub_resources(self):
        for path, value in self.__res.items():
            if isinstance(value, BaseResource):
                value._set_uuid(sub_uuid(self.uuid, value, path))
                value.path = path
                value.plan = self
            if isinstance(value, BasePlan):
                value._propagate_info_sub_resources()

    def do_init_resources(self):
        pass

    @property
    @plan_output_property
    def output(self):
        return self._output

    @property
    def resources(self):
        return self.__res

    @log_func()
    def reset_apply_state(self):
        super().reset_apply_state()
        for path, res in self.__res.items():
            res.reset_apply_state()

    def _resolve_output_values(self):
        def visitor(item):
            if isinstance(item, Connector):
                return item.value
            return item

        self._output = convert_something_values(self._output, visitor)


    @log_func()
    def apply(self, resource_manager: ResourceManager, provider, dry=False, check_drift=True, apply_uuid=None):
        if self._applied:
            return

        first_apply = apply_uuid is None
        if not apply_uuid:
            apply_uuid = uuid.uuid4()
            self.logger.info(f"New Apply apply_uuid:{apply_uuid}")

        self.logger.debug(f"{self.full_name} apply dry:{dry}")

        self.reset_apply_state()
        input, _ = self._read_state(resource_manager)
        self.resolve_dependent_values()

        for path, value in self.__res.items():
            if isinstance(value, BaseResource):
                value.apply(resource_manager, provider, dry, check_drift, apply_uuid)

        self._resolve_output_values()
        state_dict = self._create_state_dict(self._output, self._input, apply_uuid=apply_uuid)
        resource_manager.set_state(self.uuid, state_dict)

        if apply_uuid:
            self._clean_to_destroy(resource_manager, provider, dry, apply_uuid)

        self._applied = True
        if first_apply:
            self.logger.info(f"Apply Finished plan:'{self.full_name}' output:{self.output} apply_uuid:{apply_uuid}")

    @log_func()
    def destroy(self, resource_manager: ResourceManager, provider, dry=False, apply_uuid=None):
        if self._applied:
            return

        first_apply = apply_uuid is None
        if not apply_uuid:
            apply_uuid = uuid.uuid4()
            self.logger.info(f"New Destroy apply_uuid:{apply_uuid}")

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
            res = cls(state['input'])
            res._set_uuid(state['uuid'])
            res.destroy(resource_manager, provider, dry, from_deleted=True, apply_uuid=apply_uuid)
            self.logger.info(f"Destroying class:{cls} uuid:{state['uuid']} - Done")


class SimplifiedResource(BaseResource[InputT, OutputT]):

    @property
    def create_before_destroy(self):
        return True
    @log_func()
    def do_apply(self, env_inputs: InputT, resource_manager, provider, dry, check_drift, apply_uuid):
        if env_inputs is None:
            ret = self.create(provider, apply_uuid, dry)
            if ret is False:
                self.do_destroy(self.input, resource_manager, provider, apply_uuid, dry)
                self.create(provider, apply_uuid, dry)
            return
        if env_inputs != self.input or (check_drift and self.is_drifted(provider, dry)):
            if not self.update(env_inputs, resource_manager, provider, apply_uuid, dry):
                if self.create_before_destroy:
                    self.mark_destroy(resource_manager, env_inputs, apply_uuid)
                else:
                    self.do_destroy(env_inputs, resource_manager, provider, apply_uuid, dry)
                ret = self.create(provider, apply_uuid, dry)
                if ret is False:
                    self.do_destroy(self.input, resource_manager, provider, apply_uuid, dry)
                    self.create(provider, apply_uuid, dry)

        else:
            self.logger.info("nothing to do")

    @log_func()
    def update(self, env_inputs: InputT, resource_manager, provider, apply_uuid, dry):
        return False

    @log_func()
    def do_destroy(self, env_inputs: InputT, resource_manager, provider, apply_uuid, dry):
        pass

    @log_func()
    def create(self, provider, apply_uuid, dry):
        pass

    @log_func()
    def is_drifted(self, provider, dry):
        pass


class BaseBackbone(BasePlan[InputT, OutputT]):
    pass
