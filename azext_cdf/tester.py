""" Tester  file """

# import os
from knack.util import CLIError
from knack.log import get_logger
from azext_cdf.utils import Progress, init_config
from azext_cdf.parser import ConfigParser
from azext_cdf.provisioner import de_provision, provision
_logger = get_logger(__name__)

def run_expect(cobj, test_name):
    return {"failed"}

def _run_fn_abort_if_needed(cmd, test_cobj, func, phase_name, test_name, exit_on_first_error, always_clean_up):
    progress_indicator = Progress(cmd, pseudo=False)
    result = {"phase": phase_name}
    try:
        progress_indicator.begin(f"Test {test_name}: {phase_name}")
        func(cmd, test_cobj)
        result = {"failed": False, "msg": ""}
    except CLIError as error:
        result = {"failed": True, "msg": f"Failed during testing {phase_name}. {error}"}
        if always_clean_up and phase_name != "de-provisioning":
            progress_indicator.begin(f"Test {test_name}: cleaning up due to error")
            try:
                de_provision(cmd, test_cobj)
            except CLIError as error2:
                _logger.warning("Failed to clean up %s, %s", test_name, error2)
        progress_indicator.end(f"Test {test_name}: {phase_name} failed")
        if always_clean_up and phase_name == "de-provisioning":
            _logger.warning("Failed to clean up %s, %s", test_name, error)
        if exit_on_first_error:
            raise CLIError(f"test '{test_name}' failed with msg '{result['msg']}") from error
    progress_indicator.end(f"Test {test_name}: {phase_name} finished")
    return result

# pylint: disable=unused-argument
def run_test(cmd, cobj, config, cwd, exit_on_first_error, test_args, working_dir, state_file, always_clean_up):
    """ test handler function. Run all tests or specific ones """

    results = {}
    one_test_failed = False

    for test_name in test_args:
        results[test_name] = {"name": test_name}
        test_cobj, _ = init_config(config, ConfigParser, remove_tmp=False, working_dir=working_dir, state_file=state_file, test=test_name)
        #### 1. up
        results[test_name] = {**results[test_name], **_run_fn_abort_if_needed(cmd, test_cobj, provision, "provisioning", test_name, exit_on_first_error, always_clean_up)}
        if results[test_name]["failed"]:
            one_test_failed = True
            continue
        #### 2. run tests
        results[test_name] = {**results[test_name], **_run_fn_abort_if_needed(cmd, test_cobj, run_expect, "testing", test_name, exit_on_first_error, always_clean_up)}
        if results[test_name]["failed"]:
            one_test_failed = True
            continue
        #### 3. down
        results[test_name] = {**results[test_name], **_run_fn_abort_if_needed(cmd, test_cobj, de_provision, "de-provisioning", test_name, exit_on_first_error, always_clean_up)}
        if results[test_name]["failed"]:
            one_test_failed = True
            continue
    # 4. write tests to state
    # TODO write tests to state

    # print status to screen
    if one_test_failed:
        for test in results:
            if results[test]["failed"]:
                _logger.warning(results[test])
        raise CLIError("At-least on test failed")
    return results, one_test_failed
