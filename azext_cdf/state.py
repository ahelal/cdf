''' Handeling the state file '''

from copy import deepcopy
from datetime import datetime
import semver
from knack.util import CLIError
from knack.log import get_logger
from azext_cdf.utils import json_write_to_file, file_exists, file_read_content, json_load, file_http_write_json_content, file_http_read_json_content
from azext_cdf.version import VERSION
# pylint: disable=W0401,W0614
from azext_cdf._def import *

_LOGGER = get_logger(__name__)


class State():
    ''' The state class '''

    def __init__(self, state_file):
        self.config_hooks = None
        if state_file.startswith('file://'):
            self.state_file = state_file[len("file://"):]
            self.state_url = None
        elif state_file.startswith('http://') or state_file.startswith('https://'):
            self.state_file = None
            self.state_url = state_file
        else:
            raise CLIError(f"Error unsupported schmea for state file '{state_file}' supported schemas 'file://'|'https://'|'http://'")
        if self._read_state():
            return
        # New state file
        self.state_db = {
            STATE_DEPLOYMENT_NAME: None,
            STATE_PHASE: STATE_PHASE_UNKNOWN,
            STATE_LASTUPDATE: self._timestamp(),
            STATE_STATUS: -1,
            STATE_EVENTS: [],
            STATE_VERSION: VERSION,
            STATE_STORE: {},
            STATE_HOOKS_RESULT: {},
            STATE_RESOURCE_GROUP: None,
            STATE_UP_RESULT: {STATE_UP_RESULT_OUTPUTS: {}, STATE_UP_RESULT_RESOURCES: {}},
        }
        self._setup_hooks_reference()
        self.add_event("Created a state file", status=STATE_STATUS_UNKNOWN, flush=True)

    def setup(self, deployment_name, resource_group, config_hooks):
        ''' Check if resource group is mapping to state else raise an error'''

        self.config_hooks = config_hooks
        if self.state_db[STATE_RESOURCE_GROUP] is None:
            self.state_db[STATE_RESOURCE_GROUP] = resource_group
        elif resource_group == self.state_db[STATE_RESOURCE_GROUP]:
            pass
        elif self.state_db[STATE_PHASE] == STATE_PHASE_UNKNOWN or self.state_db[STATE_PHASE] == STATE_PHASE_DOWN:
            pass
        else:
            raise CLIError("Resource group already provisioned '{}' requested '{}', Can't change resource group before destroying.".format(self.state_db[STATE_RESOURCE_GROUP], resource_group))

        if self.state_db[STATE_DEPLOYMENT_NAME] is None:
            self.state_db[STATE_DEPLOYMENT_NAME] = deployment_name
        elif self.state_db[STATE_DEPLOYMENT_NAME] == deployment_name:
            pass
        elif self.state_db[STATE_PHASE] == STATE_PHASE_UNKNOWN or self.state_db[STATE_PHASE] == STATE_PHASE_DOWN:
            pass
        else:
            raise CLIError("state error seems you have changed the deployment name to '{}', the state has this deployment name: {}".format(self.state_db[STATE_DEPLOYMENT_NAME], deployment_name))
        self._version_compare()
        self._setup_hooks_reference()
        self._flush_state()

    def _version_compare(self):
        ''' Check if state version '''
        state_version = semver.parse_version_info(self.state_db["version"])
        cli_version = semver.parse_version_info(VERSION)

        if state_version < cli_version:  # state is less then cli
            _LOGGER.warning("Your state file is out date: state version %s CDF version %s. Run `up -r` to rewrite state", state_version, VERSION)
        elif state_version > cli_version:  # state is more then cli
            _LOGGER.warning("Your CDF extension is outdate: state version %s CLI version %s. Upgrade extension", state_version, VERSION)
        elif state_version == cli_version:  # state is same as cli
            pass

    def _setup_hooks_reference(self):
        # TODO to complex refactor
        # hooks/ops in state db but not config_db
        current_state_db_hooks = deepcopy(self.state_db[STATE_HOOKS_RESULT])
        for state_hook in current_state_db_hooks:
            if state_hook in self.config_hooks:
                for state_op in current_state_db_hooks[state_hook]:
                    if state_op[0] == "_":
                        pass  # ignore _
                    elif state_op not in self.config_hooks[state_hook]:
                        self.state_db[STATE_HOOKS_RESULT][state_hook].pop(state_op)
            else:
                self.state_db[STATE_HOOKS_RESULT].pop(state_hook)  # remove hook outdate

        # hooks/ops in config db but not config_db
        if not self.config_hooks:
            return
        for config_hook in self.config_hooks:
            if config_hook not in self.state_db[STATE_HOOKS_RESULT]:
                self.state_db[STATE_HOOKS_RESULT][config_hook] = {}
            for config_op in self.config_hooks[config_hook]:
                if config_op not in self.state_db[STATE_HOOKS_RESULT][config_hook]:
                    self.state_db[STATE_HOOKS_RESULT][config_hook][config_op] = {}

    def _read_state(self):
        if self.state_file and file_exists(self.state_file):
            # state file exists
            try:
                state_str = file_read_content(self.state_file)
                self.state_db = json_load(state_str)
            except CLIError as error:
                raise CLIError(f"Error while reading/decoding state '{self.state_file}' Did you try to change it manually. {str(error)}") from error
            return True
        if self.state_url:  # TODO need to add check if path
            self.state_db = file_http_read_json_content(self.state_url)
        return False

    def _flush_state(self, flush=True):
        if not flush:
            return
        if self.state_file:
            json_write_to_file(self.state_file, self.state_db)
        elif self.state_url:
            file_http_write_json_content(self.state_url, self.state_db)

    @staticmethod
    def _timestamp():
        ''' Current timestamp '''
        # str_time ='%H:%M:%S %d/%m/%Y-%Z'  # utc
        str_time = "%H:%M:%S %d/%m/%Y"  # local time
        return datetime.now().strftime(str_time)

    def transition_to_phase(self, phase):
        """An alias to add event to write state transition"""

        self.add_event(f"Transitioning to {phase}", phase=phase, status=STATE_STATUS_PENDING, flush=True)

    def completed_phase(self, phase, status, msg=""):
        """An alias to add event to write phase state"""

        if status == STATE_STATUS_SUCCESS:
            self.add_event(f"Successfully reached {phase}. { msg }", phase=phase, status=STATE_STATUS_SUCCESS, flush=True)
        elif status == STATE_STATUS_ERROR:
            self.add_event(f"Errored during {phase}. { msg }", status=STATE_STATUS_ERROR, flush=True)
        elif status == STATE_STATUS_FAILED:
            self.add_event(f"Failed during {phase}. { msg }", status=STATE_STATUS_FAILED, flush=True)

    def add_event(self, msg, status=None, phase=None, hook=None, flush=True):
        ''' Add an event to the events state '''

        if phase:
            self.state_db[STATE_PHASE] = phase
        event = {"timestamp": self._timestamp(), "phase": self.state_db[STATE_PHASE], "msg": msg, "status": status, "hook": hook}
        self.state_db[STATE_EVENTS].append(event)
        if status:
            self.state_db[STATE_STATUS] = len(self.state_db[STATE_EVENTS]) - 1
        self._flush_state(flush)

    def set_result(self, outputs=None, resources=None, flush=True):
        ''' Write outputs and resources to state'''

        if outputs:
            self.state_db[STATE_UP_RESULT][STATE_UP_RESULT_OUTPUTS] = outputs
        if resources:
            self.state_db[STATE_UP_RESULT][STATE_UP_RESULT_RESOURCES] = resources
        self._flush_state(flush)

    def set_hook_state(self, hook, op_name, op_data, flush=True):
        ''' Write hook output to the state file '''

        # TODO add state success or failure
        if not self.state_db[STATE_HOOKS_RESULT][hook].get(op_name, False):
            self.state_db[STATE_HOOKS_RESULT][hook][op_name] = {}
        self.state_db[STATE_HOOKS_RESULT][hook][op_name] = {**self.state_db[STATE_HOOKS_RESULT][hook][op_name], **op_data}
        self._flush_state(flush)

    def store_get(self, key, value):
        ''' Get variable from store in state'''

        try:
            return self.state_db[STATE_STORE][key]
        except KeyError:
            self.state_db[STATE_STORE][key] = value
            return value

    @property
    def status(self):
        ''' Return status from state file'''

        last_status_event = self.state_db[STATE_EVENTS][self.state_db[STATE_STATUS]]
        return_status = {
            "Name": self.state_db[STATE_DEPLOYMENT_NAME],
            "Phase": self.state_db[STATE_PHASE],
            "Timestamp": self.state_db[STATE_LASTUPDATE],
            "ResourceGroup": self.state_db[STATE_RESOURCE_GROUP],
            "Status": last_status_event["status"],
            "StatusMessage": last_status_event["msg"],
            "version": self.state_db["version"],
        }
        return return_status

    @property
    def events(self):
        ''' Return the events from state file '''

        return_events = []
        for event in reversed(self.state_db[STATE_EVENTS]):
            return_events.append(
                {
                    "Timestamp": event["timestamp"],
                    "Phase": event["phase"],
                    "Message": event["msg"],
                    "Status": event["status"],
                    "Hook": event["hook"],
                }
            )
        return return_events

    @property
    def result_up(self):
        ''' Return the result dict (output and resources)'''

        return self.state_db[STATE_UP_RESULT]

    @property
    def result_hooks(self):
        ''' Return the results for all hooks'''

        return self.state_db[STATE_HOOKS_RESULT]

    @property
    def state(self):
        ''' Return the state dict '''

        return self.state_db
