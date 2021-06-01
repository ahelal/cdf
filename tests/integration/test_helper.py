''' test helper functions '''
import subprocess
import os

def run_command(bin_path, args=None, interactive=False, cwd=None):
    ''' Run process '''
    process = None
    stdout = None
    stderr = None
    try:
        cmd_args = [rf"{bin_path}"] + args
        if interactive:
            subprocess.check_call(cmd_args, cwd=cwd)
            return "", ""
        process = subprocess.run(cmd_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd, check=False)
        stdout = process.stdout.decode('utf-8')
        stderr = process.stderr.decode('utf-8')
        process.check_returncode()
        return stdout, stderr
    except subprocess.CalledProcessError as error:
        context = f"Run command error. {str(error)}\nstdout: {stdout}\nstderr: {stderr}"
        if stdout:
            context = f"{context}\nstdout:{stdout}"
        if stderr:
            context = f"{context}\nstdout:{stderr}"
        raise ValueError(error) from error


def remove_file(filepath):
    ''' remove file and ignore errors'''
    try:
        os.remove(filepath)
    except OSError:
        pass
