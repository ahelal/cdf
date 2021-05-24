""" Tester  file """

# import os
import shlex

from distutils.util import strtobool
from knack.util import CLIError
from knack.log import get_logger
from azext_cdf.utils import Progress, init_config
from azext_cdf.parser import ConfigParser
from azext_cdf.provisioner import de_provision, provision, run_command
from azext_cdf.hooks import run_hook

_logger = get_logger(__name__)

def _run_hook(_, cobj, __, expect_hook):
    hook_name = expect_hook.get("hook")
    hook_args = expect_hook.get("args", [])
    hook_args = [hook_name] + hook_args
    return run_hook(cobj, hook_args)

def _run_provision(cmd, cobj, _, __):
    return provision(cmd, cobj)

def _run_de_provision(cmd, cobj, _, __):
    return de_provision(cmd, cobj)

def _run_expect_tests(_, cobj, test_name, expect_obj):
    errors = []
    expect_cmds = expect_obj.get("cmd")
    if expect_cmds:
        if isinstance(expect_cmds, str):
            expect_cmds = [expect_cmds] # convert to list
        for expect_cmd in expect_cmds:
            try:
                _expect_cmd_exec(cobj, test_name, expect_cmd)
            except CLIError as error:
                errors.append(f"expect cmd failed '{expect_cmd}'. Error: '{error}'")

    asserts = expect_obj.get("assert")
    if asserts:
        if isinstance(asserts, str):
            asserts = [asserts] # convert to list
        for expect_assert in asserts:
            try:
                _expect_assert_exec(cobj, test_name, expect_assert)
            except CLIError as error:
                errors.append(f"expect asset failed '{expect_assert}'. Error: '{error}'")
    if errors:
        raise CLIError(errors)

def _expect_cmd_exec(cobj, test_name, expect_cmd):
    cobj.interpolate_delayed_variable()
    expect_cmds_interpolated = cobj.interpolate(phase=2, template=expect_cmd, context=f"test '{test_name}' cmd interpolation '{expect_cmd}'")
    expect_cmds_interpolated = shlex.split(expect_cmds_interpolated)
    return run_command(expect_cmds_interpolated[0], expect_cmds_interpolated[1:], interactive=False)

def _expect_assert_exec(cobj, test_name, expect_assert):
    cobj.interpolate_delayed_variable()
    try:
        expect_assert = cobj.interpolate(phase=2, template=expect_assert, context=f"test '{test_name}' cmd interpolation '{expect_assert}'")
        if isinstance(expect_assert, bool):
            pass
        elif isinstance(expect_assert, (str)):
            expect_assert = strtobool(expect_assert)
        else:
            raise CLIError("Unknown boolean expression '{expect_assert}'")
    except ValueError as error:
        raise CLIError from error

    if not expect_assert:
        raise CLIError("expression evaluted to false")


def _phase_cordinator(cmd, test_cobj, func, phase_name, phase_params, expect_obj, results):
    progress_indicator = Progress(cmd, pseudo=False)
    expect_to_fail = phase_params.get("fail", expect_obj.get("fail",  False)) # get expect to fail from params, from expect obj, or defaults to false
    test_name = phase_params['test_name']
    results[test_name][phase_name] = { "expect_to_fail": expect_to_fail }
    mismatched_failed_expection = False
    progress_indicator.begin(f"Test {phase_params['test_name']}: {phase_name}")
    progress_end_msg = ""
    try:
        func(cmd, test_cobj, test_name, expect_obj)
        if expect_to_fail:
            results[test_name]["failed"] = True # test failed globably
            mismatched_failed_expection = True
            progress_end_msg = f"Test {phase_params['test_name']}: {phase_name} failed"
            results[test_name][phase_name] = {"failed": True, "msg": "expecting to fail and did not fail"}
        else:
            progress_end_msg = f"Test {phase_params['test_name']}: {phase_name} finished"
            results[test_name][phase_name] = {"failed": False, "msg": ""}

    except CLIError as error:
        if expect_to_fail:
            progress_end_msg = f"Test {phase_params['test_name']}: {phase_name} finished"
            results[test_name][phase_name]["failed"] = False
            results[test_name][phase_name]["msg"] = "Failed but skipped, due to matched expectation"
        else:
            progress_end_msg = f"Test {phase_params['test_name']}: {phase_name} failed"
            results[test_name][phase_name]["failed"] = True
            results[test_name][phase_name]["msg"] = str(error)
            results[test_name]["failed"] = True # test failed globably
            mismatched_failed_expection = True
    progress_indicator.begin(progress_end_msg)
    if mismatched_failed_expection and phase_params["always_clean_up"] and phase_name != "de-provisioning":
        progress_indicator.begin(f"Test {test_name}: cleaning up due to error")
        try:
            de_provision(cmd, test_cobj)
        except CLIError as error:
            _logger.warning("Failed to clean up %s, %s", test_name, error)
        progress_indicator.begin(f"Test {test_name}: cleaning up due to error")
    elif mismatched_failed_expection and phase_params["always_clean_up"] and phase_name == "de-provisioning":
        _logger.warning("Failed to clean up %s, %s", phase_params['test_name'], str(error))

    progress_indicator.end(progress_end_msg)
    if phase_params['exit_on_first_error'] and mismatched_failed_expection:
        raise CLIError(f"test '{phase_params['test_name']}' failed with msg '{results[phase_params['test_name']]['msg']}")

# pylint: disable=unused-argument
def run_test(cmd, cobj, config, cwd, exit_on_first_error, test_args, working_dir, state_file, always_clean_up, always_keep):
    """ test handler function. Run all tests or specific ones """

    results = {}
    for test_name in test_args:
        phase_params = { "test_name": test_name, "exit_on_first_error": exit_on_first_error, "always_clean_up": always_clean_up, "always_keep": always_keep }
        results[test_name] = { "failed": False }
        test_cobj, _ = init_config(config, ConfigParser, remove_tmp=False, working_dir=working_dir, state_file=state_file, test=test_name)

        #### UP
        expect_obj = test_cobj.get_test(test_name, expect="up")
        _phase_cordinator(cmd, test_cobj, _run_provision, "provisioning", phase_params, expect_obj, results)
        if results[test_name]["failed"]: continue

        #### UP expect
        _phase_cordinator(cmd, test_cobj, _run_expect_tests, "provision expect", {**phase_params, **{"fail": False}}, expect_obj, results)
        if results[test_name]["failed"]: continue

        #### RUN HOOKS
        for hook in test_cobj.test_hooks(test_name=test_name):
            expect_obj = test_cobj.get_test(test_name, hook=hook)
            expect_obj['hook'] = hook
            _phase_cordinator(cmd, test_cobj, _run_hook, f"hook {hook}", phase_params, expect_obj, results)
            if results[test_name]["failed"]: continue

        #### Hooks expect
            _phase_cordinator(cmd, test_cobj, _run_expect_tests, f"hook {hook} expect", {**phase_params, **{"fail": False}}, expect_obj, results)
            if results[test_name]["failed"]: continue

        #### DOWN
        if always_keep:
            continue
        expect_obj = test_cobj.get_test(test_name, expect="down")
        _phase_cordinator(cmd, test_cobj, _run_de_provision, "de-provisioning", phase_params, expect_obj, results)
        if results[test_name]["failed"]: continue

        #### DOWN expect
        _phase_cordinator(cmd, test_cobj, _run_expect_tests, "de-provision expect", {**phase_params, **{"fail": False}}, expect_obj, results)
        if results[test_name]["failed"]: continue

    # 6. write tests to state

    # TODO write tests to state
    return results
