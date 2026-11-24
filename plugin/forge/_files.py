"""Shared by the scripts in this folder (gate.py, level.py): a file in forge-work written whole, or not at all.

Not a script: no command line. The scripts next to it import it by name, which works because Python puts a
script's own folder first on sys.path. Standard library only.
"""

import os
import tempfile


def write_whole(folder, name, text, newline=None):
    """Write TEXT to FOLDER/NAME whole: a temporary file next to it, then a rename over the old one, which
    replaces a link there instead of following it. NEWLINE as open() takes it: "\\n" writes the same line ends
    on every system, None those of the system."""
    handle, temp = tempfile.mkstemp(prefix=".forge-", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline=newline) as out:
            out.write(text)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, os.path.join(folder, name))
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
