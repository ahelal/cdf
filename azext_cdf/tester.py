""" Tester  file """

# import os
import shlex
from distutils.util import strtobool
from knack.util import CLIError
from knack.log import get_logger
from azext_cdf.utils import convert_to_list_if_need, convert_to_shlex_arg
from azext_cdf.parser import ConfigParser
from azext_cdf._def import LIFECYCLE_PRE_TEST, LIFECYCLE_POST_TEST, STATE_PHASE_TESTED, STATE_PHASE_TESTING, CONFIG_NAME
from azext_cdf.hooks import run_hook_lifecycle
from azext_cdf.provisioner import de_provision, provision, run_command
from azext_cdf.hooks import run_hook

_LOGGER = get_logger(__name__)


def _run_hook(_, cobj, __, expect_hook):
    hook_name = expect_hook.get("hook")
    hook_args = expect_hook.get("args", [])
    hook_args = convert_to_shlex_arg(hook_args)
    hook_args = [hook_name] + hook_args
    return run_hook(cobj, hook_args)


def _run_provision(cmd, cobj, _, __):
    return provision(cmd, cobj)


def _run_de_provision(cmd, cobj, _, __):
    return de_provision(cmd, cobj)


def _run_expect_tests(_, cobj, test_name, expect_obj):
    # TODO simplify ugly
    errors = []
    expect_cmds = expect_obj.get("cmd")
    for expect_cmd in convert_to_list_if_need(expect_cmds):
        try:
            _expect_cmd_exec(cobj, test_name, expect_cmd)
        except CLIError as error:
            errors.append(f"expect cmd failed '{expect_cmd}'. Error: '{error}'")

    asserts = expect_obj.get("assert")
    for expect_assert in convert_to_list_if_need(asserts):
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


def _phase_cordinator(cmd, test_cobj, func, phase_name, expect_obj, result, **kwargs):
    expect_to_fail = kwargs.get("fail")
    exit_on_error = kwargs.get("exit_on_error", False)
    down_strategy = kwargs.get("down_strategy")
    test_name = kwargs.get("test_name")
    result[phase_name] = {"expect_to_fail": expect_to_fail}
    failed_expection = False
    try:
        func(cmd, test_cobj, test_name, expect_obj)
        if expect_to_fail:
            result["failed"] = True  # test failed globably
            result[phase_name] = {"failed": True, "msg": "expecting to fail and did not fail"}
            failed_expection = True
        else:
            result[phase_name] = {"failed": False, "msg": ""}

    except CLIError as error:
        if expect_to_fail:
            result[phase_name]["failed"] = False
            result[phase_name]["msg"] = "Failed but skipped, due to matched expectation"
        else:
            result[phase_name]["failed"] = True
            result[phase_name]["msg"] = str(error)
            result["failed"] = True  # test failed globably
            failed_expection = True
    if failed_expection and down_strategy == "always" and phase_name != "de-provisioning":
        try:
            de_provision(cmd, test_cobj)
        except CLIError as error:
            _LOGGER.warning("Failed to clean up %s, %s", test_name, error)
    elif failed_expection and down_strategy == "always" and phase_name == "de-provisioning":
        _LOGGER.warning("Failed to clean up %s, %s", test_name, str(result[phase_name]["msg"]))

    if exit_on_error and failed_expection:
        raise CLIError(f"test '{test_name}' failed with msg '{result['msg']}")


def _run_single_test(cmd, test_cobj, result, test_name, exit_on_error, down_strategy):
    # Run pre test life cycle
    run_hook_lifecycle(test_cobj, LIFECYCLE_PRE_TEST)

    # ** UP and UP expect**
    expect_obj = test_cobj.get_test(test_name, expect="up")
    up_object = [{CONFIG_NAME: "provisioning", "fail_override": expect_obj.get("fail", False), "func": _run_provision},
                 {CONFIG_NAME: "provision expect", "fail_override": False, "func": _run_expect_tests}]
    for i in up_object:
        _phase_cordinator(cmd, test_cobj, i["func"], i[CONFIG_NAME], expect_obj, result, test_name=test_name, exit_on_error=exit_on_error, down_strategy=down_strategy, fail=i["fail_override"])
        if result["failed"]:
            return

    # ** Run hook and hook expect **
    for hook in test_cobj.test_hooks(test_name=test_name):
        expect_obj = test_cobj.get_test(test_name, hook=hook)
        expect_obj['hook'] = hook
        hook_object = [{CONFIG_NAME: f"hook {hook}", "fail_override": expect_obj.get("fail", False), "func": _run_hook},
                       {CONFIG_NAME: f"hook {hook} expect", "fail_override": False, "func": _run_expect_tests}]
        for i in hook_object:
            _phase_cordinator(cmd, test_cobj, i["func"], i[CONFIG_NAME], expect_obj, result, test_name=test_name, exit_on_error=exit_on_error, down_strategy=down_strategy, fail=i["fail_override"])
            if result["failed"]:
                return

    if down_strategy == 'never':  # Should we ignore down ?
        # TODO give a warning if we have down expect
        return
    # ** Down and Down expect**
    expect_obj = test_cobj.get_test(test_name, expect="down")
    down_object = [{CONFIG_NAME: "de-provisioning", "fail_override": expect_obj.get("fail", False), "func": _run_de_provision},
                   {CONFIG_NAME: "de-provisioning", "fail_override": False, "func": _run_expect_tests}]
    for i in down_object:
        _phase_cordinator(cmd, test_cobj, i["func"], i[CONFIG_NAME], expect_obj, result, test_name=test_name, exit_on_error=exit_on_error, down_strategy=down_strategy, fail=i["fail_override"])
        if result["failed"]:
            return

    # Run post test life cycle
    run_hook_lifecycle(test_cobj, LIFECYCLE_POST_TEST)


def _manage_git_upgrade():
    pass


def _prepera_upgrade(upgrade_path, config, working_dir, test_name, prefix):
    override_config = {"CONFIG_STATE_FILENAME": f"test_{prefix}_{test_name}_state.json"}
    if upgrade_path.get("from_expect") is None:
        return ConfigParser(config, remove_tmp=False, working_dir=working_dir, test=test_name, override_config=override_config)
    # Need to provision
    test_cobj = None
    if upgrade_path.get("type") == "local":
        # change working dir, override tmp file
        test_cobj = ConfigParser(config, remove_tmp=False, working_dir=working_dir, test=test_name, override_config=override_config)
    elif upgrade_path.get("type") == "git":
        pass
    # change back working dir
    return test_cobj


def _upgrade_matrix(cobj, upgrade_strategy):
    matrix = []
    if upgrade_strategy in ("all", "fresh"):
        matrix.append({CONFIG_NAME: "fresh", "from_expect": None})
    if upgrade_strategy in ("all", "upgrade"):
        matrix = matrix + cobj.upgrade_flaten
    return matrix


# pylint: disable=W0613
def run_test(cmd, cobj, config, exit_on_error, test_args, working_dir, down_strategy, upgrade_strategy):
    """ test handler function. Run all tests or specific ones """

    results = {}
    cobj.state.transition_to_phase(STATE_PHASE_TESTING)
    for upgrade_obj in _upgrade_matrix(cobj, upgrade_strategy):
        prefix = upgrade_obj[CONFIG_NAME]
        upgrade_title = f"'{upgrade_obj['name']}'"
        if upgrade_obj['from_expect']:
            prefix = f"{upgrade_obj['name']}_{upgrade_obj.get('from_expect')}"
            upgrade_title = f"'{upgrade_obj['name']}' from '{upgrade_obj['from_expect']}'"
        results[prefix] = {}
        for test_name in test_args:
            print(f"Running test: '{test_name}' upgrade path: {upgrade_title}")
            results[prefix][test_name] = {"failed": False}
            test_cobj = _prepera_upgrade(upgrade_obj, config, working_dir, test_name, prefix)  # not sure about logic
            _run_single_test(cmd, test_cobj, results[prefix][test_name], test_name, exit_on_error, down_strategy)
        # TODO write tests to state
    cobj.state.transition_to_phase(STATE_PHASE_TESTED)
    return results
