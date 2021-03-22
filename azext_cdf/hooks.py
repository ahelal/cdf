from knack.util import CLIError
from azext_cdf.utils import json_load, is_equal_or_in
from knack.log import get_logger
from azext_cdf.parser import CONFIG_HOOKS, SECOND_PHASE
from azext_cdf.provisioner import run_command

logger = get_logger(__name__)
RECURSION_LIMIT = 5

def run_hook_lifecycle(cp, state, event):
    for hook in cp.data[CONFIG_HOOKS]:
        if is_equal_or_in(event, cp.data[CONFIG_HOOKS][hook]["lifecycle"]):
            run_hook(cp, state, [hook])

def run_hook(cp, state, hook_args, recursion_n=1):
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
        if op['type'] == "az":
            stdout, stderr = _run_az(hook_name, ops_name, op_args, hook_args[1:])
        elif op['type'] == "cmd":
            stdout, stderr = _run_cmd(hook_name, ops_name, op_args, hook_args[1:])
        elif op['type'] == "print":
            stdout, stderr = _run_print(hook_name, ops_name, op_args, hook_args[1:])
        elif op['type'] == "call":
            run_hook(cp, state, [op_args], recursion_n +1)
            stdout, stderr = "", ""

        if op.get("name", False):
            state.setHooksResult(hook=hook_name, op=op['name'], op_data={"stdout": stdout,"stderr": stderr}, flush=True)
            cp.updateHooksResult(state.result_hooks)

def _run_print(hook_name, ops_name, op_args, hook_args):
    stdout = f"Print {hook_name} | {ops_name}\n{op_args}"
    print(stdout)
    return stdout, ""

def _run_cmd(hook_name, ops_name, op_args, hook_args):
    if isinstance(op_args, str):
        op_args = op_args.split(" ")
    try:
        stdout, stder = run_command(op_args[0], op_args[1:])
    except Exception as e:
        raise CLIError(f"Failed during cmd execution in op '{ops_name}' in hook '{hook_name}'.\n{str(e)} ")
    return stdout, stder

def _run_az(hook_name, ops_name, op_args, hook_args):
    if isinstance(op_args, str):
        op_args = op_args.split(" ")
    try:
        stdout, stder = run_command("az", op_args)
    except Exception as e:
        raise CLIError(f"Failed during AZ execution in op '{ops_name}' in hook '{hook_name}'.\n{str(e)} ")
    stdout = json_load(stdout)
    return stdout, stder
    # logger.info(f"Running op {op['name']}")
