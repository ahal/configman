# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# this is a stub for future implementation

try:
    import argparse
    import inspect
    from functools import partial
    from collections import Sequence

    from .. import namespace
    from .. import converters

    #from configman.converters import dont_care

    # horrors
    def find_action_name_by_value(registry, target):
        target_type = type(target)
        for key, value in registry['action'].iteritems():
            if value is target_type:
                if key is None:
                    return 'store'
                return key
        return None

    def get_args_and_values(an_action):
        args = inspect.getargspec(an_action.__class__.__init__).args
        kwargs = dict(
            (an_attr, getattr(an_action, an_attr))
            for an_attr in args if an_attr not in ('self', 'required')
        )
        return kwargs

    def create_custom_from_string_converter(const, default):
        def from_string_converter(value):
            if value == const:
                return const
            return default
        return from_string_converter

    def setup_definitions(source, destination):
        # assume that source is of type argparse
        for i, an_action in enumerate(source._actions):
            not_for_definition = an_action.default != argparse.SUPPRESS
            kwargs = get_args_and_values(an_action)

            if an_action.dest in destination:
                continue

            # figure out what would be an appropriate from_string_converter
            kwargs['action'] = find_action_name_by_value(
                source._optionals._registries,
                an_action
            )
            target_value_type = an_action.type
            if target_value_type is None:
                if kwargs['action'] == 'store_const':
                    target_value_type = converters.get_from_string_converter(
                        an_action.const
                    )
                else:
                    target_value_type = \
                        converters.get_from_string_converter(
                            type(an_action.default)
                        )
            if target_value_type is type(None) or target_value_type is None:
                target_value_type = str

            try:
                if kwargs['nargs']:
                    from_string_type_converter = partial(
                        converters.list_converter,
                        item_converter=converters.get_from_string_converter(
                            target_value_type
                        ),
                        item_separator=' ',
                    )
                elif (kwargs['action'] == 'append'
                      or kwargs['action'] == 'append_const'
                ):
                    if isinstance(type(an_action.default), Sequence):
                        from_string_type_converter = partial(
                            converters.list_converter,
                            item_converter=
                                converters.get_from_string_converter(str),
                            item_separator=',',
                        )
                        if an_action.default is not None:
                            default = an_action.default
                    else:
                        from_string_type_converter = partial(
                            converters.list_converter,
                            item_converter=
                                converters.get_from_string_converter(str),
                            item_separator=',',
                            list_to_collection_converter=type(
                                an_action.default
                            )
                        )
                else:
                    from_string_type_converter = target_value_type
            except KeyError:
                from_string_type_converter = target_value_type

            # find short form
            short_form = None
            for an_option_string in kwargs['option_strings']:
                try:
                    if (
                        an_option_string[0] == an_option_string[1]
                        and an_option_string[0] in source.prefix_chars
                        and an_option_string[1] in source.prefix_chars
                    ):
                        continue  # clearly a double prefix switch
                    if (
                        an_option_string[0] in source.prefix_chars
                        and len(an_option_string) == 2
                    ):
                        short_form = an_option_string[1]
                except IndexError:
                    pass
                    # skip this one, it has to be a single letter argument,
                    # not a switch

            default = an_action.default

            destination.add_option(
                name=an_action.dest,
                default=default,
                short_form=short_form,
                from_string_converter=from_string_type_converter,
                to_string_converter=converters.to_str,
                doc=an_action.help,
                number_of_values=an_action.nargs,
                is_argument=not kwargs['option_strings'],
            )

    type_to_setup_association = {argparse.ArgumentParser: setup_definitions}

except ImportError, x:

    type_to_setup_association = {}
