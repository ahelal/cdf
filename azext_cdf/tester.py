""" Tester  file """

import os
import glob
import base64
import sys
from distutils.util import strtobool
from knack.util import CLIError
from knack.log import get_logger
from azext_cdf.utils import convert_to_list_if_need, convert_to_shlex_arg, dir_exists, file_exists, find_the_right_file, find_the_right_dir
from azext_cdf.parser import ConfigParser
from azext_cdf._def import LIFECYCLE_PRE_TEST, LIFECYCLE_POST_TEST, STATE_PHASE_TESTED, STATE_PHASE_TESTING, CONFIG_NAME
from azext_cdf._def import CONFIG_TYPE, CONFIG_STATE_FILEPATH, CONFIG_EXPECT_RUNNER, CONFIG_EXPECT_RUNNER_CMD, CONFIG_EXPECT_RUNNER_FILES, CONFIG_EXPECT_RUNNER_EXTENSION
from azext_cdf._def import CONFIG_PARAMS, CONFIG_EXPECT_HOOK_ARGS, CONFIG_EXPECT_ASSERT, CONFIG_EXPECT_PLAN
from azext_cdf.hooks import run_hook_lifecycle
from azext_cdf.provisioner import de_provision, provision, run_command, _run_arm_what_if, _run_terraform_plan, pre_provision
from azext_cdf.hooks import run_hook

_LOGGER = get_logger(__name__)


def _print_x(message):
    print(message)


def _run_hook(_, cobj, __, expect_hook):
    hook_name = expect_hook.get("hook")
    hook_args = expect_hook.get(CONFIG_EXPECT_HOOK_ARGS, [])
    hook_args = convert_to_shlex_arg(hook_args)
    hook_args = [hook_name] + hook_args
    return run_hook(cobj, hook_args)


def _run_provision(cmd, cobj, _, __):
    return provision(cmd, cobj)


def _run_de_provision(cmd, cobj, _, __):
    return de_provision(cmd, cobj)


def _expect_plan(cmd, cobj, test_name, expect_obj):
    # todo check if
    plan_expect = expect_obj.get(CONFIG_EXPECT_PLAN)
    if plan_expect == {}:
        # print("skipping no plan")
        return False
    plan_actual = {}
    pre_provision(cmd, cobj)
    deployment_name = cobj.name
    params = cobj.config[CONFIG_PARAMS]
    if cobj.provisioner == "bicep" or cobj.provisioner == "arm":
        plan_actual = _run_arm_what_if(cmd,
                                       deployment_name=deployment_name,
                                       arm_template_file=find_the_right_file(cobj.up_location, "arm", "*.json", cobj.config_dir),
                                       resource_group=cobj.resource_group_name,
                                       params=params,
                                       no_prompt=False,
                                       complete_deployment=cobj.deployment_mode)
    elif cobj.provisioner == "terraform":
        plan_actual =_run_terraform_plan(deployment_name,
                                        find_the_right_dir(cobj.up_location, cobj.config_dir),
                                        cobj.tmp_dir,
                                        params=params,
                                        bin_path="terraform",
                                        no_prompt=False)
    result = _compare_plans(cobj, test_name, plan_actual, plan_expect)
    if result != {}:
        raise CLIError(f"plan mismatch {result}")
    return False


def _compare_plans(cobj, test_name, plan_actual, plan_expect):
    diff = {}
    # print("plan_actual", plan_actual)
    # print("plan_expect", plan_expect)
    for expect_plan_name, expect_plan_value in plan_expect.items():
        actual_plan_value = plan_actual.get(expect_plan_name, None)
        if actual_plan_value is None:
            pass
        elif isinstance(expect_plan_value, int) and actual_plan_value != expect_plan_value:
            diff[expect_plan_name] = {"expected": expect_plan_value, "actual": actual_plan_value}
        elif isinstance(expect_plan_value, str):
            expr_result = cobj.interpolate(phase=2, template=expect_plan_value, context=f"test '{test_name}' plan interpolation for '{expect_plan_name}'", extra_vars={"_plan": actual_plan_value})
            if not strtobool(expr_result):
                diff[expect_plan_name] = {"expected_expression": expect_plan_value, "actual": actual_plan_value}
    return diff


def _run_expect_tests(_, cobj, test_name, expect_obj):
    errors = []
    # run runner
    expect_runner = expect_obj.get(CONFIG_EXPECT_RUNNER)
    try:
        expect_runner_exec(cobj, test_name, expect_runner)
    except CLIError as error:
        errors.append(f"expect runner failed '{expect_runner}'. Error: '{error}'")
    # run asserts
    asserts = expect_obj.get(CONFIG_EXPECT_ASSERT)
    for expect_assert in convert_to_list_if_need(asserts):
        try:
            _expect_assert_exec(cobj, test_name, expect_assert)
        except CLIError as error:
            errors.append(f"expect asset failed '{expect_assert}'. Error: '{error}'")
    if errors:
        raise CLIError(errors)


def expect_runner_exec(cobj, test_name, expect_runner):
    ''' main expect runner function'''

    if expect_runner is None:
        return
    cobj.interpolate_delayed_variable()
    cmd = expect_runner.get(CONFIG_EXPECT_RUNNER_CMD, None)
    if cmd is None:
        return
    cmd = cobj.interpolate(phase=2, template=cmd, context=f"test '{test_name}' expect runner cmd interpolation '{cmd}'")
    cmd = convert_to_shlex_arg(cmd)
    # files
    files = expect_runner.get(CONFIG_EXPECT_RUNNER_FILES, None)
    files = cobj.interpolate(phase=2, template=files, context=f"test '{test_name}' expect runner files interpolation '{files}'")
    # ext to filter
    ext = expect_runner.get(CONFIG_EXPECT_RUNNER_EXTENSION, None)
    ext = cobj.interpolate(phase=2, template=ext, context=f"test '{test_name}' expect runner extension interpolation '{ext}'")
    # test files
    test_files = _prepare_test_runner_dirs(cobj, test_name, files, ext)
    if test_files is None or len(test_files) == 0:
        error, stdout, stderr = _run_test_cmd(cobj, cmd)
        if error:
            raise CLIError(error)
        return
    test_return_error = []
    for test_file in test_files:
        if '<test_file>' in cmd:
            cmd = [s_cmd.replace('<test_file>', test_file) for s_cmd in cmd]
        else:
            cmd = cmd + [test_file]
        error, stdout, stderr = _run_test_cmd(cobj, cmd)
        if error:
            test_return_error.append({"error": error, "stdout": stdout, "stderr": stderr, "cmd": cmd})
    if test_return_error:
        raise CLIError(test_return_error)
    return


def _run_test_cmd(cobj, cmd):
    env = {"PYTHONPATH": ":".join(sys.path)}
    env["CDF_NAME"] = cobj.name
    env["CDF_LOCATION"] = cobj.location
    env["CDF_RESOURCE_GROUP"] = cobj.resource_group_name
    # TODO output status from state or point to state ??
    env["CDF_JSON_VARS"] = "TODO"
    error, stdout, stderr = None, None, None
    try:
        stdout, stderr = run_command(cmd[0], cmd[1:], env=env)
    except CLIError as err:
        error = err
    return error, stdout, stderr


def _prepare_test_runner_dirs(cobj, test_name, files, ext_filter):
    ''' Run  tests runner '''

    if files is None:
        return None
    if isinstance(files, str):
        files = [files]

    test_files = []
    for test_file in files:
        test_file = cobj.interpolate(phase=2, template=test_file, context=f"test '{test_name}' expect runner file interpolation '{test_file}'")
        test_file = os.path.realpath(test_file)
        if file_exists(test_file):
            # A file just add it
            test_files.append(test_file)
        elif dir_exists(test_file):
            for glob_file in glob.glob(os.path.join(test_file, ext_filter)):
                if file_exists(os.path.join(test_file, glob_file)):
                    test_files.append(os.path.join(test_file, glob_file))
    return test_files


def _expect_assert_exec(cobj, test_name, expect_assert):
    cobj.interpolate_delayed_variable()
    try:
        expect_assert = cobj.interpolate(phase=2, template=expect_assert, context=f"test '{test_name}' cmd interpolation '{expect_assert}'")
        if isinstance(expect_assert, bool):
            pass
        elif isinstance(expect_assert, (str)):
            expect_assert = strtobool(expect_assert)
        else:
            raise CLIError(f"Unknown boolean expression '{expect_assert}'")
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
    _print_x(f"  Calling '{phase_name}', expect to fail: '{expect_to_fail}'")
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
            _print_x(f"  Failed to cleanup '{test_name}' {str(error)}")
            _LOGGER.warning("Failed to clean up %s, %s", test_name, str(error))
    elif failed_expection and down_strategy == "always" and phase_name == "de-provisioning":
        _print_x(f"  Failed to cleanup '{test_name}' {str(result[phase_name]['msg'])}")
        _LOGGER.warning("Failed to clean up %s, %s", test_name, str(result[phase_name]["msg"]))

    if exit_on_error and failed_expection:
        _print_x(f"  Exiting test '{test_name}' since exit on error is set. ")
        raise CLIError(f"test '{test_name}' failed with msg '{result.get('msg', '')}")
    _print_x(f"  '{phase_name}' failed: {result[phase_name]['failed']}, expected to fail: {expect_to_fail}, Msg: '{result[phase_name]['msg']}'")


def _run_single_test(cmd, test_cobj, result, test_name, exit_on_error, down_strategy):
    # Run pre test life cycle
    run_hook_lifecycle(test_cobj, LIFECYCLE_PRE_TEST)

    # ** Run whatif/plan **
    expect_obj = test_cobj.get_test(test_name, expect="up")
    _phase_cordinator(cmd, test_cobj, _expect_plan, "plan", expect_obj, result, test_name=test_name, exit_on_error=exit_on_error, down_strategy=down_strategy, fail=False)
    if result["failed"]:
        return

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
# git rev-list -n 1 $TAG
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
    _print_x(f"  Upgrade provisioning initial state {prefix}_{upgrade_test}")
    # TODO replace with _phase_cordinator to handle if provisioning fail
    _run_provision(cmd, upgrade_cobj, None, None)
    # change back working dir
    return test_cobj


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
    _print_x(f"Test configuration, exit on error: '{exit_on_error}', down strategy: '{down_strategy}', upgrade strategy: '{upgrade_strategy}'")
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
            _print_x(f"Starting test: '{test_name}', upgrade path: {upgrade_title}")
            test_cobj = _prepera_upgrade(cmd, upgrade_obj, config, working_dir, test_name, prefix)  # not sure about logic
            _run_single_test(cmd, test_cobj, results[prefix][test_name], test_name, exit_on_error, down_strategy)
        # TODO write tests to state
    cobj.state.transition_to_phase(STATE_PHASE_TESTED)
    return results

# pylint disable=W0613
