from knack.util import CLIError
from azext_cdf.utils import json_load, is_equal_or_in, file_read_content, file_write_content
from knack.log import get_logger
from azext_cdf.parser import CONFIG_HOOKS, SECOND_PHASE
from azext_cdf.provisioner import run_command
import os
import stat
import shlex

logger = get_logger(__name__)
RECURSION_LIMIT = 5

def run_hook_lifecycle(cp, state, event):
    for hook in cp.data[CONFIG_HOOKS]:
        if is_equal_or_in(event, cp.data[CONFIG_HOOKS][hook]["lifecycle"]):
            run_hook(cp, state, [hook])

def run_hook(cp, state, hook_args, recursion_n=1):
    hook_name = hook_args[0]
    state.addEvent(f"Running hook. hook args '{hook_args[1:]}'", hook=hook_name, flush=True)
    try:
        _run_hook(cp, state, hook_args, recursion_n=1)
    except CLIError as e:
        state.addEvent(f"Error during hook execution {str(e)}", hook=hook_name, flush=True)
        raise

    state.addEvent(f"Finished running hook", hook=hook_name, flush=True)

def _run_hook(cp, state, hook_args, recursion_n=1):
    hook_name = hook_args[0]
    if recursion_n > RECURSION_LIMIT:
        raise CLIError(f"Call recursion limit reached {recursion_n - 1}")
        
    logger.info(f"Entering hook {hook_name} and hook_args {hook_args}")
    try:
        hook = cp.data[CONFIG_HOOKS][hook_name]
    except KeyError as e:
        raise CLIError(f"Unknown hook name '{hook_name}'.\n{str(e)} ")

    n = 0
    ops = {}
    for op in hook['ops']:
        n += 1
        ops_name = op.get("name", op.get("descrpition", f"#{n}"))
        if is_equal_or_in("",  op['platform']):
            pass # all platforms
        elif is_equal_or_in(cp.platform,  op['platform']):
            pass # my platfrom
        else:
            # Skip 
            continue

        op_args = cp.interpolate(phase=SECOND_PHASE, 
                                        template=op['args'], 
                                        context=f"az-cli op interpolation '{ops_name}' in hook '{hook_name}'")
        interactive = op.get("interactive", False)
        if op['type'] == "az":
            stdout, stderr = _run_az(hook_name, ops_name, op_args, hook_args[1:])
        elif op['type'] == "cmd":
            stdout, stderr = _run_cmd(hook_name, ops_name, op_args, hook_args[1:], interactive)
        elif op['type'] == "script":
            stdout, stderr = _run_script(hook_name, ops_name, op_args, hook_args[1:], cp)
        elif op['type'] == "print":
            stdout, stderr = _run_print(hook_name, ops_name, op_args, hook_args[1:])
        elif op['type'] == "call":
            _run_hook(cp, state, [op_args], recursion_n +1)
            stdout, stderr = "", ""

        if op.get("name", False):
            state.setHooksResult(hook=hook_name, op=op['name'], op_data={"stdout": stdout,"stderr": stderr}, flush=True)
            cp.updateHooksResult(state.result_hooks)

def _run_print(hook_name, ops_name, op_args, hook_args):
    stdout = f"Print {hook_name} | {ops_name}\n{op_args}"
    print(stdout)
    return stdout, ""

def _run_cmd(hook_name, ops_name, op_args, hook_args, interactive=False):
    if isinstance(op_args, str):
        op_args = shlex.split(op_args)
    try:
        stdout, stder = run_command(op_args[0], op_args[1:], interactive=interactive)
    except Exception as e:
        raise CLIError(f"Failed during cmd execution in op '{ops_name}' in hook '{hook_name}'.\n{str(e)} ")
    return stdout, stder

def _run_az(hook_name, ops_name, op_args, hook_args):
    if isinstance(op_args, str):
        op_args = shlex.split(op_args)
    try:
        stdout, stder = run_command("az", op_args)
    except Exception as e:
        raise CLIError(f"Failed during AZ execution in op '{ops_name}' in hook '{hook_name}'.\n{str(e)} ")
    # stdout = json_load(stdout)
    return stdout, stder
    # logger.info(f"Running op {op['name']}")

def _run_script(hook_name, ops_name, op_args, hook_args, cp):
    if isinstance(op_args, str):
        op_args = shlex.split(op_args)
    filename = op_args[0]
    target_file = f"{cp.tmp_dir}/{os.path.basename(filename)}"
    content = file_read_content(op_args[0])
    content = cp.interpolate(SECOND_PHASE,content, f"Interplating script op {op_args[0]}")
    file_write_content(target_file, content)
    # os.chmod(target_file, stat.st_mode | stat.S_IEXEC) # make file exec
    os.chmod(target_file, stat.S_IRUSR | stat.S_IEXEC | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH) # make file exec
    op_args[0] = target_file
    return _run_cmd(hook_name, ops_name, op_args, hook_args)
