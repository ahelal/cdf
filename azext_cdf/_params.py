""" Command Arguments file """


def load_arguments(self, _):
    with self.argument_context("cdf") as context:
        context.argument("config", options_list=["--config", "-c"], help="config file for cdf", default=".cdf.yml")
        context.argument("working_dir", options_list=["--work-dir", "-w"], help="Change working directory", default=False)
        context.argument("state_file", options_list=["--state", "-s"], help="State file", default=False)

    with self.argument_context("cdf init") as context:
        context.argument("force", options_list=["--force", "-f"], help="force overwrite of files", default=False)
        context.argument("example", options_list=["--example", "-e"], help="create a demo files", default=False)

    with self.argument_context("cdf up") as context:
        context.argument("prompt", options_list=["--ask", "-a"], help="Ask interactively for missing parameters if any", default=False)
        context.argument("remove_tmp", options_list=["--remove-dir", "-r"], help="Remove temporary directory content and recreate the dir", default=False)

    with self.argument_context("cdf down") as context:
        context.argument("remove_tmp", options_list=["--remove-tmp", "-r"], help="Remove temp directory content and recreate the dir", default=False)

    with self.argument_context("cdf status") as context:
        context.argument("events", options_list=["--events", "-e"], help="Print also events", default=False)
    with self.argument_context("debug_interpolate_handler") as context:
        context.argument("phase", options_list=["--phase", "-p"], help="test your jinja2 expression", default=2)

    with self.argument_context("cdf hook") as context:
        context.positional("hook_args", nargs="*", help="Hook name to run.", default=None)

        context.argument("confirm", options_list=["--yes", "-y"], help="Run hook even if an phase or status are not ready. (Might corrupt state)", default=None)
