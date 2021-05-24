''' Utils test'''

import unittest
import tempfile
import shutil
from azext_cdf.utils import file_exists
# pylint: disable=missing-class-docstring,missing-function-docstring
class TestFileExits(unittest.TestCase):
    def setUp(self):
        self.dirpath = tempfile.mkdtemp()
        self.file = f'{self.dirpath}/example.txt'
        with open(self.file, 'w') as the_file:
            the_file.write('Hello')
    def test_file_exits(self):
        self.assertTrue(file_exists(self.file))
    def test_file_doest_not_exits(self):
        self.assertFalse(file_exists(f'{self.file}aa'))
    def test_dir_exits(self):
        self.assertFalse(file_exists(self.dirpath))
        # with self.assertRaises(TypeError):
        #     s.split(2)
        # self.assertEqual('foo'.upper(), 'FOO')
        # self.assertFalse('Foo'.isupper())

    def tearDown(self):
        shutil.rmtree(self.dirpath)

if __name__ == '__main__':
    unittest.main()
