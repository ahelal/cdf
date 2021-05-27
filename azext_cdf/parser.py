""" Configuration module"""

import os
import platform
import yaml
import schema
from schema import Schema, And, Or, Use, Optional, SchemaError, SchemaMissingKeyError, SchemaWrongKeyError

from knack.util import CLIError
from jinja2 import Environment, BaseLoader, StrictUndefined, pass_context, Template
from jinja2.exceptions import UndefinedError, TemplateSyntaxError, TemplateRuntimeError
from azext_cdf.version import VERSION
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
CONFIG_SUPPORTED_PROVISIONERS = ('bicep', 'arm', 'terraform')
CONFIG_PROVISIONER = "provisioner"
CONFIG_SCOPE = "scope"
CONFIG_TMP = "tmp_dir"
CONFIG_UP = "up"
CONFIG_VARS = "vars"
CONFIG_PARAMS = "params"
CONFIG_STATE_FILENAME = "state_filename"
CONFIG_STATE_FILEPATH = "state_Path"
CONFIG_HOOKS = "hooks"
CONFIG_TESTS = "tests"
CONFIG_CDF = "cdf"
CONFIG_FILE = "file"
CONFIG_DEPLOYMENT_COMPLETE = "complete_deployment"
CONFIG_STATE_FILEPATH_DEFAULT = "file://{{ cdf.tmp_dir }}"
CONFIG_STATE_FILENAME_DEFAULT = "state.json"
LIFECYCLE_PRE_UP, LIFECYCLE_POST_UP, LIFECYCLE_PRE_DOWN, LIFECYCLE_POST_DOWN = "pre-up", "post-up", "pre-down", "post-down"
LIFECYCLE_PRE_TEST, LIFECYCLE_POST_TEST, LIFECYCLE_ALL = "pre-test", "post-test", ""
CONFIG_SUPPORTED_LIFECYCLE = (LIFECYCLE_PRE_UP, LIFECYCLE_POST_UP, LIFECYCLE_PRE_DOWN, LIFECYCLE_POST_DOWN, LIFECYCLE_PRE_TEST, LIFECYCLE_POST_TEST, LIFECYCLE_ALL)
CONFIG_SUPPORTED_PLATFORM = ("linux", "windows", "darwin", "")
CONFIG_SUPPORTED_OPS_TYPES = ("az", "cmd", "print", "call", "script")
CONFIG_SUPPORTED_OPS_MODE = ('wait', "interactive")
CONFIG_DESCRIPTION = "description"


def _include_file(name):
    try:
        with open(name) as in_file:
            return in_file.read()
    except Exception as error:
        raise CLIError(f"include_file filter argument '{name}' error. {str(error)}") from error


@pass_context
def _template_file(ctx, name):
    try:
        data = _include_file(name)
        return Template(data, undefined=StrictUndefined).render(ctx)

    except Exception as error:
        raise CLIError(f"template_file filter argument '{name}' error. {str(error)}") from error
    return data


def _list_or_tuple_of(sub_schema):
    return schema.Or((sub_schema,), [sub_schema])


class ConfigParser:
    '''  CDF yaml config parser class '''

    def __init__(self, cdf_yml_filepath, remove_tmp=False, override_state=None, test=None):
        self.data = {}
        self.state = {}
        self.first_phase_vars = {}
        self.second_phase_vars = {}
        self._delayed_vars = []
        self.jinja_env = None
        self.test = test
        # https://github.com/keleshev/schema
        hooks_schema = {
            str: {
                "ops": [
                    {
                        Optional(CONFIG_NAME): str,
                        Optional(CONFIG_DESCRIPTION, default=""): str,
                        Optional("type", default="az"): And(str, Use(str.lower), lambda s: s in CONFIG_SUPPORTED_OPS_TYPES),
                        Optional("platform", default=""): Or(And(str, Use(str.lower), (And(list))), lambda s: is_part_of(s, CONFIG_SUPPORTED_PLATFORM)),
                        Optional("mode", default='wait'): And(str, Use(str.lower), lambda s: s in CONFIG_SUPPORTED_OPS_MODE),
                        Optional("cwd"): str,
                        "args": Or(str, list),
                    }
                ],
                Optional("lifecycle", default=""): Or(And(str, Use(str.lower), (And(list))), lambda s: is_part_of(s, CONFIG_SUPPORTED_LIFECYCLE)),
                Optional(CONFIG_DESCRIPTION, default=""): str,
                Optional("run_if", default="true"): str,
            }
        }
        expect_schema = {
            Optional("fail", default=False): bool,
            Optional("assert"): Or(str, list),
            Optional("cmd"): Or(str, list),
            Optional("args"): Or(str, list),
        }
        test_schema = {
            str: {
                Optional(CONFIG_FILE): str,
                Optional(CONFIG_NAME): And(str, len),
                Optional(CONFIG_DESCRIPTION, default=""): str,
                Optional(CONFIG_RG): And(str, len),
                Optional(CONFIG_LOCATION): And(str, len),
                Optional(CONFIG_RG_MANAGED, default=True): bool,
                Optional(CONFIG_DEPLOYMENT_COMPLETE, default=False): bool,
                Optional(CONFIG_UP): And(str, len),
                # Optional('vars_file', default=[]): Or(str,list),
                Optional(CONFIG_VARS): dict,
                Optional(CONFIG_PARAMS): dict,
                Optional("expect"): {
                    Optional(Or("up", "down")): expect_schema,
                    Optional("hooks"): _list_or_tuple_of({str: expect_schema}),
                },
            }
        }
        self.schema_def = {
            CONFIG_NAME: And(str, len),
            CONFIG_RG: And(str, len),
            CONFIG_LOCATION: And(str, len),
            Optional(CONFIG_SCOPE, default="resource_group"): And(str, len),
            Optional(CONFIG_RG_MANAGED, default=True): bool,
            Optional(CONFIG_PROVISIONER, default="bicep"): And(str, Use(str.lower), lambda s: s in CONFIG_SUPPORTED_PROVISIONERS),
            Optional(CONFIG_DEPLOYMENT_COMPLETE, default=False): bool,
            Optional(CONFIG_UP, default=""): str,
            Optional(CONFIG_TMP, default="{{cdf.config_dir}}/.cdf_tmp"): And(str, len),
            # Optional('vars_file', default=[]): Or(str,list),
            Optional(CONFIG_VARS, default={}): dict,
            Optional(CONFIG_PARAMS, default={}): dict,
            Optional(CONFIG_HOOKS, default={}): hooks_schema,
            Optional(CONFIG_TESTS, default={}): test_schema,
            Optional(CONFIG_STATE_FILEPATH, default=CONFIG_STATE_FILEPATH_DEFAULT): str,
            Optional(CONFIG_STATE_FILENAME, default=CONFIG_STATE_FILENAME_DEFAULT): str,
        }
        self.data = self._read_config(cdf_yml_filepath)
        self._validate_conf(cdf_yml_filepath)
        self._setup_jinja2()
        self._setup_pre_phase_interpolation(cdf_yml_filepath)  # pre phase
        self._setup_test()
        self._setup_first_phase_interpolation(override_state, remove_tmp)  # First phase
        self._setup_second_phase_variables()  # Second phase
        self.update_hooks_result(self.state.result_hooks)

    def _validate_conf(self, cdf_yml_filepath):
        try:
            schema_obj = Schema(self.schema_def)
            self.data = schema_obj.validate(self.data)
            self._extra_validate()
        except SchemaWrongKeyError as error:
            raise CLIError(f"config schema error 'SchemaWrongKeyError' in '{cdf_yml_filepath}' an unexpected key is detected: {str(error)}") from error
        except SchemaMissingKeyError as error:
            raise CLIError(f"config  schema error 'SchemaMissingKeyError' in '{cdf_yml_filepath}' a mandatory key is not found: {str(error)}") from error
        except SchemaError as error:
            raise CLIError(f"config schema error 'SchemaError' in '{cdf_yml_filepath}' a general schema violation: {str(error)}") from error

    def _extra_validate(self):
        ''' validation not covered by schema '''
        hooks = []
        for hook_name, hook_value in self.hooks_dict:
            hooks.append(hook_name)
            if hook_name[0] == "_":
                raise CLIError(f"Hook names '{hook_name}' can't start with '_'")
            for operation in hook_value.get("ops"):
                op_name = operation.get(CONFIG_NAME, " ")
                if op_name[0] == "_":
                    raise CLIError(f"op names '{op_name}' can't start with '_'")
                if operation.get("type") == "call" and operation.get("args") not in self.hook_names:
                    raise CLIError(f"'{op_name}' can't call an undefined hook {operation.get('args')}")

        # TODO Refactor very messy
        for test in self.data.get(CONFIG_TESTS, {}):
            for hooks_ops in self.data[CONFIG_TESTS][test].get("expect", {}).get("hooks", []):
                for hook in hooks_ops:
                    if hook not in hooks:
                        raise CLIError(f"unknown hook name'{hook}' in expect test '{test}'")

    @staticmethod
    def _read_config(filepath):
        try:
            with open(filepath) as file_in:
                return yaml.load(file_in, Loader=yaml.FullLoader)
        except yaml.parser.ParserError as error:
            raise CLIError(f"Config file '{filepath}' yaml parser error:': {str(error)}") from error
        except FileNotFoundError as error:
            raise CLIError(f"Config file '{filepath}' file not found:': {str(error)}") from error

    def _setup_jinja2(self):
        self.jinja_env = Environment(loader=BaseLoader, undefined=StrictUndefined)
        self.jinja_env.globals["include_file"] = _include_file
        self.jinja_env.globals["template_file"] = _template_file
        self.jinja_env.globals["random_string"] = random_string

    def _setup_test(self):
        if not self.test:
            return
        self.data[CONFIG_STATE_FILENAME] = f"{self.test}_test_state.json"  # override default state file
        if self.data[CONFIG_TESTS][self.test].get(CONFIG_FILE, False):  # load test from another dir
            self.data[CONFIG_TESTS][self.test][CONFIG_FILE] = self.interpolate(FIRST_PHASE, self.data[CONFIG_TESTS][self.test][CONFIG_FILE], f"test {self.test} key {CONFIG_FILE}")
            test_data = self._read_config(self.data[CONFIG_TESTS][self.test][CONFIG_FILE])
            self.data[CONFIG_TESTS][self.test] = {**self.data[CONFIG_TESTS][self.test], **test_data}
            self._validate_conf(self.data[CONFIG_TESTS][self.test][CONFIG_FILE])  # revalidate after loading data

        self.data[CONFIG_NAME] = self.data[CONFIG_TESTS][self.test].get(CONFIG_NAME, f"{self.data[CONFIG_NAME]}_{self.test}_test")
        self.data[CONFIG_TESTS][self.test][CONFIG_DESCRIPTION] = self.data[CONFIG_TESTS][self.test].get(CONFIG_DESCRIPTION, f"{self.data[CONFIG_NAME]} {self.test} test")
        self.data[CONFIG_LOCATION] = self.data[CONFIG_TESTS][self.test].get(CONFIG_LOCATION, self.data[CONFIG_LOCATION])
        self.data[CONFIG_RG_MANAGED] = self.data[CONFIG_TESTS][self.test].get(CONFIG_RG_MANAGED, self.data[CONFIG_RG_MANAGED])
        self.data[CONFIG_UP] = self.data[CONFIG_TESTS][self.test].get(CONFIG_UP, self.data[CONFIG_UP])
        self.data[CONFIG_VARS] = {**self.data[CONFIG_VARS], **self.data[CONFIG_TESTS][self.test].get(CONFIG_VARS, {})}
        self.data[CONFIG_PARAMS] = {**self.data[CONFIG_PARAMS], **self.data[CONFIG_TESTS][self.test].get(CONFIG_PARAMS, {})}

        if self.data[CONFIG_TESTS][self.test].get(CONFIG_RG, None):
            self.data[CONFIG_RG] = self.data[CONFIG_TESTS][self.test][CONFIG_RG]
        elif self.data[CONFIG_RG_MANAGED]:
            self.data[CONFIG_RG] = f"{self.data[CONFIG_RG]}_{self.test}_test"
        # Don't do anything use cdf self.data[CONFIG_RG]

    def _setup_pre_phase_interpolation(self, cdf_yml_filepath):
        self.first_phase_vars = {
            CONFIG_CDF: {
                "version": VERSION,
                "config_dir": real_dirname(cdf_yml_filepath),
                "platform": platform.system().lower(),
            },
            RUNTIME_ENV_KEY: os.environ,
            CONFIG_VARS: {},
            CONFIG_PARAMS: {},
            RUNTIME_RUN_ONCE_KEY: RUNTIME_RUN_ONCE,
        }

    def _setup_first_phase_interpolation(self, override_state=None, remove_tmp=False):
        ''' first phase interpolation '''

        self.first_phase_vars[CONFIG_CDF][CONFIG_TMP] = self.interpolate(FIRST_PHASE, self.data[CONFIG_TMP], context=f"key {CONFIG_TMP}")
        if remove_tmp:  # remove and create tmp dir incase we will download some stuff for templates
            dir_remove(self.tmp_dir)
        dir_create(self.tmp_dir)
        if override_state:
            full_path_state_file = override_state
        else:
            self.data[CONFIG_STATE_FILENAME] = self.interpolate(FIRST_PHASE, self.data[CONFIG_STATE_FILENAME], context=f"key {CONFIG_STATE_FILENAME}")
            self.data[CONFIG_STATE_FILEPATH] = self.interpolate(FIRST_PHASE, self.data[CONFIG_STATE_FILEPATH], context=f"key {CONFIG_STATE_FILEPATH}")
            full_path_state_file = os.path.join(self.data[CONFIG_STATE_FILEPATH], self.data[CONFIG_STATE_FILENAME])

        self.state = State(full_path_state_file)  # initialize state
        self.jinja_env.globals["store"] = self.state.store_get  # setup store functions in jinja2

        self.first_phase_vars[CONFIG_CDF][CONFIG_NAME] = self.interpolate(FIRST_PHASE, self.data[CONFIG_NAME], f"key {CONFIG_NAME}")
        if CONFIG_VARS in self.data:
            # lazy variable resolve
            for key, value in self.data[CONFIG_VARS].items():
                try:
                    self.first_phase_vars[CONFIG_VARS][key] = self.interpolate(FIRST_PHASE, value, f"variables in config '{key}':'{value}'", raw_undefined_error=True)
                except UndefinedError as error:
                    if "result" in str(error):
                        self._delayed_vars.append(key)
                    else:
                        raise CLIError() from error
        self.first_phase_vars[CONFIG_CDF][CONFIG_RG] = self.interpolate(FIRST_PHASE, self.data[CONFIG_RG], f"key {CONFIG_RG}")
        self.first_phase_vars[CONFIG_CDF][CONFIG_LOCATION] = self.interpolate(FIRST_PHASE, self.data[CONFIG_LOCATION], f"key {CONFIG_LOCATION}")
        self.data[CONFIG_UP] = self.interpolate(FIRST_PHASE, self.data[CONFIG_UP], f"key {CONFIG_UP}")
        # Setup state after interpolation
        self.state.setup(deployment_name=self.name, resource_group=self.resource_group_name, config_hooks=self._hooks_ops())

    def _setup_second_phase_variables(self):
        self.second_phase_vars = {
            RUNTIME_RESULT: {
                RUNTIME_RESULT_OUTPUTS: {},
                RUNTIME_RESULT_RESOURCES: {},
            },
            RUNTIME_HOOKS: self._hooks_ops(),
        }
        self.second_phase_vars[RUNTIME_RESULT] = self.state.result_up  # update results from state

    def _interpolate_object(self, phase, template, variables=None):
        if isinstance(template, str):
            return self._interpolate_string(template, variables)
        if isinstance(template, list):
            interpolated_list = []
            for template_item in template:
                interpolated_list.append(self._interpolate_object(phase, template_item, variables))
            return interpolated_list
        if isinstance(template, dict):
            interpolated_dict = {}
            for template_key, template_value in template.items():
                interpolated_dict.update({template_key: self._interpolate_object(phase, template_value, variables)})
            return interpolated_dict
        # do nothing
        return template
        # raise CLIError(f"unsupported type in interpolate f{type(template)}, '{template}'")

    def _interpolate_string(self, string, variables):
        return self.jinja_env.from_string(string).render(variables)

    def _interpolate_pre_up_element(self, obj):
        if isinstance(obj, (list, set)):
            for i, _ in enumerate(obj):
                obj[i] = self._interpolate_pre_up_element(obj[i])
        elif isinstance(obj, dict):
            for key in obj:
                obj[key] = self._interpolate_pre_up_element(obj[key])
        elif isinstance(obj, str):
            obj = obj = self.interpolate(FIRST_PHASE, obj, f"variables in config in delayed interpolate '{obj}'")
        return obj

    def _hooks_ops(self):
        ''' returns ops in hooks '''

        output_hooks = {}
        for hook_k, hook_v in self.hooks_dict:
            output_hooks[hook_k] = {}
            for op_obj in hook_v["ops"]:
                op_name = op_obj.get(CONFIG_NAME, False)
                if op_name:
                    if op_name in output_hooks[hook_k]:
                        raise CLIError(f"config schema error duplicate op name '{op_name}'  in hook '{hook_k}")
                    output_hooks[hook_k][op_name] = {}
        return output_hooks

    def interpolate_delayed_variable(self):
        ''' Interpolate delayed variables that was not caught in earlier phases '''

        for k in self._delayed_vars:
            self.first_phase_vars[CONFIG_VARS][k] = self.interpolate(SECOND_PHASE, self.data[CONFIG_VARS][k], f"variables in config in delayed interpolate '{k}'")

    def interpolate_pre_up(self):
        ''' Interpolate variables before up '''

        self.interpolate_delayed_variable()
        if CONFIG_PARAMS in self.data:
            self._interpolate_pre_up_element(self.data[CONFIG_PARAMS])

    def interpolate(self, phase, template, context=None, extra_vars=None, root_vars=None, raw_undefined_error=False):
        ''' Interpolate a string template '''

        if template is None:
            return None
        if phase == FIRST_PHASE:
            variables = self.first_phase_vars
        elif phase == SECOND_PHASE:
            variables = {**self.second_phase_vars, **self.first_phase_vars}

        if extra_vars:
            variables[CONFIG_VARS] = {**variables[CONFIG_VARS], **extra_vars}
        if root_vars:
            variables = {**root_vars, **variables}
        if context:
            error_context = f"in phase: '{phase}'', Context: '{context}'"
        else:
            error_context = f"in phase '{phase}'"
        try:
            return self._interpolate_object(phase, template, variables)
        except UndefinedError as error:
            if raw_undefined_error:
                raise CLIError(f"undefined variable {str(error)}") from error
            raise CLIError(f"expression interpolation error. {error_context}, undefined variable: {str(error)}") from error
        except TemplateSyntaxError as error:
            raise CLIError(f"expression interpolation error. {error_context}, template syntax: {str(error)}") from error
        except (TypeError, TemplateRuntimeError) as error:
            raise CLIError(f"expression interpolation error. {error_context}, Runtime error: {str(error)}") from error

    def update_hooks_result(self, hooks_output):
        ''' Update all hooks results and make them available as variables to second phase '''

        self.second_phase_vars[RUNTIME_HOOKS] = hooks_output

    def get_test(self, test_name, expect=None, hook=None):
        ''' Return test dic '''

        test_obj = self.data.get(CONFIG_TESTS, {}).get(test_name, {})
        if expect is None and hook is None:
            return test_obj
        if expect:
            return test_obj.get("expect", {}).get(expect, {})
        for expect_hook in test_obj.get("expect", {}).get("hooks", []):
            if hook in expect_hook:
                return expect_hook.get(hook)
        return {}

    def test_hooks(self, test_name):
        ''' returns all hooks in a test as list '''

        hooks = []
        for k in self.data.get(CONFIG_TESTS, {}).get(test_name, {}).get("expect", {}).get("hooks", []):
            hooks.append(list(k.keys())[0])
        return hooks

    @property
    def name(self):
        ''' returns CDF name '''

        return self.first_phase_vars[CONFIG_CDF][CONFIG_NAME]

    @property
    def resource_group_name(self):
        ''' returns CDF resource group '''

        return self.first_phase_vars[CONFIG_CDF][CONFIG_RG]

    @property
    def managed_resource(self):
        ''' returns boolean if resource group should be managed by CDF '''

        return self.data[CONFIG_RG_MANAGED]

    @property
    def location(self):
        ''' returns CDF azure location '''

        return self.first_phase_vars[CONFIG_CDF][CONFIG_LOCATION]

    @property
    def tmp_dir(self):
        ''' returns CDF temp directory '''

        return self.first_phase_vars[CONFIG_CDF][CONFIG_TMP]

    @property
    def up_location(self):
        ''' returns CDF up location '''

        return self.data[CONFIG_UP]

    @property
    def provisioner(self):
        ''' returns CDF provisioner '''

        return self.data["provisioner"]

    @property
    def config(self):
        ''' returns raw data of config '''

        return self.data

    @property
    def platform(self):
        ''' returns current platform '''

        return self.first_phase_vars[CONFIG_CDF]["platform"]

    @property
    def config_dir(self):
        ''' return config directory path '''

        return self.first_phase_vars[CONFIG_CDF]["config_dir"]

    @property
    def deployment_mode(self):
        ''' return deployment mode '''

        return self.data[CONFIG_DEPLOYMENT_COMPLETE]

    @property
    def hooks_dict(self):
        ''' returns  hooks as dict '''

        return self.data[CONFIG_HOOKS].items()

    @property
    def hook_names(self):
        ''' returns all hook names as list '''

        hooks = []
        # if self.data[CONFIG_HOOKS]:
        for k, _ in self.hooks_dict:
            hooks.append(k)
        return hooks

    @property
    def tests(self):
        ''' returns all test names as list '''

        tests = []
        for k, _ in self.data[CONFIG_TESTS].items():
            tests.append(k)
        return tests
