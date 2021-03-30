""" Configuration module"""

import os
import platform
import yaml

from knack.util import CLIError
from schema import Schema, And, Or, Use, Optional, SchemaError, SchemaMissingKeyError, SchemaWrongKeyError
from jinja2 import Environment, BaseLoader, StrictUndefined, contextfunction, Template
from jinja2.exceptions import UndefinedError, TemplateSyntaxError
from azext_cdf.version import version
from azext_cdf.utils import dir_create, dir_remove, is_part_of, real_dirname, random_string
from azext_cdf.state import State

FIRST_PHASE = 1
SECOND_PHASE = 2
# Runtime vars
RUNTIME_ENV_KEY = "env"
RUNTIME_RESULT = "result"
RUNTIME_RESULT_OUTPUTS = "outputs"
RUNTIME_RESULT_RESOURCES = "resources"
RUNTIME_HOOKS = "hooks"
RUNTIME_RUN_ONCE_KEY = "once"
RUNTIME_RUN_ONCE = "_ONCE_ONCE_"
# Config
CONFIG_NAME = "name"
CONFIG_RG = "resource_group"
CONFIG_RG_MANAGED = "manage_resource_group"
CONFIG_LOCATION = "location"
CONFIG_SUPPORTED_PROVISIONERS = "bicep"  # ('bicep', 'terraform')
CONFIG_PROVISIONER = "provisioner"
CONFIG_SCOPE = "scope"
CONFIG_TMP = "temp_dir"
CONFIG_UP = "up"
CONFIG_VARS = "vars"
CONFIG_PARAMS = "params"
CONFIG_STATE_FILE = "state"
CONFIG_HOOKS = "hooks"
CONFIG_DEPLOYMENT_COMPLETE = "complete_deployment"
CONFIG_STATE_FILE_DEFAULT = "{{ cdf.tmp_dir }}/state.json"
LIFECYCLE_PRE_UP, LIFECYCLE_POST_UP, LIFECYCLE_PRE_DOWN, LIFECYCLE_POST_DOWN = "pre-up", "post-up", "pre-down", "post-down"
LIFECYCLE_PRE_TEST, LIFECYCLE_POST_TEST, LIFECYCLE_ALL = "pre-test", "post-test", ""
CONFIG_SUPPORTED_LIFECYCLE = (LIFECYCLE_PRE_UP, LIFECYCLE_POST_UP, LIFECYCLE_PRE_DOWN, LIFECYCLE_POST_DOWN, LIFECYCLE_PRE_TEST, LIFECYCLE_POST_TEST, LIFECYCLE_ALL)
CONFIG_SUPPORTED_PLATFORM = ("linux", "windows", "darwin", "")
CONFIG_SUPPORTED_OPS_TYPES = ("az", "cmd", "print", "call", "script")  # ('bicep', 'arm',  'api', 'rest', "terraform")
CONFIG_SUPPORTED_OPS_MODE = ('wait', "interactive")

def include_file(name):
    try:
        with open(name) as in_file:
            return in_file.read()
    except Exception as error:
        raise CLIError(f"include_file filter argument '{name}' error. {str(error)}") from error


@contextfunction
def template_file(ctx, name):
    try:
        data = include_file(name)
        return Template(data, undefined=StrictUndefined).render(ctx)

    except Exception as error:
        raise CLIError(f"template_file filter argument '{name}' error. {str(error)}") from error
    return data


class ConfigParser:
    def __init__(self, config, remove_tmp=False):
        self.data = {}
        self._config = config
        self.first_phase_vars = {}
        self.second_phase_vars = {}
        self._remove_tmp = remove_tmp
        # https://github.com/keleshev/schema
        hooks_schema = {
            str: {
                "ops": [
                    {
                        Optional("name"): str,
                        Optional("description"): str,
                        Optional("type", default="az"): And(str, Use(str.lower), lambda s: s in CONFIG_SUPPORTED_OPS_TYPES),
                        Optional("platform", default=""): Or(And(str, Use(str.lower), (And(list))), lambda s: is_part_of(s, CONFIG_SUPPORTED_PLATFORM)),
                        Optional("mode", default='wait'): And(str, Use(str.lower), lambda s: s in CONFIG_SUPPORTED_OPS_MODE),
                        "args": Or(str, list),
                    }
                ],
                Optional("lifecycle", default=""): Or(And(str, Use(str.lower), (And(list))), lambda s: is_part_of(s, CONFIG_SUPPORTED_LIFECYCLE)),
                Optional("description", default=""): str,
                Optional("run_if", default="true"): str,
            }
        }
        self._schema_def = {
            CONFIG_NAME: And(str, len),
            CONFIG_RG: And(str, len),
            CONFIG_LOCATION: And(str, len),
            Optional(CONFIG_SCOPE, default="resource_group"): And(str, len),
            Optional(CONFIG_RG_MANAGED, default=True): bool,
            Optional(CONFIG_PROVISIONER, default="bicep"): And(str, Use(str.lower), lambda s: s in CONFIG_SUPPORTED_PROVISIONERS),
            Optional(CONFIG_DEPLOYMENT_COMPLETE, default=False): bool,
            Optional(CONFIG_UP, default=None): And(str, len),
            Optional(CONFIG_TMP, default="{{cdf.config_dir}}/.cdf_tmp"): And(str, len),
            # Optional('vars_file', default=[]): Or(str,list),
            Optional(CONFIG_VARS, default={}): dict,
            Optional(CONFIG_PARAMS, default={}): dict,
            Optional(CONFIG_HOOKS, default={}): hooks_schema,
            Optional(CONFIG_STATE_FILE, default=CONFIG_STATE_FILE_DEFAULT): str,
        }
        self._load_validate()
        self.jinja_env = Environment(loader=BaseLoader, undefined=StrictUndefined)
        self.jinja_env.globals["include_file"] = include_file
        self.jinja_env.globals["template_file"] = template_file
        self.jinja_env.globals["random_string"] = random_string
        self._quick_delayed_vars = []
        self._delayed_vars = []
        # First phase
        self._setup_first_phase_interpolation()
        # Second phase
        self._setup_second_phase_variables()
        self._update_result(self.state.result_up)
        self.updateHooksResult(self.state.result_hooks)

    def _load_validate(self):
        self.data = self._read_config(self._config)
        try:
            schema = Schema(self._schema_def)
            self.data = schema.validate(self.data)
            self._validate_hooks()
        except SchemaWrongKeyError as error:
            raise CLIError(f"config schema error 'SchemaWrongKeyError' in '{self._config}' an unexpected key is detected: {str(error)}") from error
        except SchemaMissingKeyError as error:
            raise CLIError(f"config  schema error 'SchemaMissingKeyError' in '{self._config}' a mandatory key is not found: {str(error)}") from error
        except SchemaError as error:
            raise CLIError(f"config schema error 'SchemaError' in '{self._config}' a general schema violation: {str(error)}") from error

    def _validate_hooks(self):
        for hook_name, hook_value in self.data[CONFIG_HOOKS].items():
            if hook_name[0] == "_":
                raise CLIError(f"Hook names '{hook_name}' can't start with '_'")
            for operation in hook_value.get("ops"):
                op_name = operation.get("name", " ")
                if op_name[0] == "_":
                    raise CLIError(f"op names '{op_name}' can't start with '_'")

    @staticmethod
    def _read_config(filepath):
        try:
            with open(filepath) as f:
                return yaml.load(f, Loader=yaml.FullLoader)
        except yaml.parser.ParserError as error:
            raise CLIError(f"Config file '{filepath}' yaml parser error:': {str(error)}") from error
        except FileNotFoundError as error:
            raise CLIError(f"Config file '{filepath}' file not found:': {str(error)}") from error

    def _setup_first_phase_interpolation(self):
        self.first_phase_vars = {
            "cdf": {
                "version": version,
                "config_dir": real_dirname(self._config),
                "platform": platform.system().lower(),
            },
            RUNTIME_ENV_KEY: os.environ,
            CONFIG_VARS: {},
            CONFIG_PARAMS: {},
            RUNTIME_RUN_ONCE_KEY: RUNTIME_RUN_ONCE,
        }
        if CONFIG_VARS in self.data:
            self._lazy_variable_resolve(allow_undefined=True)
            # self._lazy_variable_resolve(allow_undefined=False)
        self.data[CONFIG_TMP] = self.interpolate(FIRST_PHASE, self.data[CONFIG_TMP], f"key {CONFIG_TMP}")
        self.first_phase_vars["cdf"]["tmp_dir"] = self.data[CONFIG_TMP]
        # remove and create tmp dir incase we will download some stuff for templates
        if self._remove_tmp:
            dir_remove(self.data[CONFIG_TMP])
        dir_create(self.data[CONFIG_TMP])
        self.data[CONFIG_STATE_FILE] = self.interpolate(FIRST_PHASE, self.data[CONFIG_STATE_FILE], f"key {CONFIG_STATE_FILE}")
        self.data[CONFIG_NAME] = self.interpolate(FIRST_PHASE, self.data[CONFIG_NAME], f"key {CONFIG_NAME}")
        self.state = State(self.data[CONFIG_STATE_FILE], self.data[CONFIG_NAME], self.hooks_ops)  # initialize state
        self.jinja_env.globals["store"] = self.state.store_get
        for k in self._quick_delayed_vars:
            self.first_phase_vars[CONFIG_VARS][k] = self.interpolate(SECOND_PHASE, self.data[CONFIG_VARS][k], f"variables in config in quick delayed interpolate '{k}'")
        self.data[CONFIG_RG] = self.interpolate(FIRST_PHASE, self.data[CONFIG_RG], f"key {CONFIG_RG}")
        self.first_phase_vars["cdf"]["resource_group"] = self.data[CONFIG_RG]
        self.data[CONFIG_LOCATION] = self.interpolate(FIRST_PHASE, self.data[CONFIG_LOCATION], f"key {CONFIG_LOCATION}")
        self.first_phase_vars["cdf"]["location"] = self.data[CONFIG_RG]
        self.data[CONFIG_UP] = self.interpolate(FIRST_PHASE, self.data[CONFIG_UP], f"key {CONFIG_UP}")
        self.state.check_resource_group(self.data[CONFIG_RG])  # check resource group with state

    def _setup_second_phase_variables(self):
        self.second_phase_vars = {
            RUNTIME_RESULT: {
                RUNTIME_RESULT_OUTPUTS: {},
                RUNTIME_RESULT_RESOURCES: {},
            },
            RUNTIME_HOOKS: self.hooks_ops,
        }

    def _lazy_variable_resolve(self, allow_undefined=False):
        if CONFIG_VARS in self.data:
            for key, value in self.data[CONFIG_VARS].items():
                context = f"variables in config '{key}':'{value}'"
                try:
                    self.first_phase_vars[CONFIG_VARS][key] = self.interpolate(FIRST_PHASE, value, context, raw_undefined_error=allow_undefined)
                except UndefinedError as error:
                    if "result" in str(error):
                        self._delayed_vars.append(key)
                    elif "store" in str(error):
                        self._quick_delayed_vars.append(key)
                    else:
                        real_error = True
                        for delayed_var in self._quick_delayed_vars:
                            if any(delayed_var in err for err in error.args):
                                self._quick_delayed_vars.append(key)
                                real_error = False
                                continue
                        if real_error:
                            raise CLIError(f"config interpolation error. {context}, undefined lazy variable: {str(error)}") from error

    def _interpolate_object(self, phase, template, variables=None):
        if isinstance(template, str):
            return self._interpolate_string(template, variables)
        elif isinstance(template, list):
            interpolated_list = []
            for template_item in template:
                interpolated_list.append(self._interpolate_object(phase, template_item, variables))
            return interpolated_list
        elif isinstance(template, dict):
            interpolated_dict = {}
            for template_key, template_value in template.items():
                interpolated_dict.update({template_key: self._interpolate_object(phase, template_value, variables)})
            return interpolated_dict
        else:
            raise CLIError(f"unsupported type in interpolate f{type(template)}, '{template}'")

    def _interpolate_string(self, string, variables):
        template_string = self.jinja_env.from_string(string)
        return template_string.render(variables)

    def updateHooksResult(self, hooks_output):
        self.second_phase_vars[RUNTIME_HOOKS] = hooks_output

    def _update_result(self, result):
        self.second_phase_vars[RUNTIME_RESULT] = result

    def delayed_variable_interpolite(self):
        for k in self._delayed_vars:
            self.first_phase_vars[CONFIG_VARS][k] = self.interpolate(SECOND_PHASE, self.data[CONFIG_VARS][k], f"variables in config in delayed interpolate '{k}'")

    def delayed_up_Interpolite(self):
        ''' '''
        self.delayed_variable_interpolite()
        if CONFIG_PARAMS in self.data:
            for v, k in self.data[CONFIG_PARAMS].items():
                self.data[CONFIG_PARAMS][v] = self.interpolate(FIRST_PHASE, k, f"variables in config in delayed interpolate '{k}'")

    def interpolate(self, phase, template, context=None, extra_vars=None, raw_undefined_error=False):
        if template is None:
            return None
        if phase == FIRST_PHASE:
            variables = self.first_phase_vars
        elif phase == SECOND_PHASE:
            variables = {**self.second_phase_vars, **self.first_phase_vars}

        if extra_vars:
            variables = {**variables, **extra_vars}

        if context:
            error_context = f"in phase: '{phase}'', Context: '{context}'"
        else:
            error_context = f"in phase '{phase}'"

        try:
            return self._interpolate_object(phase, template, variables)
        # except TypeError as e:
        #     raise CLIError(f"config interpolation error. {error_context}, undefined variable : {str(e)}")
        except UndefinedError as error:
            if raw_undefined_error:
                raise
            raise CLIError(f"config interpolation error. {error_context}, undefined variable: {str(error)}") from error
        except TemplateSyntaxError as error:
            raise CLIError(f"config interpolation error. {error_context}, template syntax: {str(error)}") from error

    @property
    def name(self):
        return self.data[CONFIG_NAME]

    @property
    def resource_group_name(self):
        return self.data[CONFIG_RG]

    @property
    def managed_resource(self):
        return self.data[CONFIG_RG_MANAGED]

    @property
    def location(self):
        return self.data[CONFIG_LOCATION]

    @property
    def tmp_dir(self):
        return self.data[CONFIG_TMP]

    @property
    def up_file(self):
        return self.data[CONFIG_UP]

    @property
    def provisioner(self):
        return self.data["provisioner"]

    @property
    def config(self):
        return self.data

    @property
    def hook_names(self):
        hooks = []
        # if self.data[CONFIG_HOOKS]:
        for k, _ in self.data[CONFIG_HOOKS].items():
            hooks.append(k)
        return hooks

    @property
    def hook_table(self):
        output_hooks = []
        # if self.data[CONFIG_HOOKS]:
        for k, v in self.data[CONFIG_HOOKS].items():
            lifecycle = v["lifecycle"]
            if isinstance(lifecycle, str):
                lifecycle = [lifecycle]
            output_hooks.append({"name": k, "description": v["description"], "lifecycle": lifecycle})
        return output_hooks

    @property
    def hooks_ops(self):
        output_hooks = {}
        if not self.data[CONFIG_HOOKS]:
            return output_hooks

        for hook_k, hook_v in self.data[CONFIG_HOOKS].items():
            output_hooks[hook_k] = {}
            for op in hook_v["ops"]:
                op_name = op.get("name", False)
                if op_name:
                    if op_name in output_hooks[hook_k]:
                        raise CLIError(f"config schema error duplicate op name '{op_name}'  in hook '{hook_k}")
                    output_hooks[hook_k][op_name] = {}
        return output_hooks

    @property
    def state_file(self):
        return self.data[CONFIG_STATE_FILE]

    @property
    def platform(self):
        return self.first_phase_vars["cdf"]["platform"]

    @property
    def config_dir(self):
        return self.first_phase_vars["cdf"]["config_dir"]

    @property
    def deployment_mode(self):
        return self.data[CONFIG_DEPLOYMENT_COMPLETE]
