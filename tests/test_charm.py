# Copyright 2020 Ubuntu
# See LICENSE file for licensing details.

import unittest
from unittest.mock import (
    call,
    Mock,
    patch,
    mock_open
)
from ops.testing import Harness
from charm import SimpleStreamsCharm


class TestCharm(unittest.TestCase):

    def test_config_changed(self):
        harness = Harness(SimpleStreamsCharm)
        # from 0.8 you should also do:
        self.addCleanup(harness.cleanup)
        harness.begin()

        default_config = {
            'image-selectors': 'selctor',
            'verbose': False,
            'image-max': 1,
            'image-source': 'source',
            'image-dir': 'dir',
        }

        self.assertEqual(harness.charm._stored.config, {})
        harness.update_config(default_config)
        self.assertEqual(harness.charm._stored.config, default_config)

    @patch('builtins.open', new_callable=mock_open)
    def test_cron_schedule_set(self, mock_open_call):
        harness = Harness(SimpleStreamsCharm)
        self.addCleanup(harness.cleanup)
        harness.begin()
        default_config = {
            'image-selectors': 'selctor',
            'verbose': False,
            'image-max': 1,
            'image-source': 'source',
            'image-dir': 'dir',
            'image-dir': 'dir',
            'cron-schedule': 'cron-schedule',
        }
        self.assertEqual(harness.charm._stored.config, {})
        harness.update_config(default_config)
        self.assertEqual(harness.charm._stored.config, default_config)
        mock_open_call.assert_called_with('/etc/cron.d/{}'.format(harness.charm.model.app.name),
                                          "w")
        mock_open_call.return_value.write.assert_called_once_with(
            "cron-schedule root sstream-mirror --no-verify --max=1 source dir 'selctor'\n"
        )

    @patch('subprocess.check_output')
    def test_synchronize_action_defaults(self, mock_subproc):
        process_mock = Mock()
        mock_subproc.return_value = process_mock
        harness = Harness(SimpleStreamsCharm)
        harness.begin()
        harness.charm._stored.config = {
            'image-selectors': 'selctor',
            'verbose': False,
            'image-max': 1,
            'image-source': 'source',
            'image-dir': 'dir',
        }
        action_event = Mock()
        harness.charm._on_synchronize_action(action_event)
        self.assertTrue(mock_subproc.called)
        assert mock_subproc.call_args == call(['sstream-mirror', '--no-verify', '--max=1',
                                               'source', 'dir', 'selctor'], stderr=-2)

    @patch('subprocess.check_output')
    def test_synchronize_action_all_params(self, mock_subproc):
        process_mock = Mock()
        mock_subproc.return_value = process_mock
        harness = Harness(SimpleStreamsCharm)
        harness.begin()
        harness.charm._stored.config = {
            'image-selectors': 'selctor',
            'verbose': True,
            'image-max': 1,
            'image-source': 'source',
            'image-dir': 'dir',
            'keyring-file': 'keyring-file',
            'path': 'path',
            'log-file': 'log-file'
        }
        action_event = Mock()
        harness.charm._on_synchronize_action(action_event)
        self.assertTrue(mock_subproc.called)
        assert mock_subproc.call_args == call(['sstream-mirror', '--keyring=keyring-file',
                                               '--verbose', '--path=path', '--log-file=log-file',
                                               '--max=1', 'source', 'dir', 'selctor'], stderr=-2)

    # def test_action_fail(self):
    #     harness = Harness(SimpleStreamsCharm)
    #     harness.begin()
    #     action_event = Mock(params={"fail": "fail this"})
    #     harness.charm._on_fortune_action(action_event)

    #     self.assertEqual(action_event.fail.call_args, [("fail this",)])
