""" Provisioner file """

import subprocess
import json
import os
from knack.util import CLIError
from knack.log import get_logger
from azure.cli.command_modules.resource.custom import build_bicep_file
from azure.cli.command_modules.resource.custom import deploy_arm_template_at_resource_group, create_resource_group, delete_resource, show_resource
from azure.cli.core.commands.client_factory import get_subscription_id
from msrestazure.azure_exceptions import CloudError

from azext_cdf.utils import find_the_right_file, find_the_right_dir
from azext_cdf.parser import CONFIG_PARAMS
from azext_cdf.utils import json_write_to_file

_logger = get_logger(__name__)

def _resource_group_exists(cmd, resource_group):
    try:
        show_resource(cmd, resource_ids=[f"/subscriptions/{get_subscription_id(cmd.cli_ctx)}/resourceGroups/{resource_group}"])
    except CloudError as error:
        if 'ResourceGroupNotFound' in str(error):
            return False
        raise CLIError from error
    else:
        return True

def de_provision(cmd, cobj):
    if cobj.provisioner == "bicep" or cobj.provisioner == "arm":
        _empty_deployment(cmd, cobj)
    elif cobj.provisioner == "terraform":
        # Run template interpolate
        run_terraform_destroy(
            cmd,
            deployment_name=cobj.name,
            terraform_dir=find_the_right_dir(cobj.up_location, cobj.config_dir),
            tmp_dir=cobj.tmp_dir,
            resource_group=cobj.resource_group_name,
            location=cobj.location,
            params=cobj.data[CONFIG_PARAMS],
            manage_resource_group=cobj.managed_resource,
            no_prompt=False
        )
    cobj.state.set_result(outputs={}, resources={}, flush=True)

    if cobj.managed_resource and _resource_group_exists(cmd, cobj.resource_group_name):
        delete_resource(cmd, resource_ids=[f"/subscriptions/{get_subscription_id(cmd.cli_ctx)}/resourceGroups/{cobj.resource_group_name}"])


def provision(cmd, cobj):
    output_resources, outputs = None, None
    # Run template interpolate
    cobj.interpolate_pre_up()
    if cobj.provisioner == "bicep":
        output_resources, outputs = run_bicep(
            cmd,
            deployment_name=cobj.name,
            bicep_file=find_the_right_file(cobj.up_location, "bicep", "*.bicep", cobj.config_dir),
            tmp_dir=cobj.tmp_dir,
            resource_group=cobj.resource_group_name,
            location=cobj.location,
            params=cobj.data[CONFIG_PARAMS],
            manage_resource_group=cobj.managed_resource,
            no_prompt=False,
            complete_deployment=cobj.deployment_mode,
        )
    elif cobj.provisioner == "arm":
        output_resources, outputs =  run_arm_deployment(
            cmd,
            deployment_name=cobj.name,
            arm_template_file=find_the_right_file(cobj.up_location, "arm", "*.json", cobj.config_dir),
            resource_group=cobj.resource_group_name,
            location=cobj.location,
            params=cobj.data[CONFIG_PARAMS],
            manage_resource_group=cobj.managed_resource,
            no_prompt=False,
            complete_deployment=cobj.deployment_mode,
        )
    elif cobj.provisioner == "terraform":
        output_resources, outputs = run_terraform_apply(
            cmd,
            deployment_name=cobj.name,
            terraform_dir=find_the_right_dir(cobj.up_location, cobj.config_dir),
            tmp_dir=cobj.tmp_dir,
            resource_group=cobj.resource_group_name,
            location=cobj.location,
            params=cobj.data[CONFIG_PARAMS],
            manage_resource_group=cobj.managed_resource,
            no_prompt=False
        )
    cobj.state.set_result(outputs=outputs, resources=output_resources, flush=True)

def run_command(bin_path, args=None, interactive=False, cwd=None):
    """
    Run CLI commands
    Returns: stdout, stderr  strings
    Exceptions: raise CLIError on execution error
    """
    process = None
    stdout = None
    stderr = None
    try:
        cmd_args = [rf"{bin_path}"] + args
        _logger.debug(" Running a command %s", cmd_args)
        if interactive:
            subprocess.check_call(cmd_args, cwd=cwd)
            return "", ""

        process = subprocess.run(cmd_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd, check=False)
        process.check_returncode()
        return process.stdout.decode("utf-8"), process.stderr.decode("utf-8")
    except subprocess.CalledProcessError as error:
        if process:
            stdout = process.stdout.decode('utf-8')
            stderr = process.stderr.decode('utf-8')
        context = f"Run command error. {str(error)}\nstdout: {stdout}\nstderr: {stderr}"
        if "process" in locals():
            context = f"{context}\n{process.stderr.decode('utf-8')}"
        raise CLIError(context) from error


def run_bicep(cmd, deployment_name, bicep_file, tmp_dir, resource_group, location, params=None, manage_resource_group=True, no_prompt=False, complete_deployment=False):
    '''
    Deploy an bicep files
    Returns:
        output_resources
        output
    '''
    arm_template_file = f"{tmp_dir}/targetfile.json"
    _logger.debug(" Building bicep file in tmp dir %s", arm_template_file)
    # build_bicep_file(cmd, [f"{bicep_file}", "--outfile", f"{arm_template_file}"])
    build_bicep_file(cmd, bicep_file, outfile=arm_template_file)

    return run_arm_deployment(
        cmd,
        deployment_name=deployment_name,
        arm_template_file=arm_template_file,
        resource_group=resource_group,
        location=location,
        params=params,
        manage_resource_group=manage_resource_group,
        no_prompt=no_prompt,
        complete_deployment=complete_deployment,
    )

def _empty_deployment(cmd, cobj):
    # TODO check deployment exists before doing an empty deployment
    empty_deployment = {
        "$schema": "http://schema.management.azure.com/schemas/2015-01-01/deploymentTemplate.json#",
        "contentVersion": "1.0.0.0",
        "parameters": {},
        "variables": {},
        "resources": [],
        "outputs": {},
    }
    json_write_to_file(f"{cobj.tmp_dir}/empty_deployment.json", empty_deployment)
    try:
        deploy_arm_template_at_resource_group(
            cmd, resource_group_name=cobj.resource_group_name, template_file=f"{cobj.tmp_dir}/empty_deployment.json", deployment_name=cobj.name, mode="Complete", no_wait=False
        )
    except CLIError as error:
        if "ResourceGroupNotFound" in str(error):
            pass
        else:
            raise CLIError(error) from error


def run_arm_deployment(cmd, deployment_name, arm_template_file, resource_group, location, params=None, manage_resource_group=True, no_prompt=False, complete_deployment=False):
    """
    Deploy an ARM template
    Returns:
        output_resources
        output
    """

    if manage_resource_group:
        create_resource_group(cmd, rg_name=resource_group, location=location)
    parameters = []
    for key, value in params.items():
        params_obj = [f"{key}={value}"]
        parameters.append(params_obj)

    if complete_deployment:
        mode = "Complete"
    else:
        mode = "Incremental"

    deployment = deploy_arm_template_at_resource_group(
        cmd, resource_group_name=resource_group, template_file=arm_template_file, deployment_name=deployment_name, mode=mode, no_prompt=no_prompt, parameters=parameters, no_wait=False
    )

    output_resources = deployment.result().as_dict().get("properties", {}).get("output_resources", {})
    output = deployment.result().as_dict().get("properties", {}).get("outputs", {})
    return output_resources, output

def run_terraform_apply(cmd, deployment_name, terraform_dir, tmp_dir, resource_group, location, params=None, manage_resource_group=True, no_prompt=False):
    ''' Run terraform apply '''

    varsfile = os.path.join(tmp_dir,"terraformvars.json")
    if manage_resource_group:
        create_resource_group(cmd, rg_name=resource_group, location=location)
    if params:
        json_write_to_file(varsfile, params)

    # terraform apply -input=false -var-file input.json -auto-approve
    run_command("terraform", args=["init"], interactive=False, cwd=terraform_dir)

    args = ["apply", f"-input={no_prompt}", f"-state={deployment_name}.tfstate", "-auto-approve"]
    if params:
        args.append("-var-file")
        args.append(varsfile)

    run_command("terraform", args=args, interactive=False, cwd=terraform_dir)
    # TODO fix return
    stdout, _ = run_command("terraform", args=["output","-json"], interactive=False, cwd=terraform_dir)
    try:
        output = json.loads(stdout)
    except subprocess.CalledProcessError as error:
        raise CLIError(f"Error while decoding json from terraform output. Error: {error}") from error
    output_resources = {}
    return output_resources, output

def run_terraform_destroy(cmd, deployment_name, terraform_dir, tmp_dir, resource_group, location, params=None, manage_resource_group=True, no_prompt=False):
    ''' Run terraform destroy '''

    varsfile = os.path.join(tmp_dir,"terraformvars.json")
    if manage_resource_group:
        create_resource_group(cmd, rg_name=resource_group, location=location)
    if params:
        json_write_to_file(varsfile, params)

    run_command("terraform", args=["init"], interactive=False, cwd=terraform_dir)
    args = ["destroy", f"-input={no_prompt}", f"-state={deployment_name}.tfstate", "-auto-approve"]
    if params:
        args.append("-var-file")
        args.append(varsfile)

    return run_command("terraform", args=args, interactive=False, cwd=terraform_dir)
