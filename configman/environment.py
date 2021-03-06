# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from os import environ

from configman.dotdict import configman_keys

environment = configman_keys(environ)
environment.always_ignore_mismatches = True

