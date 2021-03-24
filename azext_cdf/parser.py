import yaml
import os
import platform

from knack.util import CLIError
from schema import Schema, And,Or, Use, Optional, SchemaError, SchemaMissingKeyError, SchemaWrongKeyError
from jinja2 import Environment, BaseLoader, StrictUndefined, contextfunction
from jinja2.exceptions import UndefinedError, TemplateSyntaxError
from azext_cdf.VERSION import VERSION
from azext_cdf.utils import dir_create, dir_remove, is_part_of, real_dirname

FIRST_PHASE = 1
SECOND_PHASE = 2
# Runtime vars
RUNTIME_ENV_KEY = 'env'
RUNTIME_CDF_VERSION_KEY = 'CDF_VERSION'
RUNTIME_CDF_TMP_DIR_KEY = 'CDF_TMP_DIR'
RUNTIME_CONFIG_DIR_KEY = 'CONFIG_DIR'
RUNTIME_CONFIG_RESOURCE_GROUP = 'CONFIG_RESOURCE_GROUP'
RUNTIME_PLATFORM = 'PLATFORM'
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
CONFIG_STATE_FILE_DEFAULT = '{{' + RUNTIME_CDF_TMP_DIR_KEY + '}}/state.json'
LIFECYCLE_PRE_UP, LIFECYCLE_POST_UP, LIFECYCLE_PRE_DOWN, LIFECYCLE_POST_DOWN,LIFECYCLE_PRE_TEST, LIFECYCLE_POST_TEST, LIFECYCLE_ALL  = "pre-up", "post-up", "pre-down","post-down", "pre-test","post-test", ""
CONFIG_SUPPORTED_LIFECYCLE = (LIFECYCLE_PRE_UP, LIFECYCLE_POST_UP, LIFECYCLE_PRE_DOWN, LIFECYCLE_POST_DOWN,LIFECYCLE_PRE_TEST, LIFECYCLE_POST_TEST, LIFECYCLE_ALL)
CONFIG_SUPPORTED_PLATFORM = ("linux", "windows", "darwin", "")
CONFIG_SUPPORTED_TYPES = ('az', 'cmd', "print", "call") #('bicep', 'arm',  'api', 'rest', "terraform")

# @contextfunction                                                                                                                                                                                         
# def content(ctx, name):                                                                                                                                                                                   
#     env = ctx.environment                                                                                                                                                                                      
#     return jinja2.Markup(env.loader.get_source(env, name)[0])    

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
                                    Optional("type", default="az"): And(str, Use(str.lower), lambda s: s in CONFIG_SUPPORTED_TYPES),
                                    Optional("platform", default=""): Or(And(str, Use(str.lower), (And(list))), lambda s: is_part_of(s, CONFIG_SUPPORTED_PLATFORM)),
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
                            Optional(CONFIG_TMP, default='{{CONFIG_DIR}}/.cdf_tmp'): And(str, len),
                            # Optional('vars_file', default=[]): Or(str,list),
                            Optional(CONFIG_VARS, default={}): dict,
                            Optional(CONFIG_PARAMS, default={}): dict,
                            Optional(CONFIG_HOOKS, default={}): hooks_schema,
                            Optional(CONFIG_STATE_FILE, default=CONFIG_STATE_FILE_DEFAULT) : str ,
                           }
        self._loadandValidateConf()
        self.jEnv = Environment(loader=BaseLoader,undefined=StrictUndefined)
        # self.jEnv.globals['content'] = content
        # first phase
        self._setupFirstPhaseVariables()
        self._setupFirstPhaseInterpolation()
        #seconf phase
        self._setupSecondPhaseVariables() 

    def updateHooksResult(self, hooks_output):
        self.secondPhaseVars[RUNTIME_HOOKS] = hooks_output

    def updateResult(self, result):
        self.secondPhaseVars[RUNTIME_RESULT] = result


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
            RUNTIME_CDF_VERSION_KEY: VERSION,
            RUNTIME_CONFIG_DIR_KEY: real_dirname(self._config),
            RUNTIME_ENV_KEY: os.environ,
            RUNTIME_PLATFORM: platform.system().lower(),
            CONFIG_VARS: {},
            CONFIG_PARAMS: {},
        }
        if CONFIG_VARS in self.data:
            for v, k in self.data[CONFIG_VARS].items():
                self.firstPhaseVars[CONFIG_VARS][v] = self.interpolate(FIRST_PHASE, k, f"variables in config '{v}':'{k}'")
            # cosmetics change the vars in data not really needed
            self.data[CONFIG_VARS] = self.firstPhaseVars[CONFIG_VARS]

    def _setupFirstPhaseInterpolation(self):
        self.data[CONFIG_TMP] = self.interpolate(FIRST_PHASE, self.data[CONFIG_TMP])
        self.firstPhaseVars[RUNTIME_CDF_TMP_DIR_KEY] = self.data[CONFIG_TMP]
        # remove and create tmp dir incase we will download some stuff for templates
        if self._rtmp:
            dir_remove(self.data[CONFIG_TMP])
        dir_create(self.data[CONFIG_TMP])
        self.data[CONFIG_STATE_FILE] = self.interpolate(FIRST_PHASE, self.data[CONFIG_STATE_FILE])
        self.data[CONFIG_NAME] = self.interpolate(FIRST_PHASE, self.data[CONFIG_NAME])
        self.data[CONFIG_RG] = self.interpolate(FIRST_PHASE, self.data[CONFIG_RG])
        self.firstPhaseVars[RUNTIME_CONFIG_RESOURCE_GROUP] = self.data[CONFIG_RG]
        self.data[CONFIG_LOCATION] = self.interpolate(FIRST_PHASE, self.data[CONFIG_LOCATION])
        self.data[CONFIG_SCOPE] = self.interpolate(FIRST_PHASE, self.data[CONFIG_SCOPE])
        self.data[CONFIG_UP] = self.interpolate(FIRST_PHASE, self.data[CONFIG_UP])
        if CONFIG_PARAMS in self.data:
            for v,k in self.data[CONFIG_PARAMS].items():
                self.data[CONFIG_PARAMS][v] = self.interpolate(FIRST_PHASE, k)
    
    def _setupSecondPhaseVariables(self):
        self.secondPhaseVars = {
                RUNTIME_RESULT: {
                    RUNTIME_RESULT_OUTPUTS: {},
                    RUNTIME_RESULT_RESOURCES: {},
                },
                RUNTIME_HOOKS: self.hooks_ops
        }

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

        return self._interpolate_object(phase, template, error_context, variables)

    def _interpolate_object(self, phase, template, context=None, variables={}):
        if isinstance(template, str):
            return self._intrerpolate_string(template, context, variables)
        elif isinstance(template, list):
            interpolated_list = []
            for template_item in template:
                interpolated_list.append(self._interpolate_object(phase, template_item, context, variables))
            return interpolated_list
        elif isinstance(template, dict):
            interpolated_dict = {}
            for template_key, template_value in template.items():
                interpolated_dict.update({template_key: self._interpolate_object(phase, template_value, context, variables)})
            return interpolated_dict

    def _intrerpolate_string(self, string, error_context, variables):
        try:
            template_string = self.jEnv.from_string(string)
            return template_string.render(variables)
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
        return self.firstPhaseVars[RUNTIME_PLATFORM]

    @property
    def deployment_mode(self):
        return self.data[CONFIG_DEPLOYMENT_COMPLETE]
