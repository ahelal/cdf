""" Provisioner file """

import subprocess
import json
import os
from knack.util import CLIError
from knack.log import get_logger
from azext_cdf.utils import json_write_to_file
from azure.cli.command_modules.resource.custom import build_bicep_file
from azure.cli.command_modules.resource.custom import deploy_arm_template_at_resource_group, create_resource_group

_logger = get_logger(__name__)


def run_command(bin_path, args=[], interactive=False, cwd=None):
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


def run_arm_deployment(cmd, deployment_name, arm_template_file, resource_group, location, params=None, manage_resource_group=True, no_prompt=False, complete_deployment=False):
    """
    Deploy an ARM template

    Args:

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

def run_terraform_apply(cmd, terraform_dir, tmp_dir, resource_group, location, params=None, manage_resource_group=True, no_prompt=False):
    varsfile = os.path.join(tmp_dir,"terraformvars.json")
    if manage_resource_group:
        create_resource_group(cmd, rg_name=resource_group, location=location)
    if params:
        json_write_to_file(varsfile, params)

    # terraform apply -input=false -var-file input.json -auto-approve
    run_command("terraform", args=["init"], interactive=False, cwd=terraform_dir)

    args = ["apply", f"-input={no_prompt}", "-auto-approve"]
    if params:
        args.append("-var-file")
        args.append(varsfile)

    run_command("terraform", args=args, interactive=False, cwd=terraform_dir)
    # TODO fix return
    stdout, stderr = run_command("terraform", args=["output","-json"], interactive=False, cwd=terraform_dir)
    try:
        output = json.loads(stdout)
    except subprocess.CalledProcessError as error:
        context = f"Error while decoding json from terraform output. {error}"
        raise CLIError(error) from error
    output_resources = {}
    return output_resources, output

def run_terraform_destroy(cmd, terraform_dir, tmp_dir, resource_group, location, params=None, manage_resource_group=True, no_prompt=False):
    varsfile = os.path.join(tmp_dir,"terraformvars.json")
    if manage_resource_group:
        create_resource_group(cmd, rg_name=resource_group, location=location)
    if params:
        json_write_to_file(varsfile, params)

    run_command("terraform", args=["init"], interactive=False, cwd=terraform_dir)

    args = ["destroy", f"-input={no_prompt}", "-auto-approve"]
    if params:
        args.append("-var-file")
        args.append(varsfile)

    run_command("terraform", args=args, interactive=False, cwd=terraform_dir)

    return None, None
