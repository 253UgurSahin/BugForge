"""Shared by the scripts in this folder (lookcheck.py, workcheck.py): the start of a command line of checks.

Not a script: no command line of its own. The scripts next to it import it by name, which works because Python
puts a script's own folder first on sys.path. Standard library only.
"""

import argparse
import sys


def checks_parser(doc):
    """Set the console up so that what it cannot show comes out as \\u escapes, not a crash, and return
    (parser, its subcommands) for a script whose docstring is DOC and that runs one CHECK of several."""
    for stream in (sys.stdout, sys.stderr):
        getattr(stream, "reconfigure", lambda **_: None)(errors="backslashreplace")
    parser = argparse.ArgumentParser(description=doc, formatter_class=argparse.RawDescriptionHelpFormatter)
    return parser, parser.add_subparsers(dest="command", metavar="CHECK", required=True)
