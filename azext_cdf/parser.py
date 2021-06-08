""" Configuration module"""

import os
import platform
import yaml
from schema import Schema, SchemaError, SchemaMissingKeyError, SchemaWrongKeyError

from knack.util import CLIError
from jinja2 import Environment, BaseLoader, StrictUndefined, Template, contextfunction  # pass_context
from jinja2.exceptions import UndefinedError, TemplateSyntaxError, TemplateRuntimeError
from azext_cdf.version import VERSION
from azext_cdf.utils import dir_create, dir_remove, real_dirname, random_string, convert_to_list_if_need, dir_change_working
from azext_cdf.state import State
from azext_cdf.parser_schema import MAIN_SCHEMA
# pylint: disable=W0401,W0614
from azext_cdf._def import *


def _include_file(name):
    try:
        with open(name) as in_file:
            return in_file.read()
    except Exception as error:
        raise CLIError(f"include_file filter argument '{name}' error. {str(error)}") from error


# @pass_context
@contextfunction
def _template_file(ctx, name):
    try:
        data = _include_file(name)
        return Template(data, undefined=StrictUndefined).render(ctx)

    except Exception as error:
        raise CLIError(f"template_file filter argument '{name}' error. {str(error)}") from error
    return data


class ConfigParser:
    '''  CDF yaml config parser class '''
    def __init__(self, config_filepath, remove_tmp=False, test=None, working_dir=None, override_config=None, state_locking=True):
        self.data = {}
        self.state = {}
        self.first_phase_vars = {}
        self.second_phase_vars = {}
        self._delayed_vars = []
        self.jinja_env = None
        self.test = test
        self.cwd = os.getcwd()
        if working_dir:
            dir_change_working(working_dir)
        self.data = self._read_config(config_filepath)
        self._validate_conf(config_filepath)
        self._setup_jinja2()
        self._setup_pre_phase_interpolation(config_filepath)  # pre phase
        self._setup_load_file_references()
        self._setup_test()
        if override_config:
            self.data = {**self.data, **override_config}
        self._setup_first_phase_interpolation(state_locking, remove_tmp)  # First phase
        self._setup_second_phase_variables()  # Second phase
        self.update_hooks_result(self.state.result_hooks)
        dir_change_working(self.cwd)

    def _validate_conf(self, config_filepath):
        try:
            schema_obj = Schema(MAIN_SCHEMA)
            self.data = schema_obj.validate(self.data)
            self._extra_validate()
        except SchemaWrongKeyError as error:
            raise CLIError(f"config schema error 'SchemaWrongKeyError' in '{config_filepath}' an unexpected key is detected: {str(error)}") from error
        except SchemaMissingKeyError as error:
            raise CLIError(f"config  schema error 'SchemaMissingKeyError' in '{config_filepath}' a mandatory key is not found: {str(error)}") from error
        except SchemaError as error:
            raise CLIError(f"config schema error 'SchemaError' in '{config_filepath}' a general schema violation: {str(error)}") from error

    def _extra_validate(self):
        ''' validation not covered by schema '''
        hooks = []
        for hook_name, hook_value in self.get_hooks(format_list=False):
            hooks.append(hook_name)
            if hook_name[0] == "_":
                raise CLIError(f"Hook names '{hook_name}' can't start with '_'")
            for operation in hook_value.get("ops"):
                op_name = operation.get(CONFIG_NAME, " ")
                if op_name[0] == "_":
                    raise CLIError(f"op names '{op_name}' can't start with '_'")
                if operation.get(CONFIG_TYPE) == "call" and operation.get(CONFIG_ARGS) not in self.get_hooks(format_list=True):
                    raise CLIError(f"'{op_name}' can't call an undefined hook {operation.get('args')}")

        # TODO Refactor very messy
        for test in self.data.get(CONFIG_TESTS, {}):
            for hooks_ops in self.data[CONFIG_TESTS][test].get(CONFIG_EXPECT, {}).get(CONFIG_HOOKS, []):
                for hook in hooks_ops:
                    if hook not in hooks:
                        raise CLIError(f"unknown hook name '{hook}' in expect test '{test}'")
            upgrade_from_names = []
            for upgrade in self.data[CONFIG_TESTS][test].get("upgrade_from", []):
                name = upgrade.get(CONFIG_NAME).lower().strip()
                if name in upgrade_from_names:
                    raise CLIError(f"upgrade from name'{name}' is duplicated.")
                upgrade_from_names.append(name)

    @staticmethod
    def _read_config(filepath):
        try:
            with open(filepath) as file_in:
                return yaml.load(file_in, Loader=yaml.FullLoader)
        except (yaml.parser.ParserError, yaml.scanner.ScannerError, yaml.constructor.ConstructorError) as error:
            raise CLIError(f"Config file '{filepath}' yaml parser error:': {str(error)}") from error
        except FileNotFoundError as error:
            raise CLIError(f"Config file '{filepath}' file not found:': {str(error)}") from error

    def _setup_jinja2(self):
        self.jinja_env = Environment(loader=BaseLoader, undefined=StrictUndefined)
        self.jinja_env.globals["include_file"] = _include_file
        self.jinja_env.globals["template_file"] = _template_file
        self.jinja_env.globals["random_string"] = random_string

    def _setup_load_file_references(self):
        # Load all files from tests
        for test_name in self.data[CONFIG_TESTS].keys():
            if self.data[CONFIG_TESTS][test_name].get(CONFIG_FILE, False):  # load test from another dir
                self.data[CONFIG_TESTS][test_name][CONFIG_FILE] = self.interpolate(FIRST_PHASE, self.data[CONFIG_TESTS][test_name][CONFIG_FILE], f"test {test_name} key {CONFIG_FILE}")
                test_data = self._read_config(self.data[CONFIG_TESTS][test_name][CONFIG_FILE])
                self.data[CONFIG_TESTS][test_name] = {**self.data[CONFIG_TESTS][test_name], **test_data}
                self._validate_conf(self.data[CONFIG_TESTS][test_name][CONFIG_FILE])  # revalidate after loading data

    def _setup_test(self):
        if not self.test:
            return
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

    def _setup_pre_phase_interpolation(self, config_filepath):
        self.first_phase_vars = {
            CONFIG_CDF: {
                "version": VERSION,
                "config_dir": real_dirname(config_filepath),
                "platform": platform.system().lower(),
            },
            RUNTIME_ENV_KEY: os.environ,
            CONFIG_VARS: {},
            CONFIG_PARAMS: {},
            RUNTIME_RUN_ONCE_KEY: RUNTIME_RUN_ONCE,
        }

    def _setup_first_phase_interpolation(self, state_locking, remove_tmp=False):
        ''' first phase interpolation '''
        # self.override override_state=None, prefix_state=None,
        self.first_phase_vars[CONFIG_CDF][CONFIG_TMP] = self.interpolate(FIRST_PHASE, self.data[CONFIG_TMP], context=f"key {CONFIG_TMP}")
        if remove_tmp:  # remove and create tmp dir incase we will download some stuff for templates
            dir_remove(self.tmp_dir)
        dir_create(self.tmp_dir)
        self.data[CONFIG_STATE_FILEPATH] = self.interpolate(FIRST_PHASE, self.data[CONFIG_STATE_FILEPATH], context=f"key {CONFIG_STATE_FILEPATH}")
        self.state = State(self.data[CONFIG_STATE_FILEPATH], locking=state_locking)  # initialize state
        self.jinja_env.globals["store"] = self.state.store_get  # setup store functions in jinja2

        self.first_phase_vars[CONFIG_CDF][CONFIG_NAME] = self.interpolate(FIRST_PHASE, self.data[CONFIG_NAME], f"key {CONFIG_NAME}")
        if CONFIG_VARS in self.data:
            # lazy variable resolve
            for key, value in self.data[CONFIG_VARS].items():
                try:
                    self.first_phase_vars[CONFIG_VARS][key] = self.interpolate(FIRST_PHASE, value, f"variables in config '{key}':'{value}'")
                except UndefinedError as error:
                    if "result" in str(error):
                        self._delayed_vars.append(key)
                    else:
                        raise CLIError() from error
        self.first_phase_vars[CONFIG_CDF][CONFIG_RG] = self.interpolate(FIRST_PHASE, self.data[CONFIG_RG], f"key {CONFIG_RG}")
        self.first_phase_vars[CONFIG_CDF][CONFIG_LOCATION] = self.interpolate(FIRST_PHASE, self.data[CONFIG_LOCATION], f"key {CONFIG_LOCATION}")
        self.data[CONFIG_UP] = self.interpolate(FIRST_PHASE, self.data[CONFIG_UP], f"key {CONFIG_UP}")
        # Setup state after interpolation
        self.state.setup(deployment_name=self.name, resource_group=self.resource_group_name, config_hooks=self._ops_in_hooks())

    def _setup_second_phase_variables(self):
        self.second_phase_vars = {
            RUNTIME_RESULT: {
                RUNTIME_RESULT_OUTPUTS: {},
                RUNTIME_RESULT_RESOURCES: {},
            },
            RUNTIME_HOOKS: self._ops_in_hooks(),
        }
        self.second_phase_vars[RUNTIME_RESULT] = self.state.result_up  # update results from state

    def _raw_interpolate_object(self, template, variables=None):
        if isinstance(template, str):
            return self.jinja_env.from_string(template).render(variables)
        if isinstance(template, list):
            interpolated_list = []
            for template_item in template:
                interpolated_list.append(self._raw_interpolate_object(template_item, variables))
            return interpolated_list
        if isinstance(template, dict):
            interpolated_dict = {}
            for template_key, template_value in template.items():
                interpolated_dict.update({template_key: self._raw_interpolate_object(template_value, variables)})
            return interpolated_dict
        # do nothing
        return template

    # TODO can be moved to interploate with flag
    def interpolate_delayed_variable(self):
        ''' Interpolate delayed variables that was not caught in earlier phases '''

        for k in self._delayed_vars:
            self.first_phase_vars[CONFIG_VARS][k] = self.interpolate(SECOND_PHASE, self.data[CONFIG_VARS][k], f"variables in config in delayed interpolate '{k}'")

    def interpolate_pre_up(self):
        ''' Interpolate variables before up '''

        self.interpolate_delayed_variable()
        if CONFIG_PARAMS in self.data:
            self.data[CONFIG_PARAMS] = self.interpolate(FIRST_PHASE, self.data[CONFIG_PARAMS], context="pre up interpolation")

    def interpolate(self, phase, template, context=None, extra_vars=None, root_vars=None):
        ''' Interpolate a string template '''

        if template is None:
            return None
        # variables
        variables = self.first_phase_vars  # setup first phase anyway
        if phase == SECOND_PHASE:
            variables = {**self.second_phase_vars, **self.first_phase_vars}
        if extra_vars:
            variables[CONFIG_VARS] = {**variables[CONFIG_VARS], **extra_vars}
        if root_vars:
            variables = {**root_vars, **variables}

        error_context = f"in phase '{phase}'"
        if context:
            error_context = f"in phase: '{phase}'', Context: '{context}'"

        try:
            return self._raw_interpolate_object(template, variables)
        except UndefinedError as error:
            raise CLIError(f"expression interpolation error. {error_context}, undefined variable: {str(error)}") from error
        except TemplateSyntaxError as error:
            raise CLIError(f"expression interpolation error. {error_context}, template syntax: {str(error)}") from error
        except (TypeError, TemplateRuntimeError) as error:
            raise CLIError(f"expression interpolation error. {error_context}, Runtime error: {str(error)}") from error

    def update_hooks_result(self, hooks_output):
        ''' Update all hooks results and make them available as variables to second phase '''

        self.second_phase_vars[RUNTIME_HOOKS] = hooks_output

    def _ops_in_hooks(self):
        ''' returns ops in hooks '''

        output_hooks = {}
        for hook_k, hook_v in self.get_hooks(format_list=False):
            output_hooks[hook_k] = {}
            for op_obj in hook_v["ops"]:
                op_name = op_obj.get(CONFIG_NAME, False)
                if not op_name:
                    continue  # skip since we don't have a names
                if op_name in output_hooks[hook_k]:
                    raise CLIError(f"config schema error duplicate op name '{op_name}' in hook '{hook_k}")
                output_hooks[hook_k][op_name] = {}
        return output_hooks

    def get_hooks(self, format_list=True):
        ''' Return hooks as list of name or as dict with object'''
        if format_list:
            hooks = []
            for k, _ in self.data[CONFIG_HOOKS].items():
                hooks.append(k)
            return hooks
        return self.data[CONFIG_HOOKS].items()

    def get_test(self, test_name, expect=None, hook=None):
        ''' Return test dic '''

        test_obj = self.data.get(CONFIG_TESTS, {}).get(test_name, {})
        if expect is None and hook is None:
            return test_obj
        if expect:
            return test_obj.get(CONFIG_EXPECT, {}).get(expect, {})
        for expect_hook in test_obj.get(CONFIG_EXPECT, {}).get(CONFIG_HOOKS, []):
            if hook in expect_hook:
                return expect_hook.get(hook)
        return {}

    def test_hooks(self, test_name):
        ''' returns all hooks in a test as list '''

        hooks = []
        for k in self.data.get(CONFIG_TESTS, {}).get(test_name, {}).get(CONFIG_EXPECT, {}).get(CONFIG_HOOKS, []):
            hooks.append(list(k.keys())[0])
        return hooks

    def upgrade_flaten(self, test_name):
        ''' return deployment mode '''
        upgrade_path = []
        upgrades = self.data[CONFIG_UPGRADE] + self.get_test(test_name).get(CONFIG_UPGRADE)
        for upgrade in self.interpolate(FIRST_PHASE, upgrades, context="upgrade path"):
            from_expects = convert_to_list_if_need(upgrade.get("from_expect"))
            for from_expect in from_expects:
                upgrade_copy = upgrade.copy()
                upgrade_copy["from_expect"] = from_expect
                upgrade_path.append(upgrade_copy)
        return upgrade_path

    # TODO merge with get_test
    @property
    def tests(self):
        ''' returns all test names as list '''

        tests = []
        for k, _ in self.data[CONFIG_TESTS].items():
            tests.append(k)
        return tests

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
