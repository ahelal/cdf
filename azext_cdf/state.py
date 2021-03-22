from azext_cdf.utils import json_write_to_file, file_exits, file_read_content, json_load
from datetime import datetime
from knack.util import CLIError
from copy import deepcopy

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
STATE_PHASE = "phase"
STATE_LASTUPDATE = "lastUpdate"
STATE_STATUS = "status"
STATE_EVENTS = "events"
STATE_UP_RESULT = "result"
STATE_UP_RESULT_OUTPUTS = "outputs"
STATE_UP_RESULT_RESOURCES = "resources"
STATE_HOOKS_RESULT = "hooks"

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
                STATE_HOOKS_RESULT: {},
                STATE_UP_RESULT: {
                    STATE_UP_RESULT_OUTPUTS: {},
                    STATE_UP_RESULT_RESOURCES: {}
                }
            }
            self._setup_hooks_reference()
            self.addEvent("Created state file", status=STATE_STATUS_UNKNOWN, flush=True)
            return
        
        # file exists
        try:
            state_str = file_read_content(self.state_file)
            self.state_db = json_load(state_str)
        except CLIError as e:
            raise CLIError(f"Error while reading/decoding state '{self.state_file}' Did you try to change it manually. {str(e)}")
        if not self.state_db[STATE_DEPLOYMENT_NAME] == name:
            raise CLIError("state error seems you have changed the delpoyment name to '{}', the state has this deployment name: {}".format(self.state_db[STATE_DEPLOYMENT_NAME], name))
        self._setup_hooks_reference()
    
    def _setup_hooks_reference(self):
        # hooks/ops in state db but not config_db
        current_state_db_hooks = deepcopy(self.state_db[STATE_HOOKS_RESULT])
        for state_hook in current_state_db_hooks:
            if state_hook in self.config_hooks:
                for state_op in current_state_db_hooks[state_hook]:
                    if not state_op in self.config_hooks[state_hook]:
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

    def _flushState(self, flush=True):
        if flush:
            json_write_to_file(self.state_file, self.state_db)

    def transitionToPhase(self, phase):
        self.addEvent(f"Transitioning to {phase}", phase=phase, status=STATE_STATUS_PENDING, flush=True)

    def completedPhase(self, phase, status, msg=""):
        if status == STATE_STATUS_SUCCESS:
            self.addEvent(f"Successfully reached {phase}. { msg }", phase=phase, status=STATE_STATUS_SUCCESS, flush=True)
        elif status == STATE_STATUS_ERROR:
            self.addEvent(f"Errored during {phase}. { msg }", status=STATE_STATUS_ERROR, flush=True)
        elif status == STATE_STATUS_FAILED:
            self.addEvent(f"Failed during {phase}. { msg }", status=STATE_STATUS_FAILED, flush=True)

    def addEvent(self, msg, status=None, phase=None, flush=True):
        if phase:
            self.state_db[STATE_PHASE] = phase
        event = {"timestamp": self.timestamp(), "phase": self.state_db[STATE_PHASE], "msg": msg, "status": status}
        self.state_db[STATE_EVENTS].append(event)
        if status:
            self.state_db[STATE_STATUS] = len(self.state_db[STATE_EVENTS]) -1
        self._flushState(flush)

    def setResult(self, outputs=None, resources=None, flush=True):
        if resources:
            self.state_db[STATE_UP_RESULT][STATE_UP_RESULT_OUTPUTS] = outputs
        if outputs:
            self.state_db[STATE_UP_RESULT][STATE_UP_RESULT_RESOURCES] = resources
        self._flushState(flush)

    def setHooksResult(self, hook, op, op_data, flush=True):
        self.state_db[STATE_HOOKS_RESULT][hook][op] = op_data
        self._flushState(flush)

    @staticmethod
    def timestamp():
        # utc='%H:%M:%S %d/%m/%Y-%Z'
        # return datetime.utcnow().strftime(utc)
        local='%H:%M:%S %d/%m/%Y'
        return datetime.now().strftime(local)

    @property
    def status(self):
        last_status_event = self.state_db[STATE_EVENTS][self.state_db[STATE_STATUS]]
        return_status = {
                "Name": self.state_db[STATE_DEPLOYMENT_NAME],
                "Phase": self.state_db[STATE_PHASE],
                "Timestamp": self.state_db[STATE_LASTUPDATE],
                "Status": last_status_event["status"],
                "StatusMessage": last_status_event["msg"],
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