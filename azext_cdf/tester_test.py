''' tester test'''

import unittest
import tempfile
import copy
import os
import shutil
import random
import string
from unittest.mock import patch
from pathlib import Path
from knack.util import CLIError
from azext_cdf.tester import run_test, _manage_git_upgrade, _prepare_test_runner_dirs
from azext_cdf.parser import ConfigParser, CONFIG_STATE_FILEPATH
from azext_cdf._supporter_test import assert_state
from azext_cdf.utils import run_command

# pylint: disable=C0111

def assert_run_count(self, run_dict):
    for assert_key, assert_value in run_dict.items():
        self.assertEqual(assert_key.call_count, assert_value)

class robj():
    def interpolate(self, **cargs):
        return cargs['template']

class TesterNoUpgrade(unittest.TestCase):
    def setUp(self):
        self.config =  {"name": "cdf_simple", "resource_group": "rg", "location": "loc"}
        self.config["tests"] =  {"default": {}, "patch": {}}
        self.tmpdir = tempfile.mkdtemp()
        self.config["tmp_dir"] = self.tmpdir
        self.state_file = f"{self.tmpdir}/{''.join(random.sample(string.ascii_lowercase, 25))}.json"
        self.config[CONFIG_STATE_FILEPATH] = f"file://{self.state_file}"
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


class TestManageGitUpgrade(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.upgrade_config = {"name": "x1", "type": "git", "path": "/"}
        self.upgrade_config["git"] = {"repo": "https://github.com/ahelal/git-example.git"}
# branch
# tag
# key
    def test_reuse_manage_git_upgrade(self):
        # new branch
        upgrade_config = copy.deepcopy(self.upgrade_config)
        upgrade_config["git"]['branch'] = "new"
        gitdir_new = _manage_git_upgrade(upgrade_config, self.tmpdir, upgrade_config["name"], reuse_dir=True)
        git_hash, _ = run_command("git",["show", '--pretty=format:"%H"', "--no-patch"], cwd=gitdir_new)
        self.assertEqual(git_hash.replace('"',""), "1c247b950f1655ad84d2cc8fc4f594c6a6afb402")

        # tag v0.0.2 branch
        upgrade_config = copy.deepcopy(self.upgrade_config)
        upgrade_config["git"]['tag'] = "v0.0.2"
        gitdir_v0_0_2 = _manage_git_upgrade(upgrade_config, self.tmpdir, upgrade_config["name"], reuse_dir=True)
        git_hash, _ = run_command("git",["show", '--pretty=format:"%H"', "--no-patch"], cwd=gitdir_v0_0_2)
        self.assertEqual(git_hash.replace('"',""), "c0659f4bd2f44a917e5bc77ae41aeaa542133103")
        self.assertEqual(gitdir_new, gitdir_v0_0_2)

        # main branch
        upgrade_config = copy.deepcopy(self.upgrade_config)
        upgrade_config["git"]['branch'] = "main"
        gitdir_main = _manage_git_upgrade(upgrade_config, self.tmpdir, upgrade_config["name"], reuse_dir=True)
        git_hash, _ = run_command("git",["show", '--pretty=format:"%H"', "--no-patch"], cwd=gitdir_main)
        self.assertEqual(git_hash.replace('"',""), "a0281435a7e1880921ae59399c98b3d04473e471")
        self.assertEqual(gitdir_v0_0_2, gitdir_main)

        # commit
        upgrade_config = copy.deepcopy(self.upgrade_config)
        upgrade_config["git"]['commit'] = "8131806c7906a252573ef329433dd5e91d708607"
        gitdir_commit = _manage_git_upgrade(upgrade_config, self.tmpdir, upgrade_config["name"], reuse_dir=True)
        git_hash, _ = run_command("git",["show", '--pretty=format:"%H"', "--no-patch"], cwd=gitdir_main)
        self.assertEqual(git_hash.replace('"',""), "8131806c7906a252573ef329433dd5e91d708607")
        self.assertEqual(gitdir_main, gitdir_commit)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

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

class TestRunner(unittest.TestCase):
    def setUp(self):
        self.tmpdir = os.path.realpath(tempfile.mkdtemp())
        self.a_dir = os.path.join(self.tmpdir, "a")
        self.empty_dir = os.path.join(self.a_dir, "a")
        self.no_test_dir = os.path.join(self.a_dir, "b")
        self.b_dir = os.path.join(self.tmpdir, "b")
        self.b_a_dir = os.path.join(self.b_dir, "b")
        self.dir_struct = { self.tmpdir: ["0.test"],
                            self.empty_dir: [],
                            self.no_test_dir: ["no.tr", "yes.asd"],
                            self.a_dir:["1.test", "2.test", "3.txt", "4.py"],
                            self.b_dir:["5.test", "6.test", "7.txt", "8.py"],
                            self.b_a_dir:["9.test", "10.txt", "11.py"],
                            }

        for directory in self.dir_struct:
            try:
                os.makedirs(directory)
            except OSError:
                pass

            for touch_file in self.dir_struct[directory]:
                Path(os.path.join(directory, touch_file)).touch()
        self.cobj = robj()
        # def _prepare_test_runner_dirs(cobj, test_name, files, ext_filter):

    def test_prepare_runner_none(self):
        self.assertIsNone(_prepare_test_runner_dirs(self.cobj, "unittest", None, None))

    def test_prepare_runner_empty_dir(self):
        self.assertEqual(_prepare_test_runner_dirs(self.cobj, "unittest", self.empty_dir, "*"), [])
    def test_prepare_runner_no_filters(self):
        all_dirs = [os.path.join(self.a_dir, sf) for sf in self.dir_struct[self.a_dir]]
        self.assertListEqual(sorted(_prepare_test_runner_dirs(self.cobj, "unittest", self.a_dir, "*")), sorted(all_dirs))
    def test_prepare_runner_filtered(self):
        all_files = [os.path.join(self.b_dir, "5.test"), os.path.join(self.b_dir, "6.test")]
        self.assertListEqual(sorted(_prepare_test_runner_dirs(self.cobj, "unittest", self.b_dir, "*.test")), sorted(all_files))
        # _prepare_test_runner_dirs
    def test_prepare_runner_relative(self):
        fqdn = [os.path.join(self.b_dir, "8.py")]
        os.chdir(self.b_dir)
        self.assertListEqual(_prepare_test_runner_dirs(self.cobj, "unittest", ".", "*.py"), fqdn)

    def test_prepare_runner_empty_filter(self):
        self.assertListEqual(sorted(_prepare_test_runner_dirs(self.cobj, "unittest", ".", "*.nonrow")), [])

if __name__ == '__main__':
    unittest.main()


# TODO Write tests for
# _run_single_test
# _expect_runner_exec
# _expect_assert_exec
# _phase_cordinator
