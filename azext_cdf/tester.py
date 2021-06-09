""" Tester  file """

import os
import shlex
import base64
from distutils.util import strtobool
from knack.util import CLIError
from knack.log import get_logger
from azext_cdf.utils import convert_to_list_if_need, convert_to_shlex_arg, dir_exists
from azext_cdf.parser import ConfigParser
from azext_cdf._def import LIFECYCLE_PRE_TEST, LIFECYCLE_POST_TEST, STATE_PHASE_TESTED, STATE_PHASE_TESTING, CONFIG_NAME
from azext_cdf._def import CONFIG_TYPE, CONFIG_STATE_FILEPATH
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
    errors = []
    # run commands
    expect_cmds = expect_obj.get("cmd")
    for expect_cmd in convert_to_list_if_need(expect_cmds):
        try:
            _expect_cmd_exec(cobj, test_name, expect_cmd)
        except CLIError as error:
            errors.append(f"expect cmd failed '{expect_cmd}'. Error: '{error}'")
    # run asserts
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
        raise CLIError(f"test '{test_name}' failed with msg '{result.get('msg', '')}")


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
                   {CONFIG_NAME: "de-provision expect", "fail_override": False, "func": _run_expect_tests}]
    for i in down_object:
        _phase_cordinator(cmd, test_cobj, i["func"], i[CONFIG_NAME], expect_obj, result, test_name=test_name, exit_on_error=exit_on_error, down_strategy=down_strategy, fail=i["fail_override"])
        if result["failed"]:
            return
    # Run post test life cycle
    run_hook_lifecycle(test_cobj, LIFECYCLE_POST_TEST)


# git fetch tags --all
# git show HEAD~3 --pretty=format:"%H" --quiet
# git --no-pager tag --sort=-creatordate
#  git rev-list -n 1 $TAG
def _run_git(args=None, cwd=None):
    return run_command("git", args=args, interactive=False, cwd=cwd)[0]


def _manage_git_upgrade(upgrade_config, tmp_dir, prefix_test, reuse_dir=True):
    git_config = upgrade_config.get("git")
    repo_name = git_config.get("repo")
    repo_dir_path = os.path.join(tmp_dir, prefix_test)
    if reuse_dir:
        repo_dir_path = os.path.join(tmp_dir, str(base64.urlsafe_b64encode(repo_name.encode("utf-8")), "utf-8"))

    if not dir_exists(repo_dir_path):
        _run_git(args=["clone", repo_name, repo_dir_path])  # clone

    _run_git(args=["fetch", "--all"], cwd=repo_dir_path)  # fetch all
    if git_config.get("branch", False):
        branch = git_config.get("branch")
        if "~" in branch:
            #       compute right tag
            pass
        else:
            _run_git(args=["checkout", branch], cwd=repo_dir_path)
            _run_git(args=["pull"], cwd=repo_dir_path)
    elif git_config.get("tag", False):
        tag = git_config.get("tag")
        if "~" in tag:
            #       compute right tag
            pass
        _run_git(args=["checkout", tag], cwd=repo_dir_path)
        return repo_dir_path
    elif git_config.get("commit", False):
        commit = git_config.get("commit")
        _run_git(args=["checkout", commit], cwd=repo_dir_path)
    else:
        raise CLIError(f"No branch, commit, or tag defined. in {upgrade_config['name']}")
    return repo_dir_path


def _prepera_upgrade(cmd, upgrade_config, config, working_dir, test_name, prefix):
    override_config = {CONFIG_STATE_FILEPATH: "file://{{ cdf.tmp_dir }}/test_" + f"{prefix}_{test_name}_state.json"}
    test_cobj = ConfigParser(config, remove_tmp=False, working_dir=working_dir, test=test_name, override_config=override_config)
    upgrade_test = upgrade_config.get("from_expect")
    if upgrade_test is None:
        return test_cobj
    # Need to provision
    override_config["name"] = test_cobj.name
    override_config["resource_group"] = test_cobj.resource_group_name
    override_config["tmp_dir"] = test_cobj.tmp_dir

    if upgrade_config.get(CONFIG_TYPE) == "local":
        upgrade_location = upgrade_config.get("path")
    elif upgrade_config.get(CONFIG_TYPE) == "git":
        upgrade_location = _manage_git_upgrade(upgrade_config, test_cobj.tmp_dir, f"{prefix}_{test_name}", reuse_dir=True)

    upgrade_cobj = ConfigParser(config, remove_tmp=False, working_dir=upgrade_location, test=upgrade_test, override_config=override_config)
    print(f"Provisioning initial state {prefix}_{upgrade_test}")
    # TODO replace with _phase_cordinator to handle if provisioning fail
    _run_provision(cmd, upgrade_cobj, None, None)
    # change back working dir
    return test_cobj


# def _upgrade_matrix(cobj, upgrade_strategy):
#     matrix = []
#     if upgrade_strategy in ("all", "fresh"):
#         matrix.append({CONFIG_NAME: "fresh", "from_expect": None})
#     if upgrade_strategy in ("all", "upgrade"):
#         matrix = matrix + cobj.upgrade_flaten
#     return matrix

def _upgrade_matrix(cobj, global_upgrade_strategy, test_name):
    matrix = []
    test_upgrade_strategy = cobj.get_test(test_name).get("upgrade_strategy", "all")
    if global_upgrade_strategy in ("all", "fresh") and test_upgrade_strategy in ("all", "fresh"):
        matrix.append({CONFIG_NAME: "fresh", "from_expect": None})
    if global_upgrade_strategy in ("all", "upgrade") and test_upgrade_strategy in ("all", "upgrade"):
        matrix = matrix + cobj.upgrade_flaten(test_name)
    return matrix


def run_test(cmd, cobj, config, exit_on_error, test_args, working_dir, down_strategy, upgrade_strategy):
    """ test handler function. Run all tests or specific ones """

    results = {}
    cobj.state.transition_to_phase(STATE_PHASE_TESTING)
    for test_name in test_args:
        for upgrade_obj in _upgrade_matrix(cobj, upgrade_strategy, test_name):
            prefix = upgrade_obj[CONFIG_NAME]
            upgrade_title = f"'{upgrade_obj['name']}'"
            if upgrade_obj['from_expect']:
                prefix = f"{upgrade_obj['name']}_{upgrade_obj.get('from_expect')}"
                upgrade_title = f"'{upgrade_obj['name']}' from '{upgrade_obj['from_expect']}'"
            if prefix not in results:
                results[prefix] = {}

            results[prefix][test_name] = {"failed": False}
            print(f"Running test: '{test_name}' upgrade path: {upgrade_title}")
            test_cobj = _prepera_upgrade(cmd, upgrade_obj, config, working_dir, test_name, prefix)  # not sure about logic
            _run_single_test(cmd, test_cobj, results[prefix][test_name], test_name, exit_on_error, down_strategy)
        # TODO write tests to state
    cobj.state.transition_to_phase(STATE_PHASE_TESTED)
    return results

# pylint disable=W0613
