''' Utils test'''

import unittest
import tempfile
import shutil
from knack.util import CLIError
from azext_cdf.utils import file_exists, run_command

# pylint: disable=C0111
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

class TestRunCommand(unittest.TestCase):
    def setUp(self):
        self.dirpath = tempfile.mkdtemp()
    def test_no_error_with_no_output(self):
        with open(f'{self.dirpath}/noerror.sh', 'w') as no_error:
            no_error.write("exit 0")
        stdout, stderr = run_command("/bin/sh", ["-e", f'{self.dirpath}/noerror.sh'])
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
    def test_no_error_with_output(self):
        with open(f'{self.dirpath}/noerror.sh', 'w') as no_error:
            no_error.write("echo 1\n>&2 echo 2\nexit 0")
        stdout, stderr = run_command("/bin/sh", ["-e", f'{self.dirpath}/noerror.sh'])
        self.assertEqual(stdout, "1\n")
        self.assertEqual(stderr, "2\n")
    def test_error_with_output(self):
        with open(f'{self.dirpath}/noerror.sh', 'w') as no_error:
            no_error.write("echo _1_\n>&2 echo _2_\nexit 1")

        with self.assertRaises(CLIError) as context:
            run_command("/bin/sh", ["-e", f'{self.dirpath}/noerror.sh'])
        self.assertIn("status", str(context.exception))
        self.assertIn("_1_\n", str(context.exception))
        self.assertIn("_2_\n", str(context.exception))

if __name__ == '__main__':
    unittest.main()
