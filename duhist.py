#!/usr/bin/env python3
"""
Run duhist directly from a source checkout (e.g. ./duhist.py).

The implementation lives in du_histogram.py; installed copies use the
'duhist' (or 'duhist.py') command instead of this file.
"""

import sys

from du_histogram import main

if __name__ == "__main__":
    sys.exit(main())
