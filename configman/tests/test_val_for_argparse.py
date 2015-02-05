# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from unittest import SkipTest, TestCase

try:
    import argparse
except ImportError:
    raise SkipTest

from configman.command_line import (
    ArgumentParser,
    ControlledErrorReportingArgumentParser,
)

from mock import Mock
from os import environ

from functools import partial

from configman import Namespace
from configman.converters import (
    list_converter,
    list_to_str,
    to_str,
    dont_care
)

from configman.config_file_future_proxy import ConfigFileFutureProxy
from configman.dotdict import DotDict
from configman.value_sources.source_exceptions import CantHandleTypeException

from configman.value_sources.for_argparse import (
    issubclass_with_no_type_error,
    ValueSource,
    argparse,
    ControlledErrorReportingArgumentParser,
)

#==============================================================================
class TestCaseForValSourceArgparse(TestCase):

    def setup_value_source(self, type_of_value_source=ValueSource):
        conf_manager = Mock()
        conf_manager.argv_source = []

        arg = ArgumentParser()
        arg.add_argument(
            '--wilma',
            dest='wilma',
        )
        vs = type_of_value_source(arg, conf_manager)
        return vs

    def setup_configman_namespace(self):
        n = Namespace()
        n.add_option(
            'alpha',
            default=3,
            doc='the first parameter',
            is_argument=True
        )
        n.add_option(
            'beta',
            default='the second',
            doc='the first parameter',
            short_form = 'b',
        )
        n.add_option(
            'gamma',
            default=[1, 2, 3],
            number_of_values="*",
            from_string_converter=partial(
                list_converter,
                item_separator=' ',
                item_converter=int
            ),
            to_string_converter=partial(
                list_to_str,
                delimiter=' '
            ),
        )
        n.add_option(
            'delta',
            default=False,
        )
        n.add_option(
            'kappa',
            default=[7, 8],
            from_string_converter=partial(
                list_converter,
                item_separator=' ',
                item_converter=int
            ),
            to_string_converter=partial(
                sequence_to_string,
                delimiter=' '
            ),
            is_argument=True
        )
        for k, o in n.iteritems():
            o.set_value()
        return n


    def test_issubclass_with_no_type_error(self):

        class A(object):
            pass

        class B(object):
            pass

        class C(A):
            pass

        self.assertTrue(issubclass_with_no_type_error(C, A))
        self.assertFalse(issubclass_with_no_type_error(B, A))
        self.assertFalse(issubclass_with_no_type_error(None, A))

    def test_value_source_init_with_module(self):
        conf_manager = Mock()
        conf_manager.argv_source = []

        vs = ValueSource(argparse, conf_manager)
        self.assertTrue(vs.parser is None)
        self.assertTrue(
            vs.parser_class is ControlledErrorReportingArgumentParser
        )
        self.assertFalse(vs.known_args)
        self.assertFalse(vs.parent_parsers)

    def test_value_source_init_with_a_parser_1(self):
        conf_manager = Mock()
        conf_manager.argv_source = []

        arg = argparse.ArgumentParser()

        self.assertRaises(
            CantHandleTypeException,
            ValueSource,
            arg,
            conf_manager
        )

    def test_value_source_init_with_a_parser_2(self):
        vs = self.setup_value_source()

        self.assertTrue(vs.parser is None)
        self.assertTrue(
            vs.parser_class is ControlledErrorReportingArgumentParser
        )
        self.assertEqual(vs.known_args, set(['wilma']))
        self.assertEqual(vs.parent_parsers, [vs.parent_parsers[0]])
        self.assertFalse(vs.parent_parsers[0].parse_through_configman)
        self.assertEqual(vs.parent_parsers[0]._brand, 0)

    def test_get_known_args(self):
        config_manager = Mock()
        config_manager.option_definitions = self.setup_configman_namespace()
        vs = self.setup_value_source()
        self.assertEqual(
            vs._get_known_args(config_manager),
            set(['alpha', 'beta', 'gamma', 'delta', 'kappa'])
        )

    def test_option_to_command_line_str_1(self):
        n = self.setup_configman_namespace()
        vs = self.setup_value_source()
        expected = {
            'alpha': '3',
            'beta': '--beta="the second"',
            'gamma': '--gamma="1 2 3"',
            #'delta': '--delta="False"',  # not returned as it is the default
            'kappa': ['7', '8']
        }
        for k in n.keys_breadth_first():
            op = vs._option_to_command_line_str(n[k], k)
            try:
                self.assertEqual(op, expected[k])
            except KeyError, key:
                self.assertTrue('delta' in str(key))

    def test_option_to_command_line_str_2(self):
        n = self.setup_configman_namespace()
        n.gamma.default = None
        n.gamma.value = None
        vs = self.setup_value_source()
        expected = {
            'alpha': '3',
            'beta': '--beta="the second"',
            'gamma': None,
            #'delta': '--delta="False"',  # not returned as it is the default
            'kappa': ['7', '8']
        }
        for k in n.keys_breadth_first():
            op = vs._option_to_command_line_str(n[k], k)
            try:
                self.assertEqual(op, expected[k])
            except KeyError, key:
                self.assertTrue('delta' in str(key))

    def test_create_fake_args(self):
        vs = self.setup_value_source()
        n = self.setup_configman_namespace()
        conf_manager = Mock()
        conf_manager.option_definitions = n
        final = vs.create_fake_args(conf_manager)
        self.assertEqual(final, ['3', '7', '8'])

    def test_val_as_str(self):
        vs = self.setup_value_source()
        self.assertEqual(vs._val_as_str(1), '1')
        self.assertEqual(vs._val_as_str(dont_care(1)), '1')
        self.assertEqual(vs._val_as_str(dont_care(None)), '')

    def test_we_care_about_this_value(self):
        vs = self.setup_value_source()
        dci = dont_care(1)
        self.assertFalse(vs._we_care_about_this_value(dci))
        dci = dont_care([])
        self.assertFalse(vs._we_care_about_this_value(dci))
        dci.append('89')
        self.assertTrue(vs._we_care_about_this_value(dci))

    def test_get_values_1(self):
        class MyArgumentValueSource(ValueSource):
            def _create_new_argparse_instance(
                self,
                parser_class,
                config_manager,
                auto_help,
                parents
            ):
                mocked_parser = Mock()
                mocked_namespace = argparse.Namespace()
                mocked_namespace.a = 1
                mocked_namespace.b = 2
                mocked_parser.parse_known_args.return_value = (
                    mocked_namespace,
                    ['--extra', '--extra']
                )
                return mocked_parser

        vs = self.setup_value_source(
            type_of_value_source=MyArgumentValueSource
        )
        config_manager = Mock()
        config_manager.option_definitions = self.setup_configman_namespace()
        result = vs.get_values(config_manager, True)

        parser = vs.parent_parsers[0]
        self.assertEqual(vs.extra_args, ['--extra', '--extra'])
        self.assertTrue(parser.parse_known_args.called_once_with(
            vs.argv_source
        ))
        self.assertTrue(vs.parser is None)
        self.assertTrue(isinstance(result, DotDict))
        self.assertEqual(dict(result), {'a': 1, 'b': 2})
        #self.assertEqual(dict(result), {'a': '1', 'b': '2'})

    def test_get_values_2(self):
        class MyArgumentValueSource(ValueSource):
            def _create_new_argparse_instance(
                self,
                parser_class,
                config_manager,
                auto_help,
                parents
            ):
                mocked_parser = Mock()
                mocked_namespace = argparse.Namespace()
                mocked_namespace.a = 1
                mocked_namespace.b = 2
                mocked_parser.parse_args.return_value = mocked_namespace
                return mocked_parser

        vs = self.setup_value_source(
            type_of_value_source=MyArgumentValueSource
        )
        config_manager = Mock()
        config_manager.option_definitions = self.setup_configman_namespace()
        result = vs.get_values(config_manager, False)

        parser = vs.parser
        self.assertFalse(hasattr(vs, 'extra_args'))
        self.assertTrue(parser.parse_args.called_once_with(
            vs.argv_source
        ))
        self.assertTrue(isinstance(result, DotDict))
        self.assertEqual(dict(result), {'a': 1, 'b': 2})  # for when this is
                                                           # switched to real
                                                           # return values
        #self.assertEqual(dict(result), {'a': '1', 'b': '2'})

    def test_create_new_argparse_instance(self):
        class MyArgumentValueSource(ValueSource):
            def __init__(self, *args, **kwargs):
                super(MyArgumentValueSource, self).__init__(*args, **kwargs)
                self.call_counter_proxy = Mock()
            def _setup_argparse(self, parser, config_manager):
                self.call_counter_proxy(parser, config_manager)
                return
        vs = self.setup_value_source(MyArgumentValueSource)
        self.assertTrue(isinstance(vs.parent_parsers[0], argparse.ArgumentParser))
        self.assertTrue('wilma' in (x.dest for x in vs.parent_parsers[0]._actions))
        n = self.setup_configman_namespace()
        config_manager = Mock()
        config_manager.app_name = 'MyApp'
        config_manager.app_version = '1.2'
        config_manager.app_description = "it's the app"
        parent = Mock()
        parser = vs._create_new_argparse_instance(
            ControlledErrorReportingArgumentParser,
            config_manager,
            False,
            vs.parent_parsers
        )
        parser.add_argument('--bogus', dest='bogus', action='store', default=2)
        self.assertTrue(
            isinstance(parser, ControlledErrorReportingArgumentParser)
        )
        self.assertEqual(parser._brand, 1)
        vs.call_counter_proxy.assert_called_once_with(parser, config_manager)
        self.assertEqual(parser.prog, 'MyApp')
        #self.assertEqual(parser.version, '1.2')  #TODO: fix versions
        self.assertEqual(parser.description, "it's the app")
        self.assertTrue('help' not in (x.dest for x in parser._actions))
        self.assertTrue('bogus' in (x.dest for x in parser._actions))
        self.assertTrue('wilma' in (x.dest for x in parser._actions))

        second_parser = vs._create_new_argparse_instance(
            ControlledErrorReportingArgumentParser,
            config_manager,
            True,
            [parser]
        )
        self.assertEqual(second_parser._brand, 2)
        self.assertTrue('help' in (x.dest for x in second_parser._actions))
        self.assertTrue('bogus' in (x.dest for x in second_parser._actions))
        self.assertTrue('wilma' in (x.dest for x in second_parser._actions))

    def test_setup_argparse(self):
        vs = self.setup_value_source()
        n = self.setup_configman_namespace()
        config_manager = Mock()
        config_manager.option_definitions = n
        parser = vs.parent_parsers[0]
        self.assertTrue('wilma' in (x.dest for x in parser._actions))

        vs._setup_argparse(parser, config_manager)

        actions = dict((x.dest, x) for x in parser._actions)
        self.assertTrue('alpha' in actions)
        self.assertTrue('beta' in actions)
        self.assertTrue('gamma' in actions)
        self.assertTrue('kappa' in actions)

        self.assertTrue('--alpha' not in actions['alpha'].option_strings)
        self.assertEqual(actions['alpha'].default, 3)
        self.assertTrue(actions['alpha'].default.dont_care())

        self.assertTrue('--beta' in actions['beta'].option_strings)
        self.assertTrue('-b' in actions['beta'].option_strings)
        self.assertTrue(actions['beta'].default.dont_care())

        self.assertTrue('--gamma' in actions['gamma'].option_strings)
        self.assertTrue(actions['gamma'].default.dont_care())

        self.assertTrue('--delta' in actions['delta'].option_strings)
        self.assertTrue(actions['delta'].default.dont_care())

        self.assertTrue('--kappa' not in actions['kappa'].option_strings)
        self.assertTrue(actions['kappa'].default.dont_care())












