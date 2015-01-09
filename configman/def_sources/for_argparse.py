# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""this module introduces support for argparse as a data definition source
for configman.  Rather than write using configman's data definition language,
programs can instead use the familiar argparse method."""

import argparse
import inspect
from os import environ
from functools import partial
from collections import Sequence

from configman.namespace import Namespace
from configman.config_file_future_proxy import ConfigFileFutureProxy
from configman.dotdict import DotDict, iteritems_breadth_first
from configman.converters import (
    str_to_instance_of_type_converters,
    str_to_list,
    arbitrary_object_to_string,
    boolean_converter,
    to_str
)

#-----------------------------------------------------------------------------
# horrors
# argparse is not very friendly toward extension in this manner.  In order to
# fully exploit argparse, it is necessary to reach inside it to examine some
# of its internal structures that are not intended for external use.  These
# invasive methods are restricted to read-only.
#------------------------------------------------------------------------------
def find_action_name_by_value(registry, target_action_instance):
    """the association of a name of an action class with a human readable
    string is exposed externally only at the time of argument definitions.
    This routine, when given a reference to argparse's internal action
    registry and an action, will find that action and return the name under
    which it was registered.
    """
    target_type = type(target_action_instance)
    for key, value in registry['action'].iteritems():
        if value is target_type:
            if key is None:
                return 'store'
            return key
    return None


#------------------------------------------------------------------------------
def get_args_and_values(parser, an_action):
    """this rountine attempts to reconstruct the kwargs that were used in the
    creation of an action object"""
    args = inspect.getargspec(an_action.__class__.__init__).args
    kwargs = dict(
        (an_attr, getattr(an_action, an_attr))
        for an_attr in args
        if (
            an_attr not in ('self', 'required')
            and getattr(an_action, an_attr) is not None
        )
    )
    action_name = find_action_name_by_value(
        parser._optionals._registries,
        an_action
    )
    if 'required' in kwargs:
        del kwargs['required']
    kwargs['action'] = action_name
    if 'option_strings' in kwargs:
        args = tuple(kwargs['option_strings'])
        del kwargs['option_strings']
    else:
        args = ()
    return args, kwargs


#==============================================================================
class ArgumentParser(argparse.ArgumentParser):
    """this subclass of the standard argparse parser to be used as a drop in
    replacement for argparse.ArgumentParser.  It highjacks the standard
    parsing methods and hands off to configman.  Configman then calls back
    to the standard argparse base class to actually do the work, intercepting
    the final output do its overlay magic. The final result is not an
    argparse Namespace object, but a configman DotDict.  This means that it
    is functionlly equivalent to the argparse Namespace with the additional
    benefit of being compliant with the collections.Mapping abstract base
    class."""
    #--------------------------------------------------------------------------
    def __init__(self, *args, **kwargs):
        kwargs['add_help'] = False  # stop help, reintroduce it later
        super(ArgumentParser, self).__init__(*args, **kwargs)
        self.value_source_list = [environ, ConfigFileFutureProxy, argparse]
        self.required_config = Namespace()

    #--------------------------------------------------------------------------
    def add_argument(self, *args, **kwargs):
        """this method overrides the standard in order to create a parallel
        argument system in both the argparse and configman worlds.  Each call
        to this method returns a standard argparse Action object as well as
        add an equivalent Option object to this subclass' required_config
        attribute."""
        # pull out each of the argument definition components from the args
        # so that we can deal with them one at a time in a well labeled manner
        # In this section, variables beginning with the prefix "argparse" are
        # values that define Action object.  Variables that begin with
        # "configman" are the arguments to create configman Options.
        argparse_action_name = kwargs.get('action', None)
        argparse_dest = kwargs.get('dest', None)
        argparse_const = kwargs.get('const', None)
        argparse_default = kwargs.get('default', None)
        if argparse_default is argparse.SUPPRESS:
            # we'll be forcing all options to have the attribute of
            # argparse.SUPPRESS later.  It's our way of making sure that
            # argparse returns only values that the user explicitly added to
            # the command line.
            argparse_default = None
        argparse_nargs = kwargs.get('nargs', None)
        argparse_type = kwargs.get('type', None)
        argparse_help = kwargs.get('help', '')

        # we need to make sure that all arguments that the user has not
        # explicily set on the command line have this attribute.  This means
        # that when the argparse parser returns the command line values, it
        # will not return values that the user did not mention on the command
        # line.  The defaults that otherwise would have been returned will be
        # handled by configman.
        kwargs['default'] = argparse.SUPPRESS
        # forward all parameters to the underlying base class to create a
        # normal argparse action object.
        an_action = super(ArgumentParser, self).add_argument(
            *args,
            **kwargs
        )
        argparse_option_strings = an_action.option_strings
        configman_is_argument = not bool(argparse_option_strings)

        # get a human readable string that identifies the type of the argparse
        # action class that was created
        if argparse_action_name is None:
            argparse_action_name = find_action_name_by_value(
                    self._optionals._registries,
                    an_action
                )

        # each of argparse's Action types must be handled separately.
        #--------------------------------------------------------------------
        # STORE
        if argparse_action_name == 'store':
            if argparse_dest is None:
                configman_name = args[0]
            else:
                configman_name = argparse_dest
            configman_default = argparse_default
            configman_doc = argparse_help
            if argparse_nargs and argparse_type:
                configman_from_string = partial(
                    str_to_list,
                    item_converter=argparse_type,
                    item_separator=' ',
                )
            elif argparse_nargs and argparse_default:
                configman_from_string = partial(
                    str_to_list,
                    item_converter=str_to_instance_of_type_converters.get(
                        type(argparse_default),
                        str
                    ),
                    item_separator=' ',
                )
            elif argparse_nargs:
                configman_from_string = partial(
                    str_to_list,
                    item_converter=str,
                    item_separator=' ',
                )
            elif argparse_type:
                configman_from_string = argparse_type
            elif argparse_default:
                configman_from_string = str_to_instance_of_type_converters.get(
                    type(argparse_default),
                    str
                )
            else:
                configman_from_string = str
            configman_to_string = to_str

        #--------------------------------------------------------------------
        # STORE_CONST
        elif argparse_action_name == 'store_const':
            configman_name = argparse_dest
            configman_default = argparse_default
            configman_doc = argparse_help
            if argparse_type:
                configman_from_string = argparse_type
            else:
                configman_from_string = str_to_instance_of_type_converters.get(
                    type(argparse_const),
                    str
                )
            configman_to_string = to_str

        #--------------------------------------------------------------------
        # STORE_TRUE /  STORE_FALSE
        elif (
            argparse_action_name == 'store_true'
            or argparse_action_name == 'store_false'
        ):
            configman_name = argparse_dest
            configman_default = argparse_default
            configman_doc = argparse_help
            configman_from_string = boolean_converter
            configman_to_string = to_str

        #--------------------------------------------------------------------
        # APPEND
        elif argparse_action_name == 'append':
            configman_name = argparse_dest
            configman_default = argparse_default
            configman_doc = argparse_help
            if argparse_type:
                configman_from_string = argparse_type
            else:
                configman_from_string = str
            configman_to_string = to_str

        #--------------------------------------------------------------------
        # APPEND_CONST
        elif argparse_action_name == 'append_const':
            configman_name = argparse_dest
            configman_default = argparse_default
            configman_doc = argparse_help
            if argparse_type:
                configman_from_string = argparse_type
            else:
                configman_from_string = str_to_instance_of_type_converters.get(
                    type(argparse_const),
                    str
                )
            configman_to_string = to_str

        #--------------------------------------------------------------------
        # VERSION
        elif argparse_action_name == 'version':
            return an_action

        #--------------------------------------------------------------------
        # OTHER
        else:
            configman_name = argparse_dest
            print "ERROR", argparse_action_name

        # configman uses the switch name as the name of the key inwhich to
        # store values.  argparse is able to use different names for each.
        # this means that configman may encounter repeated targets.  Rather
        # than overwriting Options with new ones with the same name, configman
        # renames them by appending the '$' character.
        while configman_name in self.required_config:
            configman_name = "%s$" % configman_name
        configman_not_for_definition = configman_name.endswith('$')

        # it's finally time to create the configman Option object and add it
        # to the required_config.
        self.required_config.add_option(
            name=configman_name,
            default=configman_default,
            doc=configman_doc,
            from_string_converter=configman_from_string,
            to_string_converter=configman_to_string,
            #short_form=configman_short_form,
            is_argument=configman_is_argument,
            not_for_definition=configman_not_for_definition,
            # we're going to save the input parameters that created the
            # argparse Action.  This enables us to perfectly reproduce the
            # the original Action object later during the configman overlay
            # process.
            foreign_data=DotDict({
                'argparse.args': args,
                'argparse.kwargs': kwargs,
            })
        )
        return an_action

    #--------------------------------------------------------------------------
    def parse_args(self, args=None, namespace=None):
        """this method hijacks the normal argparse Namespace generation,
        shimming configman into the process. The return value will be a
        configman DotDict rather than an argparse Namespace."""
        # load the config_manager within the scope of the method that uses it
        # so that we avoid circular references in the outer scope
        from configman.config_manager import ConfigurationManager
        configuration_manager = ConfigurationManager(
            definition_source=[self.required_config],
            values_source_list=self.value_source_list,
            argv_source=args,
            app_name=self.prog,
            app_version=self.version,
            app_description=self.description,
            use_auto_help=False,
        )
        conf =  configuration_manager.get_config()
        return conf

    #--------------------------------------------------------------------------
    def parse_known_args(self, args=None, namespace=None):
        """this method hijacks the normal argparse Namespace generation,
        shimming configman into the process. The return value will be a
        configman DotDict rather than an argparse Namespace."""
        # load the config_manager within the scope of the method that uses it
        # so that we avoid circular references in the outer scope
        from configman.config_manager import ConfigurationManager
        configuration_manager = ConfigurationManager(
            definition_source=[self],
            values_source_list=self.value_source_list,
            argv_source=args,
            app_name=self.prog,
            app_version=self.version,
            app_description=self.description,
            use_auto_help=False,
        )
        conf =  configuration_manager.get_config()
        return conf

    #--------------------------------------------------------------------------
    def get_required_config(self):
        """this is a standard configman method that returns a hierarchy of
        configman Namespace objects populated with Options."""
        return self.required_config


#------------------------------------------------------------------------------
def setup_definitions(source, destination):
    # assume that source is of type argparse
    try:
        destination.update(source.get_required_config())
    except AttributeError:
        # looks like the user passed in a real arpgapse parser rather than our
        # bastardized version of one.  No problem, we can work with it,
        # though the translation won't be as perfect.
        our_parser = ArgumentParser()
        for i, an_action in enumerate(source._actions):
            args, kwargs = get_args_and_values(source, an_action)
            dest = kwargs.get('dest', '')
            if dest in ('help', 'version'):
                continue
            our_parser.add_argument(*args, **kwargs)
        destination.update(our_parser.get_required_config())
