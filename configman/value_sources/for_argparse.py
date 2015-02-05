# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""This module implements a configuration value source from the commandline
implemented using argparse.  This was a difficult module to make because of
some fundemental differences with the way that configman and argparse set up
their respective priorities.

One of the primary problems is that both configman and argparse have their own
data definition specs.  Configman has Options while argparse has Actions.  Both
libraries can use their own specs, so a translation layer had to be created.
"""

import argparse

import collections

from configman.option import Option
from configman.dotdict import (
    DotDict,
    iteritems_breadth_first,
)
from configman.converters import boolean_converter, to_str
from configman.namespace import Namespace

from source_exceptions import CantHandleTypeException

is_command_line_parser = True

can_handle = (
    argparse.ArgumentParser,
    argparse,
)


#==============================================================================
class ControlledErrorReportingArgumentParser(argparse.ArgumentParser):
    #--------------------------------------------------------------------------
    def __init__(self, *args, **kwargs):
        super(ControlledErrorReportingArgumentParser, self).__init__(
            *args, **kwargs
        )
        self.required_config = Namespace()

    #--------------------------------------------------------------------------
    def error(self, message):
        if (
            "not allowed" in message
            or "ignored" in message
            or "expected" in message
            or "invalid" in message
            or self.add_help
        ):
            # when we have "help" then we must also have proper error
            # processing.  Without "help", we suppress the errors by
            # doing nothing here
            super(ControlledErrorReportingArgumentParser, self).error(message)

    #--------------------------------------------------------------------------
    def add_argument_from_option(self, qualified_name, option):
        if option.foreign_data is not None and "argparse" in option.foreign_data:
            args = option.foreign_data.argparse.args
            kwargs = option.foreign_data.argparse.kwargs
            action = super(
                ControlledErrorReportingArgumentParser,
                self
            ).add_argument(
                *args,
                **kwargs
            )
            return action

        opt_name = qualified_name

        if option.is_argument:  # is positional argument
            option_name = opt_name
        else:
            option_name = '--%s' % opt_name

        if option.short_form:
            option_short_form = '-%s' % option.short_form
            args = (option_name, option_short_form)
        else:
            args = (option_name,)

        kwargs = DotDict()
        if option.from_string_converter in (bool, boolean_converter):
            kwargs.action = 'store_true'
        else:
            kwargs.action = 'store'

        kwargs.default = argparse.SUPPRESS
        kwargs.help = option.doc
        if not option.is_argument:
            kwargs.dest = opt_name
        action = \
            super(ControlledErrorReportingArgumentParser, self).add_argument(
                *args,
                **kwargs
            )
        return action

    #--------------------------------------------------------------------------
    def parse_args(self, args=None, namespace=None, object_hook=None):
        proposed_config = \
            super(ControlledErrorReportingArgumentParser, self).parse_args(
                args,
                namespace
            )
        return self._edit_config(proposed_config, object_hook)

    #--------------------------------------------------------------------------
    def parse_known_args(self, args=None, namespace=None, object_hook=None):
        result = super(ControlledErrorReportingArgumentParser, self) \
            .parse_known_args(args, namespace)
        try:
            an_argparse_namespace, extra_arguments = result
        except TypeError:
            an_argparse_namespace = argparse.Namespace()
            extra_arguments = result
        return (
            self._edit_config(an_argparse_namespace, object_hook),
            extra_arguments
        )

    #--------------------------------------------------------------------------
    def _edit_config(self, proposed_config, object_hook=None):
        if object_hook is None:
            object_hook = DotDict
        config = object_hook()
        for key, value in proposed_config.__dict__.iteritems():
            config[key] = value
        return config

# -----------------------------------------------------------------------------
def issubclass_with_no_type_error(potential_subclass, parent_class):
    try:
        return issubclass(potential_subclass, parent_class)
    except TypeError:
        return False


#==============================================================================
class ValueSource(object):
    """The ValueSource implementation for the argparse module.  This class will
    interpret an argv list of commandline arguments using argparse."""
    #--------------------------------------------------------------------------
    def __init__(self, source, conf_manager):
        self.source = source
        self.parent_parsers = []
        self.argparse_class = ControlledErrorReportingArgumentParser
        self.argv_source = tuple(conf_manager.argv_source)

    # frequently, command line data sources must be treated differently.  For
    # example, even when the overall option for configman is to allow
    # non-strict option matching, the command line should not arbitrarily
    # accept bad command line switches.  The existance of this key will make
    # sure that a bad command line switch will result in an error without
    # regard to the overall --admin.strict setting.
    command_line_value_source = True

    #--------------------------------------------------------------------------
    @staticmethod
    def _get_known_args(conf_manager):
        return set(
            x
            for x in conf_manager.option_definitions.keys_breadth_first()
        )

    #--------------------------------------------------------------------------
    def _option_to_command_line_str(an_option, key):
        if 'argparse' in an_option.foreign_data:
            return self._option_to_command_line_str_with_foreign_data(
                an_option,
                key
            )
        else:
            return self._option_to_command_line_str_standard(
                an_option,
                key
            )

    #--------------------------------------------------------------------------
    def _option_to_command_line_str(self, an_option, key):
        if an_option.is_argument:
            if an_option.foreign_data is not None:
                nargs = an_option.foreign_data.argparse.kwargs.get(
                    'nargs',
                    None
                )
            else:
                return to_str(an_option.value)
            if (
                nargs is not None
                and isinstance(an_option.value, collections.Sequence)
            ):
                return [to_str(x) for x in an_option.value]
            if an_option.value is None:
                return []
            return to_str(an_option.value)
        #if an_option.foreign_data.argparse.kwargs.nargs == 0:
            #return None
        if an_option.from_string_converter in (bool, boolean_converter):
            if an_option.value:
                return "--%s" % key
            return None
        if an_option.value is None:
            return None
        return '--%s="%s"' % (
            key,
            to_str(an_option)
        )

    #--------------------------------------------------------------------------
    def create_fake_args(self, config_manager):
        # all of this is to keep argparse from barfing if the minumum number
        # of required arguments is not in place at run time.  It may be that
        # some config file or environment will bring them in later.   argparse
        # needs to cope using this placebo argv
        args = [
            self._option_to_command_line_str(
                config_manager.option_definitions[key],
                key
            )
            for key in config_manager.option_definitions.keys_breadth_first()
            if (
                isinstance(
                    config_manager.option_definitions[key],
                    Option
                )
                and config_manager.option_definitions[key].is_argument
            )
        ]

        flattened_arg_list = []
        for x in args:
            if isinstance(x, list):
                flattened_arg_list.extend(x)
            else:
                flattened_arg_list.append(x)
        final_arg_list = [
            x.strip()
            for x in flattened_arg_list
            if x is not None and x.strip() != ''
        ]
        try:
            return final_arg_list + self.extra_args
        except (AttributeError, TypeError):
            return final_arg_list

    #--------------------------------------------------------------------------
    def get_values(self, config_manager, ignore_mismatches, object_hook=None):
        if ignore_mismatches:
            parser = self._create_new_argparse_instance(
                self.argparse_class,
                config_manager,
                False,  # create auto help
                self.parent_parsers,
            )
            namespace_and_extra_args = parser.parse_known_args(
                args=self.argv_source
            )

            try:
                argparse_namespace, self.extra_args = namespace_and_extra_args
            except TypeError:
                argparse_namespace = argparse.Namespace()
        else:
            fake_args = self.create_fake_args(config_manager)
            parser = self._create_new_argparse_instance(
                self.argparse_class,
                config_manager,
                True,
                self.parent_parsers,
            )
            argparse_namespace = parser.parse_args(
                args=fake_args,
            )
        return argparse_namespace

    #--------------------------------------------------------------------------
    def _create_new_argparse_instance(
        self,
        parser_class,
        config_manager,
        create_auto_help,
        parents,
    ):
        a_parser = parser_class(
            prog=config_manager.app_name,
            #version=config_manager.app_version,
            description=config_manager.app_description,
            add_help=create_auto_help,
            parents=parents,
        )
        self._setup_argparse(a_parser, config_manager)
        return a_parser

    #--------------------------------------------------------------------------
    def _setup_argparse(self, parser, config_manager):
        for opt_name in config_manager.option_definitions.keys_breadth_first():
            an_option = config_manager.option_definitions[opt_name]
            if isinstance(an_option, Option):
                parser.add_argument_from_option(opt_name, an_option)

    #--------------------------------------------------------------------------
    @staticmethod
    def _setup_auto_help(the_config_manager):
        pass  # there's nothing to do, argparse already has a help feature
