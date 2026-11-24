"""Shared by the scripts in this folder that check a dashboard (dashbuilt.py, dashcheck.py): the dashboard level
on record in forge-work/levels.json, which ../forge/level.py writes.

Not a script: no command line. The scripts next to it import it by name, which works because Python puts a
script's own folder first on sys.path. Standard library only.
"""

import json
import os

MAX_BYTES = 1000000  # bigger files are not read
ASK = ("Ask the user how rich the dashboard should be, 1 to 5 (python3 ../forge/level.py show dashboard has "
       "the table), then record it: python3 ../forge/level.py set dashboard N --said '<their words>'")


def level_on_record(path):
    """The dashboard level in forge-work/levels.json (see the top). ValueError, saying to ask, when there is none."""
    folder = os.path.dirname(os.path.abspath(path))
    record = os.path.join(folder if os.path.basename(folder) == "forge-work" else "forge-work", "levels.json")
    try:
        if os.path.islink(os.path.dirname(os.path.abspath(record))) or os.path.islink(record):
            raise ValueError("it is a link, so it was not read: tell the user")
        if not os.path.isfile(record) or os.path.getsize(record) > MAX_BYTES:
            raise ValueError("there is no such file (of at most 1 MB)")
        with open(record, encoding="utf-8", errors="replace") as handle:
            level = json.load(handle)["dashboard"]["level"]
        if type(level) is int and 1 <= level <= 5:
            return level
        raise ValueError("its dashboard level is %r, not 1 to 5" % (level,))
    except (OSError, ValueError, LookupError, TypeError, RecursionError) as error:
        raise ValueError("no dashboard level on record in %s (%s). %s" % (record, error, ASK))
