""" Handle hooks execution """

import os
import stat

from knack.util import CLIError
from knack.log import get_logger
from azext_cdf.utils import is_equal_or_in, file_read_content, file_write_content, run_command, convert_to_shlex_arg
from azext_cdf._def import CONFIG_HOOKS, SECOND_PHASE, RUNTIME_RUN_ONCE, CONFIG_TYPE, CONFIG_NAME, CONFIG_ARGS

_LOGGER = get_logger(__name__)

RECURSION_LIMIT = 5


def run_hook_lifecycle(cobj, event):
    """
    Loop through defined hooks and run all hooks attached to event.
    Returns: None
    """
    for hook_name in cobj.data[CONFIG_HOOKS]:
        if is_equal_or_in(event, cobj.data[CONFIG_HOOKS][hook_name]["lifecycle"]):
            _LOGGER.info("Hook event:%s triggered for hook:%s", event, hook_name)
            run_hook(cobj, [hook_name])


def run_hook(cobj, hook_args):
    """
    Loop through defined hooks and run all hooks attached to event.
    Returns: None
    """

    cobj.interpolate_delayed_variable()
    root_vars = {CONFIG_ARGS: hook_args}
    hook_name = hook_args[0]
    cobj.state.add_event(f"Running hook. hook args '{hook_args[1:]}'", hook=hook_name, flush=True)
    try:
        if not _run_hook(cobj, hook_args, root_vars=root_vars):
            cobj.state.add_event("Skipping running hook, condition evaluted to false", hook=hook_name, flush=True)
            return
        cobj.state.add_event("Finished running hook", hook=hook_name, flush=True)
        cobj.state.set_hook_state(hook_name, "_condition", {"ran": True}, flush=True)
    except CLIError as error:
        cobj.state.add_event(f"Error during hook execution {str(error)}", hook=hook_name, flush=True)
        raise


def _run_hook(cobj, hook_args, recursion_n=1, root_vars=None):
    hook_name = hook_args[0]
    if recursion_n > RECURSION_LIMIT:
        raise CLIError(f"Call recursion limit reached {recursion_n - 1} hook: {hook_name}")

    operation_num = 0
    hook = cobj.data[CONFIG_HOOKS][hook_name]
    _LOGGER.info("Running hook:%s, Args:%s", hook_name, hook_args)
    if not _evaluate_condition(cobj, hook_name, hook, root_vars):
        _LOGGER.debug("Condition for hook %s evaluted to false", hook_name)
        return False

    for operation in hook["ops"]:
        operation_num += 1
        ops_name = operation.get(CONFIG_NAME, operation.get("description", f"#{operation_num}"))
        if is_equal_or_in("", operation["platform"]):
            pass  # all platforms
        elif is_equal_or_in(cobj.platform, operation["platform"]):
            pass  # my platfrom
        else:
            _LOGGER.info("Skipping due platform. My platform '%s' limiting platform '%s'", cobj.platform, operation["platform"])
            continue  # Skip

        op_args = cobj.interpolate(phase=SECOND_PHASE, template=operation[CONFIG_ARGS], root_vars=root_vars, context=f"az-cli op interpolation '{ops_name}' in hook '{hook_name}'")
        op_cwd = cobj.interpolate(phase=SECOND_PHASE, template=operation.get("cwd", None), root_vars=root_vars, context=f"az-cli cwd interpolation '{ops_name}' in hook '{hook_name}'")
        interactive = operation.get("mode") == "interactive"
        if operation[CONFIG_TYPE] == "az":
            stdout, stderr = _run_az(hook_name, ops_name, op_args, cwd=op_cwd)
        elif operation[CONFIG_TYPE] == "cmd":
            stdout, stderr = _run_cmd(hook_name, ops_name, op_args, interactive, cwd=op_cwd)
        elif operation[CONFIG_TYPE] == "script":
            stdout, stderr = _run_script(hook_name, ops_name, op_args, hook_args[1:], cobj, cwd=op_cwd)
        elif operation[CONFIG_TYPE] == "print":
            stdout, stderr = _run_print(hook_name, ops_name, op_args)
        elif operation[CONFIG_TYPE] == "call":
            _run_hook(cobj, [op_args], recursion_n + 1, root_vars=root_vars)
            stdout, stderr = "", ""

        if operation.get(CONFIG_NAME, False):
            cobj.state.set_hook_state(hook=hook_name, op_name=operation[CONFIG_NAME], op_data={"stdout": stdout, "stderr": stderr}, flush=True)
            cobj.update_hooks_result(cobj.state.result_hooks)
    return True


def _run_print(hook_name, ops_name, op_args):
    _LOGGER.info("Print %s | %s", hook_name, ops_name)
    print(op_args)
    return op_args, ""


def _run_cmd(hook_name, ops_name, op_args, interactive=False, cwd=None):
    op_args = convert_to_shlex_arg(op_args)
    try:
        return run_command(op_args[0], op_args[1:], interactive=interactive, cwd=cwd)
    except Exception as error:
        raise CLIError(f"Failed during cmd execution in op '{ops_name}' in hook '{hook_name}'.\n{str(error)}") from error


def _run_az(hook_name, ops_name, op_args, cwd):
    op_args = convert_to_shlex_arg(op_args)
    try:
        return run_command("az", op_args, cwd=cwd)
    except Exception as error:
        raise CLIError(f"Failed during AZ execution in op '{ops_name}' in hook '{hook_name}'.\n{str(error)}") from error


def _run_script(hook_name, ops_name, op_args, hook_args, cobj, cwd):
    op_args = convert_to_shlex_arg(op_args)
    filename = op_args[0]
    target_file = f"{cobj.tmp_dir}/{os.path.basename(filename)}"
    content = file_read_content(op_args[0])
    content = cobj.interpolate(SECOND_PHASE, content, f"interpolating script op {op_args[0]}")
    file_write_content(target_file, content)
    os.chmod(target_file, stat.S_IRUSR | stat.S_IEXEC | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH)  # make file exec
    op_args[0] = target_file
    return _run_cmd(hook_name, ops_name, op_args, hook_args, cwd=cwd)


def _evaluate_condition(cobj, hook_name, hook_object, root_vars=None):
    """
    Evalute a jinja2 expression and returns a boolean

    Args:
        cobj: Config object.
        hook_name: string hook name
        hook_object: The hook object being evaluated.
        root_vars: An optional dictionary of variables.

    Returns:
        boolean if condition was evaluated correctly.
    """
    run_if = cobj.interpolate(phase=SECOND_PHASE, template=hook_object["run_if"], root_vars=root_vars, context=f"condition evaluation for hook '{hook_name}'")
    run_if = run_if.strip()
    if run_if.lower() in ["true", "1", "t", "y", "yes"]:
        return True
    if run_if.lower() in ["false", "0", "f", "n", "no"]:
        return False
    if RUNTIME_RUN_ONCE in run_if:
        condition = cobj.state.result_hooks[hook_name].get("_condition", {})
        ran = condition.get("ran", False)
        return not ran

    raise CLIError("A known boolean evaluation of condition hook '{}' expression '{}'".format(run_if, hook_name))
