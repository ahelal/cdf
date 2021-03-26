import yaml
import os
import platform

from knack.util import CLIError
from schema import Schema, And,Or, Use, Optional, SchemaError, SchemaMissingKeyError, SchemaWrongKeyError
from jinja2 import Environment, BaseLoader, StrictUndefined, contextfunction,Template
from jinja2.exceptions import UndefinedError, TemplateSyntaxError
from azext_cdf.VERSION import VERSION
from azext_cdf.utils import dir_create, dir_remove, is_part_of, real_dirname

FIRST_PHASE = 1
SECOND_PHASE = 2
# Runtime vars
RUNTIME_ENV_KEY = 'env'
# RUNTIME_CDF_VERSION_KEY = 'CDF_VERSION' # cdf.version
# RUNTIME_CDF_TMP_DIR_KEY = 'CDF_TMP_DIR' # cdf.tmp_dir
# RUNTIME_CONFIG_DIR_KEY = 'CONFIG_DIR' # cdf.tmp_dir
# RUNTIME_CONFIG_RESOURCE_GROUP = 'CONFIG_RESOURCE_GROUP' # cdf.resource_group
# RUNTIME_PLATFORM = 'PLATFORM' # cdf.platformp
RUNTIME_RESULT = 'result'
RUNTIME_RESULT_OUTPUTS = 'outputs'
RUNTIME_RESULT_RESOURCES = 'resources'
RUNTIME_HOOKS= 'hooks'
# Config
CONFIG_NAME = 'name'
CONFIG_RG = 'resource_group'
CONFIG_RG_MANAGED = 'manage_resource_group'
CONFIG_LOCATION = 'location'
CONFIG_SUPPORTED_PROVISIONERS = ('bicep') #('bicep', 'terraform')
CONFIG_PROVISIONER = 'provisioner'
CONFIG_SCOPE = 'scope'
CONFIG_TMP = 'temp_dir'
CONFIG_UP = 'up'
CONFIG_VARS = 'vars'
CONFIG_PARAMS = 'params'
CONFIG_STATE_FILE = 'state'
CONFIG_HOOKS = 'hooks'
CONFIG_DEPLOYMENT_COMPLETE = 'complete_deployment'
CONFIG_STATE_FILE_DEFAULT = '{{ cdf.tmp_dir }}/state.json'
LIFECYCLE_PRE_UP, LIFECYCLE_POST_UP, LIFECYCLE_PRE_DOWN, LIFECYCLE_POST_DOWN,LIFECYCLE_PRE_TEST, LIFECYCLE_POST_TEST, LIFECYCLE_ALL  = "pre-up", "post-up", "pre-down","post-down", "pre-test","post-test", ""
CONFIG_SUPPORTED_LIFECYCLE = (LIFECYCLE_PRE_UP, LIFECYCLE_POST_UP, LIFECYCLE_PRE_DOWN, LIFECYCLE_POST_DOWN,LIFECYCLE_PRE_TEST, LIFECYCLE_POST_TEST, LIFECYCLE_ALL)
CONFIG_SUPPORTED_PLATFORM = ("linux", "windows", "darwin", "")
CONFIG_SUPPORTED_OPS_TYPES = ('az', 'cmd', "print", "call", "script") #('bicep', 'arm',  'api', 'rest', "terraform")

def include_file(name):
    try:
        with open(name) as f:
            return f.read()
    except Exception as e:
        raise CLIError(f"include_file filter argument '{name}' error. {str(e)}")

@contextfunction
def template_file(ctx, name):
    try:
        data = include_file(name)
        return Template(data, undefined=StrictUndefined).render(ctx)
        
    except Exception as e:
        raise CLIError(f"template_file filter argument '{name}' error. {str(e)}")
    return data

class ConfigParser:
    def __init__(self, config, rtmp=False):
        self.data = {}
        self._config = config
        self.firstPhaseVars = {}
        self.secondPhaseVars = {}
        self._rtmp = rtmp
        # https://github.com/keleshev/schema
        hooks_schema = {str: {
                                "ops": [{
                                    Optional("name"):  str,
                                    Optional("description"): str,
                                    Optional("type", default="az"): And(str, Use(str.lower), lambda s: s in CONFIG_SUPPORTED_OPS_TYPES),
                                    Optional("platform", default=""): Or(And(str, Use(str.lower), (And(list))), lambda s: is_part_of(s, CONFIG_SUPPORTED_PLATFORM)),
                                    Optional("interactive", default=False): bool,
                                    "args": Or(str,list),
                                }],
                                Optional("lifecycle", default=""): Or(And(str, Use(str.lower), (And(list))), lambda s: is_part_of(s, CONFIG_SUPPORTED_LIFECYCLE)),
                                Optional("description", default=""): str,
                            }
        }
        self._schema_def = {
                            CONFIG_NAME: And(str, len),
                            CONFIG_RG: And(str, len),
                            CONFIG_LOCATION: And(str, len),
                            Optional(CONFIG_SCOPE, default='resource_group'): And(str, len),
                            Optional(CONFIG_RG_MANAGED, default=True): bool,
                            Optional(CONFIG_PROVISIONER, default='bicep'): And(str, Use(str.lower), lambda s: s in CONFIG_SUPPORTED_PROVISIONERS),
                            Optional(CONFIG_DEPLOYMENT_COMPLETE, default=False): bool,
                            Optional(CONFIG_UP, default=None): And(str, len),
                            Optional(CONFIG_TMP, default='{{cdf.config_dir}}/.cdf_tmp'): And(str, len),
                            # Optional('vars_file', default=[]): Or(str,list),
                            Optional(CONFIG_VARS, default={}): dict,
                            Optional(CONFIG_PARAMS, default={}): dict,
                            Optional(CONFIG_HOOKS, default={}): hooks_schema,
                            Optional(CONFIG_STATE_FILE, default=CONFIG_STATE_FILE_DEFAULT) : str ,
                           }
        self._loadandValidateConf()
        self.jEnv = Environment(loader=BaseLoader, undefined=StrictUndefined)
        self.jEnv.globals['include_file'] = include_file
        self.jEnv.globals['template_file'] = template_file
        self._delayed_vars = []
        # First phase
        self._setupFirstPhaseVariables()
        self._setupFirstPhaseInterpolation()
        # Second phase
        self._setupSecondPhaseVariables()

    def _loadandValidateConf(self):
        self.data = self._readConfig(self._config)
        try:
            schema = Schema(self._schema_def)
            self.data = schema.validate(self.data)
        except SchemaError as e:
            raise CLIError("config schema error 'SchemaError' in '{}' a general schema violation : {}".format(self._config, str(e)))
        except SchemaWrongKeyError as e:
            raise CLIError("config schema error 'SchemaWrongKeyError' in '{}' an unexpected key is detected : {}".format(self._config, str(e)))
        except SchemaMissingKeyError as e:
            raise CLIError("config  schema error 'SchemaMissingKeyError' in '{}' a mandatory key is not found : {}".format(self._config, str(e)))

    @staticmethod
    def _readConfig(filepath):
        try:
            with open(filepath) as f:
                return yaml.load(f, Loader=yaml.FullLoader)
        except yaml.parser.ParserError as e:
            raise CLIError(f"Config file '{filepath}' yaml parser error:': {str(e)}")
        except FileNotFoundError as e:
            raise CLIError(f"Config file '{filepath}' file not found:': {str(e)}")

    def _setupFirstPhaseVariables(self):
        self.firstPhaseVars = {
            "cdf":{
                "version": VERSION,
                "config_dir": real_dirname(self._config),
                "platform": platform.system().lower(),
            },
            RUNTIME_ENV_KEY: os.environ,
            CONFIG_VARS: {},
            CONFIG_PARAMS: {},
        }
        if CONFIG_VARS in self.data:
            for k, v in self.data[CONFIG_VARS].items():
                try:
                    self.firstPhaseVars[CONFIG_VARS][k] = self.interpolate(FIRST_PHASE, v, f"variables in config '{k}':'{v}'")
                except CLIError as e:
                    if 'result' in str(e):
                        self._delayed_vars.append(k)
                    else:
                        raise

    def _setupFirstPhaseInterpolation(self):
        self.data[CONFIG_TMP] = self.interpolate(FIRST_PHASE, self.data[CONFIG_TMP], f"key {CONFIG_TMP}")
        self.firstPhaseVars["cdf"]["tmp_dir"] = self.data[CONFIG_TMP]
        # remove and create tmp dir incase we will download some stuff for templates
        if self._rtmp:
            dir_remove(self.data[CONFIG_TMP])
        dir_create(self.data[CONFIG_TMP])
        self.data[CONFIG_STATE_FILE] = self.interpolate(FIRST_PHASE, self.data[CONFIG_STATE_FILE], f"key {CONFIG_STATE_FILE}")
        self.data[CONFIG_NAME] = self.interpolate(FIRST_PHASE, self.data[CONFIG_NAME], f"key {CONFIG_NAME}")
        self.data[CONFIG_RG] = self.interpolate(FIRST_PHASE, self.data[CONFIG_RG], f"key {CONFIG_RG}")
        self.firstPhaseVars['cdf']['resource_group'] = self.data[CONFIG_RG]
        self.data[CONFIG_LOCATION] = self.interpolate(FIRST_PHASE, self.data[CONFIG_LOCATION], f"key {CONFIG_LOCATION}")
        self.firstPhaseVars['cdf']['location'] = self.data[CONFIG_RG]
        self.data[CONFIG_UP] = self.interpolate(FIRST_PHASE, self.data[CONFIG_UP], f"key {CONFIG_UP}")

    def _setupSecondPhaseVariables(self):
        self.secondPhaseVars = {
                RUNTIME_RESULT: {
                    RUNTIME_RESULT_OUTPUTS: {},
                    RUNTIME_RESULT_RESOURCES: {},
                },
                RUNTIME_HOOKS: self.hooks_ops
        }

    def _interpolate_object(self, phase, template,variables={}):
        if isinstance(template, str):
            return self._intrerpolate_string(template, variables)
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

    def _intrerpolate_string(self, string, variables,):
        template_string = self.jEnv.from_string(string)
        return template_string.render(variables)

    def updateHooksResult(self, hooks_output):
        self.secondPhaseVars[RUNTIME_HOOKS] = hooks_output

    def updateResult(self, result):
        self.secondPhaseVars[RUNTIME_RESULT] = result

    def delayedVariableInterpolite(self):
        for k in self._delayed_vars:
            self.firstPhaseVars[CONFIG_VARS][k] = self.interpolate(SECOND_PHASE, self.data[CONFIG_VARS][k], f"variables in config in preUpInterpolite '{k}'")

    def preUpInterpolite(self):
        self.delayedVariableInterpolite()
        if CONFIG_PARAMS in self.data:
            for v,k in self.data[CONFIG_PARAMS].items():
                self.data[CONFIG_PARAMS][v] = self.interpolate(FIRST_PHASE, k, f"variables in config in preUpInterpolite '{k}'")

    def interpolate(self, phase, template, context=None, extra_vars={}):
        if template is None:
            return None
        if phase == FIRST_PHASE:
            variables = self.firstPhaseVars
        elif phase == SECOND_PHASE:
            variables = {**self.secondPhaseVars, **self.firstPhaseVars}

        if extra_vars:
            variables = {**vars, **extra_vars}

        if context:
            error_context = f"in phase: '{phase}'', Context: '{context}'"
        else:
            error_context = f"in phase '{phase}'"

        try:
            return self._interpolate_object(phase, template, variables)
        # except TypeError as e:
        #     raise CLIError(f"config interpolation error. {error_context}, undefined variable : {str(e)}")
        except UndefinedError as e:
                raise CLIError(f"config interpolation error. {error_context}, undefined variable : {str(e)}")
        except TemplateSyntaxError as e:
            raise CLIError(f"config interpolation error. {error_context}, template syntax : {str(e)}")
        

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
        return self.data['provisioner']

    @property
    def config(self):
        return self.data

    @property
    def hook_names(self):
        hooks = []
        if self.data[CONFIG_HOOKS]:
            for k, _ in self.data[CONFIG_HOOKS].items():
                hooks.append(k)
        return hooks

    @property
    def hook_table(self):
        outputHooks = []
        if self.data[CONFIG_HOOKS]:
            for k,v in self.data[CONFIG_HOOKS].items():
                outputHooks.append({"name": k, "descripition": v['description'], "lifecycle": v['lifecycle']})
        return outputHooks

    @property
    def hooks_ops(self):
        outputHooks = {}
        if not self.data[CONFIG_HOOKS]:
            return outputHooks

        for hook_k, hook_v in self.data[CONFIG_HOOKS].items():
            outputHooks[hook_k] = {}
            for op in hook_v['ops']:
                op_name = op.get("name", False)
                if op_name:
                    if op_name in outputHooks[hook_k]:
                        raise CLIError(f"config schema error duplicate op name '{op_name}'  in hook '{hook_k}")
                    outputHooks[hook_k][op_name] = {}
        return outputHooks

    @property
    def state_file(self):
        return self.data[CONFIG_STATE_FILE]
    
    @property
    def platform(self):
        return self.firstPhaseVars["cdf"]["platform"]

    @property
    def config_dir(self):
        return self.firstPhaseVars["cdf"]["config_dir"]

    @property
    def deployment_mode(self):
        return self.data[CONFIG_DEPLOYMENT_COMPLETE]
