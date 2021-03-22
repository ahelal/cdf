import os
import time
import sys

from knack.util import CLIError
from knack.log import get_logger
from azure.cli.command_modules.resource.custom import deploy_arm_template_at_resource_group, create_resource_group, get_deployment_at_resource_group, delete_resource
from azure.cli.command_modules.resource.custom import build_bicep_file, run_bicep_command
from azure.cli.core.util import user_confirmation
from azure.cli.core import __version__ as azure_cli_core_version
from azure.cli.core.commands.client_factory import get_subscription_id
from azure.cli.core.commands.parameters import resource_group_name_type
from azext_cdf.parser import ConfigParser, CONFIG_UP, CONFIG_RG, CONFIG_PARAMS, CONFIG_NAME, CONFIG_LOCATION, CONFIG_TMP, RUNTIME_CONFIG_DIR_KEY
from azext_cdf.parser import LIFECYCLE_PRE_UP, LIFECYCLE_POST_UP, LIFECYCLE_PRE_DOWN, LIFECYCLE_POST_DOWN,LIFECYCLE_PRE_TEST, LIFECYCLE_POST_TEST, LIFECYCLE_ALL
from azext_cdf.VERSION import VERSION
from azext_cdf.utils import json_write_to_file, find_the_right_file, dir_change_working, json_load, file_read_content, file_exits
from azext_cdf.hooks import run_hook, run_hook_lifecycle
from azext_cdf.state import State
from azext_cdf.state import STATE_PHASE_GOING_UP, STATE_PHASE_UP, STATE_PHASE_TESTED, STATE_PHASE_TESTING, STATE_PHASE_DOWN, STATE_PHASE_GOING_DOWN
from azext_cdf.state import STATE_STATUS_UNKNOWN, STATE_STATUS_SUCCESS, STATE_STATUS_ERROR, STATE_STATUS_FAILED, STATE_STATUS_PENDING
from azext_cdf.provisioner import run_bicep

from collections import OrderedDict
logger = get_logger(__name__)

CONFIG_DEFAULT=".cdf.yml"

def _init_config(config, rtmp=False, working_dir=None):
    if working_dir:
        dir_change_working(working_dir)
    cp = ConfigParser(config, rtmp)
    state = State(cp.state_file, cp.name, cp.hooks_ops)
    cp.updateResult(state.result_up)
    cp.updateHooksResult(state.result_hooks)
    return cp, state

def test_handler(cmd, config=CONFIG_DEFAULT, working_dir=None):
    #TODO
    print("test handler")

def init_handler(cmd, config=CONFIG_DEFAULT, force=False, example=False, working_dir=None):
    #TODO
    print(f'init {force} {example}')

def hook_handler(cmd, config=CONFIG_DEFAULT, hook_args=[], working_dir=None, confirm=False):
    cp, state = _init_config(config, False, working_dir)
    if len(hook_args) == 0:
       return cp.hook_table

    hook = hook_args[0] # hook is the first arg
    hooks = cp.hook_names
    if hook not in hooks:
        raise CLIError(f"unknown hook name '{hook}', Supported hooks '{hooks}")
    status = state.status

    if confirm:
        pass
    elif not status['Phase'] == STATE_PHASE_UP: 
        user_confirmation(f"You want to run a hook when the phase is not up '{status['Phase']}'. Are you sure ?")
    elif not status['Status'] == STATE_STATUS_SUCCESS:
        user_confirmation(f"You want to run a hook when the last status is not success '{status['Phase']}'. Are you sure ?")

    run_hook(cp, state, hook_args)

def status_handler(cmd, config=CONFIG_DEFAULT, events=False, working_dir=None):
    cp, state = _init_config(config, False, working_dir)
    output_status = {}
    if events:
        output_status['events'] = state.events
    else:
        output_status = state.status
    return output_status

def debug_version_handler(cmd, config=CONFIG_DEFAULT, working_dir=None):
    return OrderedDict([
            ('CDF', VERSION),
            ('bicep', run_bicep_command(["--version"], auto_install=False).strip("\n")),
            ('az-cli', azure_cli_core_version),
            ('python', sys.version),
        ])

def debug_config_handler(cmd, config=CONFIG_DEFAULT, working_dir=None):
    cp, _ = _init_config(config, False, working_dir)
    return cp.config

def debug_state_handler(cmd, config=CONFIG_DEFAULT, working_dir=None):
    cp, state = _init_config(config, False, working_dir)
    return state.state

def debug_result_handler(cmd, config=CONFIG_DEFAULT, working_dir=None):
    cp, state = _init_config(config, False, working_dir)
    return state.result_up

def debug_deployment_error_handler(cmd, config=CONFIG_DEFAULT, working_dir=None):
    cp, state = _init_config(config, False, working_dir)
    deployment_show = []
    if cp.provisioner == 'bicep':
        if not file_exits(f"{cp.tmp_dir}/targetfile.json"):
            raise CLIError(f"{cp.tmp_dir}/targetfile.json does not exisit please run up first")
        arm_deployment = json_load(file_read_content(f"{cp.tmp_dir}/targetfile.json"))
        deployments_status = []
        deployment = _check_deployment_error(cmd, resource_group_name=cp.resource_group_name, deployment_name=cp.name, type='Microsoft.Resources/deployments')
        if  deployment:
            deployments_status.append(deployment)

        for d in arm_deployment['resources']:
            deployment = _check_deployment_error(cmd, resource_group_name=cp.resource_group_name, deployment_name=d['name'], type=d['type'] )
            if deployment:
                deployments_status.append(deployment)
        return deployments_status

def debug_interpolate_handler(cmd, config=CONFIG_DEFAULT, working_dir=None, phase=2):
    cp, state = _init_config(config, False, working_dir)
    line=""
    print("Type your jinj2 expression.")
    print("to exit type 'quit' or 'exit' or 'ctrl+c'.")
    while not line.lower() in ("quit","exit"):
        print("> ", end='')
        try:
            line = input()
            if line == '':
                break
            print(cp.interpolate(phase=phase, template=line))
        except EOFError:
            return
        except CLIError as e:
            print(f"Error : {str(e)}")

def _check_deployment_error(cmd, resource_group_name, deployment_name, type):
    deployment_status = {}
    if not type == 'Microsoft.Resources/deployments':
        return deployment_status
    deployment = get_deployment_at_resource_group(cmd, resource_group_name=resource_group_name, deployment_name=deployment_name)
    properties = deployment.as_dict().get('properties')
    if properties.get("provisioning_state") == 'Failed':
        error = properties.get("error")
        deployment_status.update({"error": error, "name": deployment_name})
    return deployment_status

def down_handler(cmd, config=CONFIG_DEFAULT, rtmp=False, working_dir=None):
    cp, state = _init_config(config, rtmp, working_dir)
    state.transitionToPhase(STATE_PHASE_GOING_DOWN)
    run_hook_lifecycle(cp, state, LIFECYCLE_PRE_DOWN)
    try:
        if cp.provisioner == 'bicep':
            _down_bicep(cmd, cp)
    except CLIError as e:
        state.addEvent(f"Errored during down phase: {str(e)}", STATE_STATUS_ERROR)
        raise CLIError(e)
    except Exception as e:
        state.addEvent(f"General error during diwb phase: {str(e)}", STATE_STATUS_ERROR)
        raise
    
    try:
        if cp.managed_resource:
            delete_resource(cmd, resource_ids=[f"/subscriptions/{get_subscription_id(cmd.cli_ctx)}/resourceGroups/{cp.resource_group_name}"])
    except Exception as e:
        if not "failed to be deleted" in str(e):
            raise e

    state.setResult(outputs={}, resources={}, flush=True)
    state.completedPhase(STATE_PHASE_DOWN, STATE_STATUS_SUCCESS, msg="")
    run_hook_lifecycle(cp, state, LIFECYCLE_POST_DOWN)

def _down_bicep(cmd, cp):
    #TODO check deployment exisits before doing an empty deployment
    empty_deployment = {
        "$schema": "http://schema.management.azure.com/schemas/2015-01-01/deploymentTemplate.json#",
        "contentVersion": "1.0.0.0",
        "parameters": {},
        "variables": {},
        "resources": [],
        "outputs": {}
    }
    json_write_to_file(f"{cp.tmp_dir}/empty_deployment.json", empty_deployment)
    try:
        deployment = deploy_arm_template_at_resource_group(cmd, 
                                                       resource_group_name=cp.resource_group_name, 
                                                       template_file=f"{cp.tmp_dir}/empty_deployment.json", 
                                                       deployment_name=cp.data[CONFIG_NAME],
                                                       mode="Complete",
                                                       no_wait=False)
    except CLIError as e:
        if "ResourceGroupNotFound" in str(e):
            pass
        else:
            raise CLIError(e)
    
def up_handler(cmd, config=CONFIG_DEFAULT, rtmp=False, prompt=False, working_dir=None):
    cp, state = _init_config(config, rtmp, working_dir)
    state.transitionToPhase(STATE_PHASE_GOING_UP)
    run_hook_lifecycle(cp, state, LIFECYCLE_PRE_UP)
    try:
        if cp.provisioner == 'bicep':
            output_resources, outputs= run_bicep(cmd, 
                        deployment_name=cp.data[CONFIG_NAME],
                        bicep_file= find_the_right_file(cp.up_file, 'bicep', '*.bicep', cp.firstPhaseVars[RUNTIME_CONFIG_DIR_KEY]), 
                        tmp_dir=cp.tmp_dir,
                        resource_group=cp.resource_group_name, 
                        location=cp.location, 
                        params=cp.data[CONFIG_PARAMS],
                        manage_resource_group=cp.managed_resource,
                        no_prompt=False)

    except CLIError as e:
        state.addEvent(f"Errored during up phase: {str(e)}", STATE_STATUS_ERROR)
        raise CLIError(e)
    except Exception as e:
        state.addEvent(f"General error during up phase: {str(e)}", STATE_STATUS_ERROR)
        raise

    state.setResult(outputs=outputs, resources=output_resources, flush=True)
    state.completedPhase(STATE_PHASE_UP, STATE_STATUS_SUCCESS, msg="")
    run_hook_lifecycle(cp, state, LIFECYCLE_POST_UP)
    # cp.updateResult(outputs=outputs, resources=output_resources)
