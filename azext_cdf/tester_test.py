''' tester test'''

import unittest
# import tempfile
# import shutil
# import os
# import json
# import random
# import string
from mock import patch
# from knack.util import CLIError
from azext_cdf.parser import ConfigParser

# pylint: disable=C0111
class SimpleParser(unittest.TestCase):
    @patch.object(ConfigParser, '_read_config')
    def test_min_default(self, mock_read_config):
        pass


if __name__ == '__main__':
    unittest.main()
