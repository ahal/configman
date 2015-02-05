# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# this will be expanded in the future when additional command line libraries
# are supported

try:
    import argparse as command_line
    from configman.def_sources.for_argparse import ArgumentParser
except ImportError:
    import getopt as command_line

