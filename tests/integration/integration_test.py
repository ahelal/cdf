''' integration bicep test'''

import unittest
import os
from test_helper import run_command
unittest.TestLoader.sortTestMethodsUsing = None

# pylint: disable=C0111
class AzIntegration(unittest.TestCase):
    def _cmd(self, binary, args, expect_to_pass=True):
        passed = False
        error = None
        try:
            run_command(binary, args)
            passed = True
        except Exception as error_exception:
            passed = False
            error = error_exception

        if expect_to_pass != passed:
            self.fail(f"exception not met. Command expect to exit with '{expect_to_pass}' but exited with '{passed}'. {error}")


    def test_terraform_fixture(self):
        self._cmd("az", ["cdf", "test", "-w", "./tests/fixtures/terraform/v2", "--down-strategy=always"])

    def test_arm_fixture_1_up(self):
        self._cmd("az", ["cdf", "up", "-w", "./tests/fixtures/arm/v2"])
        #   az cdf up -w ./tests/fixtures/arm/v2

    def test_arm_fixture_2_status(self):
        self._cmd("az", ["cdf", "status", "-w", "./tests/fixtures/arm/v2"])
	    # az cdf status -w ./tests/fixtures/arm/v2

    def test_arm_fixture_3_hook_fail(self):
        self._cmd("az", ["cdf", "hook", "-w", "./tests/fixtures/arm/v2", "fail"], False)
    def test_arm_fixture_3_hook_pass(self):
        self._cmd("az", ["cdf", "hook", "-w", "./tests/fixtures/arm/v2", "pass"])

    def test_arm_fixture_4_down(self):
        self._cmd("az", ["cdf", "down", "-y", "-w", "./tests/fixtures/arm/v2"])
	    # az cdf down -y -w ./tests/fixtures/arm/v2

    def test_arm_fixture_5_test(self):
        self._cmd("az", ["cdf", "test", "-w", "./tests/fixtures/arm/v2"])
	    # az cdf test -w ./tests/fixtures/arm/v2

    def test_bicep_1_relative_path(self):
        self._cmd("az", ["cdf", "test", "-w", "./tests/fixtures/bicep/v2", "--down-strategy=always", "default"])

    def test_bicep_2_cwd(self):
        cwd = os.getcwd()
        try:
            os.chdir('./tests/fixtures/bicep/v2')
            run_command("az", ["cdf", "test", "expect_to_fail_and_fails"])
        except Exception as error:
            os.chdir(cwd)
            self.fail(f"exception should not be raised but raised: {error}")
        os.chdir(cwd)
