''' tester test'''

import unittest
import tempfile
import os
import shutil
import random
import string
from mock import patch
from knack.util import CLIError
from azext_cdf.tester import run_test
from azext_cdf.parser import ConfigParser, CONFIG_STATE_FILEPATH, CONFIG_STATE_FILENAME
from azext_cdf._supporter_test import assert_state

# pylint: disable=C0111

def assert_run_count(self, run_dict):
    for assert_key, assert_value in run_dict.items():
        self.assertEqual(assert_key.call_count, assert_value)

class TesterNoUpgrade(unittest.TestCase):
    def setUp(self):
        self.config =  {"name": "cdf_simple", "resource_group": "rg", "location": "loc"}
        self.config["tests"] =  {"default": {}, "patch": {}}
        self.tmpdir = tempfile.mkdtemp()
        self.config["tmp_dir"] = self.tmpdir
        self.state_file = f"{self.tmpdir}/{''.join(random.sample(string.ascii_lowercase, 25))}.json"
        self.config[CONFIG_STATE_FILENAME] = os.path.basename(self.state_file)
        self.config[CONFIG_STATE_FILEPATH] = f"file://{os.path.dirname(self.state_file)}"
        self.tests = ["default", "patch"]
        self.upgrades = ["fresh"]

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    @patch.object(ConfigParser, '_read_config')
    @patch('azext_cdf.tester._run_expect_tests')
    @patch('azext_cdf.tester._run_de_provision')
    @patch('azext_cdf.tester._run_provision')
    @patch('azext_cdf.tester._run_hook')
    def test_simple_down_strategy_always(self, _run_hook, _run_provision, _run_de_provision, _run_expect_tests, _read_config):
        self.config["name"] = 'test_simple_down_strategy_always'
        _read_config.return_value = self.config
        cobj = ConfigParser("/a/b/.cdf.yml")
        results = run_test(None, cobj=cobj, config="/a/b/.cdf.yml", exit_on_error=False, test_args=["default", "patch"], working_dir=os.getcwd(),
                          down_strategy="always", upgrade_strategy="all")

        assert_run_count(self, {_run_hook: 0, _run_provision: 2, _run_de_provision: 2, _run_expect_tests: 4})
        for upgrade_path in self.upgrades:
            self.assertEqual(len(results), len(self.upgrades))
            self.assertIn(upgrade_path, results)
            for test in self.tests:
                for phase in ["provisioning", "provision expect", "de-provisioning", "de-provision expect"]:
                    self.assertFalse(results[upgrade_path][test][phase]["failed"])
                self.assertIn(test, results[upgrade_path])
                self.assertFalse(results[upgrade_path][test]["failed"])
                assert_state(self, f"{self.tmpdir}/test_{upgrade_path}_{test}_state.json", {"name": f'{self.config["name"]}_{test}_test'})
        assert_state(self, self.state_file, {"name": self.config["name"]})
        self.assertEqual(cobj.name, self.config["name"])
        self.assertEqual(cobj.tests, self.tests)

    @patch.object(ConfigParser, '_read_config')
    @patch('azext_cdf.tester._run_expect_tests')
    @patch('azext_cdf.tester._run_de_provision')
    @patch('azext_cdf.tester._run_provision')
    @patch('azext_cdf.tester._run_hook')
    def test_simple_down_strategy_success(self, _run_hook, _run_provision, _run_de_provision, _run_expect_tests, _read_config):
        self.config["name"] = 'test_simple_down_strategy_success'
        _read_config.return_value = self.config
        cobj = ConfigParser("/a/b/.cdf.yml")
        results = run_test(None, cobj=cobj, config="/a/b/.cdf.yml", exit_on_error=False, test_args=["default", "patch"], working_dir=os.getcwd(),
                          down_strategy="success", upgrade_strategy="all")

        assert_run_count(self, {_run_hook: 0, _run_provision: 2, _run_de_provision: 2, _run_expect_tests: 4})
        for upgrade_path in self.upgrades:
            self.assertEqual(len(results), len(self.upgrades))
            self.assertIn(upgrade_path, results)
            for test in self.tests:
                for phase in ["provisioning", "provision expect", "de-provisioning", "de-provision expect"]:
                    self.assertFalse(results[upgrade_path][test][phase]["failed"])
                self.assertIn(test, results[upgrade_path])
                self.assertFalse(results[upgrade_path][test]["failed"])
                assert_state(self, f"{self.tmpdir}/test_{upgrade_path}_{test}_state.json", {"name": f'{self.config["name"]}_{test}_test'})
        assert_state(self, self.state_file, {"name": self.config["name"]})
        self.assertEqual(cobj.name, self.config["name"])
        self.assertEqual(cobj.tests, self.tests)

    @patch.object(ConfigParser, '_read_config')
    @patch('azext_cdf.tester._run_expect_tests')
    @patch('azext_cdf.tester._run_de_provision')
    @patch('azext_cdf.tester._run_provision')
    @patch('azext_cdf.tester._run_hook')
    def test_simple_down_strategy_never(self, _run_hook, _run_provision, _run_de_provision, _run_expect_tests, _read_config):
        self.config["name"] = 'test_simple_down_strategy_never'
        _read_config.return_value = self.config
        cobj = ConfigParser("/a/b/.cdf.yml")
        results = run_test(None, cobj=cobj, config="/a/b/.cdf.yml", exit_on_error=False, test_args=["default", "patch"], working_dir=os.getcwd(),
                          down_strategy="never", upgrade_strategy="all")

        assert_run_count(self, {_run_hook: 0, _run_provision: 2, _run_de_provision: 0, _run_expect_tests: 2})
        for upgrade_path in self.upgrades:
            self.assertEqual(len(results), len(self.upgrades))
            self.assertIn(upgrade_path, results)
            for test in self.tests:
                for phase in ["provisioning", "provision expect"]:
                    self.assertFalse(results[upgrade_path][test][phase]["failed"])
                for phase in ["de-provisioning", "de-provision expect"]:
                    self.assertFalse(results["fresh"][test].get(phase, False))
                self.assertIn(test, results[upgrade_path])
                self.assertFalse(results[upgrade_path][test]["failed"])
                assert_state(self, f"{self.tmpdir}/test_{upgrade_path}_{test}_state.json", {"name": f'{self.config["name"]}_{test}_test'})
        assert_state(self, self.state_file, {"name": self.config["name"]})
        self.assertEqual(cobj.name, self.config["name"])
        self.assertEqual(cobj.tests, self.tests)

    @patch('azext_cdf.tester.de_provision')
    @patch.object(ConfigParser, '_read_config')
    @patch('azext_cdf.tester._run_expect_tests')
    @patch('azext_cdf.tester._run_de_provision')
    @patch('azext_cdf.tester._run_provision')
    @patch('azext_cdf.tester._run_hook')
    def test_simple_failed_provision(self, _run_hook, _run_provision, _run_de_provision, _run_expect_tests, _read_config, de_provision):
        self.config["name"] = 'test_simple_failed_provision'
        _read_config.return_value = self.config
        cobj = ConfigParser("/a/b/.cdf.yml")
        _run_provision.side_effect = CLIError("Nooo")
        results = run_test(None, cobj=cobj, config="/a/b/.cdf.yml", exit_on_error=False, test_args=["default", "patch"], working_dir=os.getcwd(),
                          down_strategy="always", upgrade_strategy="all")

        assert_run_count(self, {_run_hook: 0, _run_provision: 2, _run_de_provision: 0, _run_expect_tests: 0, de_provision: 2})
        for upgrade_path in self.upgrades:
            self.assertEqual(len(results), len(self.upgrades))
            self.assertIn(upgrade_path, results)
            for test in self.tests:
                for phase in ["provisioning"]:
                    self.assertTrue(results[upgrade_path][test][phase]["failed"])
                for phase in ["de-provisioning", "de-provision expect", "provision expect"]:
                    self.assertFalse(results["fresh"][test].get(phase, False))
                self.assertIn(test, results[upgrade_path])
                self.assertTrue(results[upgrade_path][test]["failed"])
                assert_state(self, f"{self.tmpdir}/test_{upgrade_path}_{test}_state.json", {"name": f'{self.config["name"]}_{test}_test'})
        assert_state(self, self.state_file, {"name": self.config["name"]})
        self.assertEqual(cobj.name, self.config["name"])
        self.assertEqual(cobj.tests, self.tests)

    @patch('azext_cdf.tester.de_provision')
    @patch.object(ConfigParser, '_read_config')
    @patch('azext_cdf.tester._run_expect_tests')
    @patch('azext_cdf.tester._run_de_provision')
    @patch('azext_cdf.tester._run_provision')
    @patch('azext_cdf.tester._run_hook')
    def test_simple_failed_provision_exit_on_error(self, _run_hook, _run_provision, _run_de_provision, _run_expect_tests, _read_config, de_provision):
        self.config["name"] = 'test_simple_failed_provision'
        _read_config.return_value = self.config
        cobj = ConfigParser("/a/b/.cdf.yml")
        _run_provision.side_effect = CLIError("Nooo")
        with self.assertRaises(CLIError) as context:
            run_test(None, cobj=cobj, config="/a/b/.cdf.yml", exit_on_error=True, test_args=["default", "patch"], working_dir=os.getcwd(),
                          down_strategy="always", upgrade_strategy="all")
            self.assertIn('default', context)
        assert_run_count(self, {_run_hook: 0, _run_provision: 1, _run_de_provision: 0, _run_expect_tests: 0, de_provision: 1})
        # test with down_strategy success only
        _run_provision.reset_mock()
        de_provision.reset_mock()
        with self.assertRaises(CLIError) as context:
            run_test(None, cobj=cobj, config="/a/b/.cdf.yml", exit_on_error=True, test_args=["default", "patch"], working_dir=os.getcwd(),
                          down_strategy="success", upgrade_strategy="all")
            self.assertIn('default', context)
        assert_run_count(self, {_run_hook: 0, _run_provision: 1, _run_de_provision: 0, _run_expect_tests: 0, de_provision: 0})

        self.assertEqual(cobj.name, self.config["name"])
        self.assertEqual(cobj.tests, self.tests)

    @patch.object(ConfigParser, '_read_config')
    @patch('azext_cdf.tester._run_expect_tests')
    @patch('azext_cdf.tester._run_de_provision')
    @patch('azext_cdf.tester._run_provision')
    @patch('azext_cdf.tester._run_hook')
    def test_simple_upgrade_strategy_only_upgrade(self, _run_hook, _run_provision, _run_de_provision, _run_expect_tests, _read_config):
        self.config["name"] = 'test_simple_upgrade_strategy_only_upgrade'
        _read_config.return_value = self.config
        cobj = ConfigParser("/a/b/.cdf.yml")
        results = run_test(None, cobj=cobj, config="/a/b/.cdf.yml", exit_on_error=False, test_args=["default", "patch"], working_dir=os.getcwd(),
                          down_strategy="always", upgrade_strategy="upgrade")

        assert_run_count(self, {_run_hook: 0, _run_provision: 0, _run_de_provision: 0, _run_expect_tests: 0})
        self.assertEqual(len(results), 0)
        assert_state(self, self.state_file, {"name": self.config["name"]})
        self.assertEqual(cobj.name, self.config["name"])
        self.assertEqual(cobj.tests, self.tests)


# class TesteUpgrade(unittest.TestCase):
#     def setUp(self):
#         self.config =  {"name": "cdf_simple", "resource_group": "rg", "location": "loc"}
#         self.config["tests"] =  {"default": {}, "patch": {}}
#         self.tmpdir = tempfile.mkdtemp()
#         self.config["tmp_dir"] = self.tmpdir
#         self.state_file = f"{self.tmpdir}/{''.join(random.sample(string.ascii_lowercase, 25))}.json"
#         self.config[CONFIG_STATE_FILENAME] = os.path.basename(self.state_file)
#         self.config[CONFIG_STATE_FILEPATH] = f"file://{os.path.dirname(self.state_file)}"
#         self.tests = ["default", "patch"]
#         self.upgrades = ["fresh"]

#     def tearDown(self):
#         shutil.rmtree(self.tmpdir)

#     @patch.object(ConfigParser, '_read_config')
#     @patch('azext_cdf.tester._run_expect_tests')
#     @patch('azext_cdf.tester._run_de_provision')
#     @patch('azext_cdf.tester._run_provision')
#     @patch('azext_cdf.tester._run_hook')
#     def test_simple_upgrade_strategy_only_upgrade(self, _run_hook, _run_provision, _run_de_provision, _run_expect_tests, _read_config):
#         self.config["name"] = 'test_simple_upgrade_strategy_only_upgrade'
#         _read_config.return_value = self.config
#         cobj = ConfigParser("/a/b/.cdf.yml")
#         results = run_test(None, cobj=cobj, config="/a/b/.cdf.yml", exit_on_error=False, test_args=["default", "patch"], working_dir=os.getcwd(),
#                           down_strategy="always", upgrade_strategy="upgrade")

#         assert_run_count(self, {_run_hook: 0, _run_provision: 2, _run_de_provision: 2, _run_expect_tests: 4})
#         for upgrade_path in self.upgrades:
#             self.assertEqual(len(results), len(self.upgrades))
#             self.assertIn(upgrade_path, results)
#             for test in self.tests:
#                 for phase in ["provisioning", "provision expect", "de-provisioning", "de-provision expect"]:
#                     self.assertFalse(results[upgrade_path][test][phase]["failed"])
#                 self.assertIn(test, results[upgrade_path])
#                 self.assertFalse(results[upgrade_path][test]["failed"])
#                 assert_state(self, f"{self.tmpdir}/test_{upgrade_path}_{test}_state.json", {"name": f'{self.config["name"]}_{test}_test'})
#         assert_state(self, self.state_file, {"name": self.config["name"]})
#         self.assertEqual(cobj.name, self.config["name"])
#         self.assertEqual(cobj.tests, self.tests)


# upgrade choices=['all', 'fresh', 'upgrade'])
# down choices=['success', 'always', 'never'])

if __name__ == '__main__':
    unittest.main()


# TODO Write tests for
# _run_single_test
# _expect_cmd_exec
# _expect_assert_exec
# _phase_cordinator
