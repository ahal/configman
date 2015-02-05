# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from unittest import SkipTest, TestCase

try:
    import argparse
except ImportError:
    raise SkipTest

from configman import ConfigurationManager
from configman.command_line import ArgumentParser
from configman.converters import to_str


#==============================================================================
class TestCaseForDefSourceArgparse(TestCase):

    def setup_argparse(self):
        parser = ArgumentParser(prog='hell')
        parser.add_argument(
            '-s',
            action='store',
            dest='simple_value',
            help='Store a simple value'
        )
        parser.add_argument(
            '-c',
            action='store_const',
            dest='constant_value',
            const='value-to-store',
            help='Store a constant value'
        )
        parser.add_argument(
            '-t',
            action='store_true',
            default=False,
            dest='boolean_switch',
            help='Set a switch to true'
        )
        parser.add_argument(
            '-f',
            action='store_false',
            default=False,
            dest='boolean_switch',
            help='Set a switch to false'
        )
        parser.add_argument(
            '-a',
            action='append',
            dest='collection',
            default=[],
            help='Add repeated values to a list',
        )
        parser.add_argument(
            '-A',
            action='append_const',
            dest='const_collection',
            const='value-1-to-append',
            default=[],
            help='Add different values to list'
        )
        parser.add_argument(
            '-B',
            action='append_const',
            dest='const_collection',
            const='value-2-to-append',
            help='Add different values to list'
        )
        parser.add_argument(
            '--version',
            action='version',
            version='%(prog)s 1.0'
        )
        return parser

    def test_parser_setup(self):
        parser = self.setup_argparse()
        actions = {}
        for x in parser._actions:
            if x.dest not in actions:
                actions[x.dest] = x
        cm = ConfigurationManager(
            definition_source=[parser],
            values_source_list=[],
        )
        options = cm.option_definitions
        for key, an_action in actions.iteritems():
            self.assertTrue(key in options)

        self.assertTrue(options.simple_value.default is None)
        self.assertEqual(options.simple_value.short_form, 's')
        self.assertTrue(
            options.simple_value.from_string_converter is str
        )
        self.assertTrue(
            options.simple_value.to_string_converter is to_str
        )
        self.assertEqual(
            options.simple_value.doc,
            actions['simple_value'].help
        )
        self.assertEqual(
            options.simple_value.number_of_values,
            actions['simple_value'].nargs
        )

        self.assertEqual(
            options.constant_value.default,
            actions['constant_value'].default.as_bare_value()
        )
        self.assertEqual(options.constant_value.short_form, 'c')
        #self.assertTrue(  # can't test - custom fn created
            #options['constant_value'].from_string_converter is some-method
        #)
        self.assertTrue(
            options.constant_value.to_string_converter is to_str
        )
        self.assertEqual(
            options.constant_value.doc,
            actions['constant_value'].help
        )
        self.assertEqual(
            options.constant_value.number_of_values,
            actions['constant_value'].nargs
        )

        #self.assertEqual(
            #options.boolean_switch.default.as_bare_value(),
            #actions['boolean_switch'].const
        #)
        #self.assertEqual(options.boolean_switch.short_form, 't')
        #self.assertTrue(  # can't verify correct corverter - custom fn created
            #options['boolean_switch'].from_string_converter is str
        #)
        self.assertTrue(
            options.boolean_switch.to_string_converter is to_str
        )
        self.assertEqual(
            options.boolean_switch.doc,
            actions['boolean_switch'].help
        )
        self.assertEqual(
            options.boolean_switch.number_of_values,
            actions['boolean_switch'].nargs
        )

        self.assertEqual(
            options.collection.default,
            actions['collection'].default.as_bare_value()
        )
        self.assertEqual(options.collection.short_form, 'a')
        #self.assertTrue(  # can't verify correct corverter - custom fn created
            #options['collection'].from_string_converter is some-method
        #)
        self.assertTrue(
            options.collection.to_string_converter is to_str
        )
        self.assertEqual(
            options.collection.doc,
            actions['collection'].help
        )
        self.assertTrue(
            options.collection.number_of_values is not None
        )

        self.assertEqual(
            options.const_collection.default,
            actions['const_collection'].default.as_bare_value()
        )
        self.assertEqual(options.const_collection.short_form, 'A')
        #self.assertTrue(  # can't verify correct corverter - custom fn created
            #options['const_collection'].from_string_converter is some-method
        #)
        self.assertTrue(
            options.const_collection.to_string_converter is to_str
        )
        self.assertEqual(
            options.const_collection.doc,
            actions['const_collection'].help
        )
        self.assertTrue(
            options.const_collection.number_of_values is not None
        )






