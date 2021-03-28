from copy import deepcopy
from datetime import datetime
import semver
from knack.util import CLIError
from knack.log import get_logger
from azext_cdf.utils import json_write_to_file, file_exits, file_read_content, json_load
from azext_cdf.VERSION import VERSION

STATE_PHASE_UNKNOWN = "unknown"
STATE_PHASE_GOING_UP = "transitioning_up"
STATE_PHASE_UP = "UP"
STATE_PHASE_TESTED = "tested"
STATE_PHASE_TESTING = "testing"
STATE_PHASE_DOWN = "down"
STATE_PHASE_GOING_DOWN = "transitioning_down"
STATE_PHASE_RUNNING_HOOK = "running_hook"

STATE_STATUS_UNKNOWN = "unknown"
STATE_STATUS_SUCCESS = "success"
STATE_STATUS_ERROR = "errored"
STATE_STATUS_FAILED = "failed"
STATE_STATUS_PENDING = "pending"

STATE_DEPLOYMENT_NAME = "name"
STATE_RESOURCE_GROUP = "resource_group"
STATE_PHASE = "phase"
STATE_LASTUPDATE = "lastUpdate"
STATE_STATUS = "status"
STATE_EVENTS = "events"
STATE_UP_RESULT = "result"
STATE_UP_RESULT_OUTPUTS = "outputs"
STATE_UP_RESULT_RESOURCES = "resources"
STATE_HOOKS_RESULT = "hooks"
STATE_HOOKS_RESULT = "hooks"
STATE_VERSION = "version"
STATE_STORE = "store"

logger = get_logger(__name__)

class State(object):
    def __init__(self, state_file, name, config_hooks):
        self.state_file = state_file
        self.config_hooks = config_hooks
        if not file_exits(self.state_file):
            self.state_db = {
                STATE_DEPLOYMENT_NAME: name,
                STATE_PHASE : STATE_PHASE_UNKNOWN,
                STATE_LASTUPDATE: self.timestamp(),
                STATE_STATUS: -1,
                STATE_EVENTS: [],
                STATE_VERSION: VERSION,
                STATE_STORE: {},
                STATE_HOOKS_RESULT: {},
                STATE_RESOURCE_GROUP: None,
                STATE_UP_RESULT: {
                    STATE_UP_RESULT_OUTPUTS: {},
                    STATE_UP_RESULT_RESOURCES: {}
                }
            }
            self._setup_hooks_reference()
            self.add_event("Created state file", status=STATE_STATUS_UNKNOWN, flush=True)
            return

        # state file exists
        try:
            state_str = file_read_content(self.state_file)
            self.state_db = json_load(state_str)
        except CLIError as error:
            raise CLIError(f"Error while reading/decoding state '{self.state_file}' Did you try to change it manually. {str(error)}") from error

        if not self.state_db[STATE_DEPLOYMENT_NAME] == name:
            raise CLIError("state error seems you have changed the deployment name to '{}', the state has this deployment name: {}".format(self.state_db[STATE_DEPLOYMENT_NAME], name))
        # resource_group
        self._version_compare()
        self._setup_hooks_reference()

    def check_resource_group(self, resource_group):
        # Check resource group
        if resource_group == self.state_db[STATE_RESOURCE_GROUP]:
            pass
        elif self.state_db[STATE_RESOURCE_GROUP] is None:
            self.state_db[STATE_RESOURCE_GROUP] = resource_group
            self._flush_state()
        elif self.state_db[STATE_PHASE] == STATE_PHASE_UNKNOWN or self.state_db[STATE_PHASE] == STATE_PHASE_DOWN:
            pass
        else:
            raise CLIError("Resource group already provisioned '{}', Can't change resource group before destroying.".format(self.state_db[STATE_RESOURCE_GROUP]))

    def _version_compare(self):
        state_version = self.state_db['version']
        version_compare = semver.compare(state_version, VERSION)
        if version_compare == -1: # state is less then cli
            logger.warning(f'Your state file is out date: state version {state_version} CDF version {VERSION}. Run `up -r` to rewrite state')
        elif version_compare == 1: # state is more then cli
            logger.warning(f'Your CDF extension is outdate: state version {state_version} CLI version {VERSION}. Updgrade extension')
        elif version_compare == 0: # state is less then cli
            pass

    def _setup_hooks_reference(self):
        # hooks/ops in state db but not config_db
        current_state_db_hooks = deepcopy(self.state_db[STATE_HOOKS_RESULT])
        for state_hook in current_state_db_hooks:
            if state_hook in self.config_hooks:
                for state_op in current_state_db_hooks[state_hook]:
                    if state_op[0] == "_":
                        pass # ignore _
                    elif not state_op in self.config_hooks[state_hook]:
                        self.state_db[STATE_HOOKS_RESULT][state_hook].pop(state_op)
            else:
                self.state_db[STATE_HOOKS_RESULT].pop(state_hook) #remove hook outdate

        # hooks/ops in config db but not config_db
        for config_hook in self.config_hooks:
            if not config_hook in self.state_db[STATE_HOOKS_RESULT]:
                self.state_db[STATE_HOOKS_RESULT][config_hook] = {}
            for config_op in self.config_hooks[config_hook]:
                if not config_op in self.state_db[STATE_HOOKS_RESULT][config_hook]:
                    self.state_db[STATE_HOOKS_RESULT][config_hook][config_op] = {}

    def _flush_state(self, flush=True):
        if flush:
            json_write_to_file(self.state_file, self.state_db)

    def transitionToPhase(self, phase):
        self.add_event(f"Transitioning to {phase}", phase=phase, status=STATE_STATUS_PENDING, flush=True)

    def completedPhase(self, phase, status, msg=""):
        if status == STATE_STATUS_SUCCESS:
            self.add_event(f"Successfully reached {phase}. { msg }", phase=phase, status=STATE_STATUS_SUCCESS, flush=True)
        elif status == STATE_STATUS_ERROR:
            self.add_event(f"Errored during {phase}. { msg }", status=STATE_STATUS_ERROR, flush=True)
        elif status == STATE_STATUS_FAILED:
            self.add_event(f"Failed during {phase}. { msg }", status=STATE_STATUS_FAILED, flush=True)

    def add_event(self, msg, status=None, phase=None, hook=None, flush=True):
        if phase:
            self.state_db[STATE_PHASE] = phase
        event = {"timestamp": self.timestamp(), "phase": self.state_db[STATE_PHASE], "msg": msg, "status": status, "hook": hook}
        self.state_db[STATE_EVENTS].append(event)
        if status:
            self.state_db[STATE_STATUS] = len(self.state_db[STATE_EVENTS]) -1
        self._flush_state(flush)

    def setResult(self, outputs=None, resources=None, flush=True):
        if resources:
            self.state_db[STATE_UP_RESULT][STATE_UP_RESULT_OUTPUTS] = outputs
        if outputs:
            self.state_db[STATE_UP_RESULT][STATE_UP_RESULT_RESOURCES] = resources
        self._flush_state(flush)

    def set_hook_state(self, hook, op, op_data, flush=True):
        if not self.state_db[STATE_HOOKS_RESULT][hook].get(op, False):
            self.state_db[STATE_HOOKS_RESULT][hook][op] = {}
        self.state_db[STATE_HOOKS_RESULT][hook][op] = {**self.state_db[STATE_HOOKS_RESULT][hook][op], **op_data}        
        self._flush_state(flush)

    def store_get(self, key, value):
        try:
            return self.state_db[STATE_STORE][key]
        except KeyError:
            self.state_db[STATE_STORE][key] = value
            return value

    @staticmethod
    def timestamp():
        # utc='%H:%M:%S %d/%m/%Y-%Z'
        # return datetime.utcnow().strftime(utc)
        local = '%H:%M:%S %d/%m/%Y'
        return datetime.now().strftime(local)

    @property
    def status(self):
        last_status_event = self.state_db[STATE_EVENTS][self.state_db[STATE_STATUS]]
        return_status = {
            "Name": self.state_db[STATE_DEPLOYMENT_NAME],
            "Phase": self.state_db[STATE_PHASE],
            "Timestamp": self.state_db[STATE_LASTUPDATE],
            "ResourceGroup": self.state_db[STATE_RESOURCE_GROUP],
            "Status": last_status_event["status"],
            "StatusMessage": last_status_event["msg"],
            "Version": self.state_db['version'],
        }
        return return_status

    @property
    def events(self):
        return_events = []
        for event in reversed(self.state_db[STATE_EVENTS]):
            return_events.append({
                "Timestamp": event["timestamp"],
                "Phase": event["phase"],
                "Message": event["msg"],
                "Status": event["status"],
                "Hook": event["hook"],
            })
        return return_events

    @property
    def result_up(self):
        return self.state_db[STATE_UP_RESULT]

    @property
    def result_hooks(self):
        return self.state_db[STATE_HOOKS_RESULT]

    @property
    def state(self):
        return self.state_db
