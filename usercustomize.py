
"""
The name of this script needs to stay `usercustomize.py` for it to be run by
`site.py` on startup (though there are circumstances when it is not run).
"""

from __future__ import print_function

import sys

from util import script_is_attended, is_dev_file
from excepthook import excepthook, set_file_filter


# Note: be careful not to always hook in somthing that only works for
# Python3 (or at least test at runtime).
if script_is_attended():
    # This takes a function that returns True for files we want to emphasize
    # in our tracebacks.
    set_file_filter(is_dev_file)
    sys.excepthook = excepthook

