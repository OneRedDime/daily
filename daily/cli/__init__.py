import importlib
import inspect
import os


_pkg_root = os.path.dirname(os.path.abspath(__file__))


def get_subcommands(pkg_root):
    """ List available subcommands within a module.

    Args:
        pkg_root: a path to the root of the subpackage to be searched.

    Returns:
        A list of strings representing the names of all subpackages
        present in the given directory.
    """
    return [dname for dname in sorted(os.listdir(pkg_root)) if
            os.path.isdir(os.path.join(pkg_root, dname))
            and '__pycache__' not in dname]


def build_out_subparsers(subparser_hook):
    """ Adds subcommand subparsers to a parent parser.

    This command will dynamically search all subpackages of `daily.cli`,
    import the `parser` submodule of every subpackage, and execute a
    function named `add_*_subparser` on a `subparsers` object returned
    by `ArgumentParser.add_subparsers()`. This will have the effect of
    creating all subparsers for all available subcommands.

    Args:
        subparser_hook: an object returned by
            ArgumentParser.add_subparsers().

    Returns:
        None
    """
    parser_modules = [importlib.import_module(f'daily.cli.{x}.parser') for x in get_subcommands(_pkg_root)]
    parser_builders = []
    for module in parser_modules:
        fns = [item for name, item in inspect.getmembers(module)
               if inspect.isfunction(item) and name == 'add_subparser']
        if len(fns) != 1:
            raise RuntimeError(f'Too many functions in {module.__name__}')
        else:
            parser_builders.extend(fns)

    for builder in parser_builders:
        builder(subparser_hook)
