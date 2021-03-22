
def load_arguments(self, _):
    with self.argument_context('cdf') as c:
        c.argument('config',
                    options_list=['--config', '-c'],
                    help='config file for cdf',
                    default='.cdf.yml')
        c.argument('working_dir',
                    options_list=['--work-dir', '-w'],
                    help='Change working directory',
                    default=False)

    with self.argument_context('cdf init') as c:
        c.argument('force',
                    options_list=['--force', '-f'],
                    help='force overwrite of files',
                    default=False)
        c.argument('example',
                    options_list=['--example', '-e'],
                    help='create a demo files',
                    default=False)

    with self.argument_context('cdf up') as c:
        c.argument('prompt',
                    options_list=['--ask', '-a'],
                    help='Ask interactively for missing parameters if any',
                    default=False)
        c.argument('rtmp',
                    options_list=['--remove-dir', '-r'],
                    help='Remove temporary dirctory content and recreate the dir',
                    default=False)

    with self.argument_context('cdf down') as c:
        c.argument('rtmp',
                    options_list=['--remove-tmp', '-r'],
                    help='Remove temp dirctory content and recreate the dir',
                    default=False)

    with self.argument_context('cdf status') as c:
        c.argument('events',
                    options_list=['--events', '-e'],
                    help='Print also events',
                    default=False)
    with self.argument_context('debug_interpolate_handler') as c:
        c.argument('phase',
                    options_list=['--phase', '-p'],
                    help='test your jinj2 expression',
                    default=2)


    with self.argument_context('cdf hook') as c:
        c.positional('hook_args', 
                    nargs='*',
                    help='Hook name to run.',
                    default=None
                    )
        # c.argument('hook',
        #             options_list=['--name', '-n'],
        #             help='hook name',
        #             default=None)
        # c.argument('args',
        #             options_list=['--args', '-a'],
        #             help='hook arguments',
        #             default=None)
        c.argument('confirm',
                    options_list=['--yes', '-y'],
                    help='Run hook even if an phase or status are not ready. (Might corrupt state)',
                    default=None)
