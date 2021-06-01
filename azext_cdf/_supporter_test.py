''' Utils test'''

import unittest
import tempfile
import shutil
import os
import random
import string
from azext_cdf._def import CONFIG_STATE_FILEPATH, CONFIG_STATE_FILENAME

# pylint: disable=C0111
class BasicParser(unittest.TestCase):
    def setUp(self):
        self.dirpath = tempfile.mkdtemp()
        self.config = {"name": "cdf_simple", "resource_group": "rg", "location": "loc"}
        self.config['tmp_dir'] = self.dirpath
        self.state_file = f"{self.dirpath}/{''.join(random.sample(string.ascii_lowercase, 25))}.json"
        self.override_config = {
            CONFIG_STATE_FILENAME: os.path.basename(self.state_file),
            CONFIG_STATE_FILEPATH: f"file://{os.path.dirname(self.state_file)}",
        }
    def tearDown(self):
        shutil.rmtree(self.dirpath)

class FullParser(BasicParser):
    def setUp(self):
        self.dirpath = tempfile.mkdtemp()
        self.config = {"name": "cdf_simple", "resource_group": "rg", "location": "loc"}
        self.config['tmp_dir'] = self.dirpath
        self.state_file = f"{self.dirpath}/{''.join(random.sample(string.ascii_lowercase, 25))}.json"
    def tearDown(self):
        shutil.rmtree(self.dirpath)
