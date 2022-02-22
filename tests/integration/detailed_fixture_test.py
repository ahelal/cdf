''' Utils test'''

import os
import unittest
import json
import shutil
from test_helper import run_command, remove_file
unittest.TestLoader.sortTestMethodsUsing = None


# pylint: disable=C0111
class AzCDF(unittest.TestCase):
    def setUp(self):
        self.work_dir = f"{os.getcwd()}/tests/fixtures/bicep/v2"
        shutil.rmtree(f"{os.getcwd()}/tests/fixtures/bicep/v2/.cdf_tmp", ignore_errors=True)
    def test_cdf_debug_version(self):
        stdout, stderr = run_command("az", ["cdf", "debug", "version"])
        self.assertIn("CDF", stdout)
        self.assertIn("az-cli", stdout)
        self.assertIn("bicep", stdout)
        self.assertEqual(stderr, "")

    def test_cdf_status(self):
        stdout, stderr = run_command("az", ["cdf", "status", "-w", self.work_dir])
        json_stdout = json.loads(stdout)
        self.assertEqual(json_stdout["Phase"], 'unknown')
        self.assertEqual(json_stdout["Status"], 'unknown')
        self.assertIn('state file', json_stdout["StatusMessage"])
        self.assertIn("ResourceGroup", json_stdout)
        self.assertIn("Name", json_stdout)
        self.assertIn("version", json_stdout)
        self.assertIn("Timestamp", json_stdout)
        self.assertEqual(stderr, "")

    def test_cdf_hook_no_args(self):
        stdout, stderr = run_command("az", ["cdf", "hook", "-w", self.work_dir])
        json_stdout = json.loads(stdout)
        number_of_hooks = 14
        self.assertEqual(len(json_stdout), number_of_hooks)
        self.assertEqual(stderr, "")
    def test_cdf_debug_errors(self):
        with self.assertRaises(ValueError):
            run_command("az", ["cdf", "debug", "errors","-w", self.work_dir])

class FixtureBicep(unittest.TestCase):
    resource_id = None
    def setUp(self):
        self.work_dir = f"{os.getcwd()}/tests/fixtures/bicep/v2"
        self.hook_log = f"{os.getcwd()}/tests/fixtures/bicep/v2/.cdf_tmp/hook_log.txt"
        remove_file(self.hook_log)

    def test_1_cdf_up_0(self):
        stdout, stderr = run_command("az", ["cdf", "up", "-w", self.work_dir])
        stdout_lines = list(filter(None, stdout.split("\n")))  # remove empty lines and split into list
        self.assertEqual(stderr, "")
        self.assertEqual(4, len(stdout_lines))  # 4 lines in stdout
        self.assertIn("Provisioning", stdout_lines[0])  # 1st line
        self.assertIn('"post-up", "pre-up"', stdout_lines[1])  # 2nd line
        self.assertIn('"post-up", "pre-up"', stdout_lines[2])  # 3ed line
        self.assertIn("post-up", stdout_lines[3])  # 3ed line
        # check the hook log and compare content
        with open(self.hook_log, 'r') as file:
            data = file.read().replace('\n', '')
            self.assertEqual(data, "pre-upall-upall-uppost-up")

    def test_1_cdf_up_1_status(self):
        stdout, stderr = run_command("az", ["cdf", "status", "-w", self.work_dir])
        json_stdout = json.loads(stdout)
        self.assertEqual(json_stdout["Phase"], 'up')
        self.assertEqual(json_stdout["Status"], 'success')
        self.assertEqual(stderr, "")

    def test_1_cdf_up_2_result_resource(self):
        stdout, stderr = run_command("az", ["cdf", "debug", "result", "-w", self.work_dir])
        self.assertEqual(stderr, "")
        json_stdout = json.loads(stdout)
        self.assertEqual(json_stdout["outputs"]["extra"]['value'], 'default')
        self.assertEqual(json_stdout["outputs"]["helloword"]['value'], 'Hello')
        resource = json_stdout["resources"]
        self.__class__.resource_id = resource[0]["id"]
        self.assertEqual(len(resource), 1)
        try:
            stdout, stderr = run_command("az",["resource", "show", "--id", self.__class__.resource_id])
        except ValueError as error:
            self.fail(error)

    def test_1_cdf_up_3_errors(self):
        run_command("az", ["cdf", "debug", "errors","-w", self.work_dir])

    def test_2_cdf_hook_0_az(self):
        stdout, stderr = run_command("az", ["cdf", "hook", "az", "-w", self.work_dir])
        self.assertEqual(stderr, "")
        self.assertEqual(stdout.replace('"', "").replace("\n", ""), os.path.basename(self.__class__.resource_id.lower()))

    def test_2_cdf_hook_1_script(self):
        stdout, stderr = run_command("az", ["cdf", "hook", "script", "-w", self.work_dir])
        self.hook_log = f"{os.getcwd()}/tests/fixtures/bicep/v2/.cdf_tmp/script.txt"
        with open(self.hook_log, 'r') as file:
            data = file.read().replace('\n', '')
        self.assertEqual(data, "eastus2")
        self.assertIn("X_STDOUT", stdout)
        self.assertIn("X_STDERR", stdout)
        self.assertIn("", stderr)

    def test_2_cdf_hook_2_print_result(self):
        stdout, stderr = run_command("az", ["cdf", "hook", "print_result", "-w", self.work_dir])
        self.assertEqual(stderr, "")
        self.assertIn(self.__class__.resource_id.lower(), stdout.lower())

    def test_2_cdf_hook_3_cmd(self):
        stdout, stderr = run_command("az", ["cdf", "hook", "cmd", "-w", self.work_dir])
        self.assertEqual(stderr, "")
        self.assertEqual("printA=stdoutB=stderrC=print", stdout.replace('\n', ''))

    stdout, stderr = "", ""
    def test_2_cdf_hook_4_fail(self):
        stdout, stderr = "", ""
        with self.assertRaises(ValueError) as context:
            stdout, stderr = run_command("az", ["cdf", "hook", "fail", "-w", self.work_dir])
        self.assertEqual(stderr, "")
        self.assertEqual("", stdout.replace('\n', ''))
        self.assertIn("non-zero", str(context.exception))

    def test_3_cdf_down_0(self):
        stdout, stderr = run_command("az", ["cdf", "down", "-w", self.work_dir,  "--yes"])
        stdout_lines = list(filter(None, stdout.split("\n")))  # remove empty lines and split into list
        self.assertEqual(stderr, "")
        self.assertEqual(4, len(stdout_lines))  # 4 lines in stdout
        self.assertIn("De-provisioning", stdout_lines[0])  # 1st line
        self.assertIn('"post-down", "pre-down"', stdout_lines[1])  # 2nd line
        self.assertIn('"post-down", "pre-down"', stdout_lines[2])  # 3ed line
        self.assertIn("post-down", stdout_lines[3])  # 3ed line
        # check the hook log and compare content
        with open(self.hook_log, 'r') as file:
            data = file.read().replace('\n', '')
            self.assertEqual(data, "pre-downall-downall-downpost-down")

    def test_3_cdf_down_1_status(self):
        stdout, stderr = run_command("az", ["cdf", "status", "-w", self.work_dir])
        json_stdout = json.loads(stdout)
        self.assertEqual(json_stdout["Phase"], 'down')
        self.assertEqual(json_stdout["Status"], 'success')
        self.assertEqual(stderr, "")

    def test_3_cdf_down_2_resource_removed(self):
        with self.assertRaises(ValueError) as context:
            run_command("az",["resource", "show", "--id", self.__class__.resource_id])
        self.assertIn('non-zero', str(context.exception))
