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

from uuid import uuid4
import random


class TestCharm(unittest.TestCase):

    def default_config(self):
        return {
            'image-selectors': str(uuid4()),
            'keyring-file': str(uuid4()),
            'path': str(uuid4()),
            'log-file': str(uuid4()),
            'verbose': False,
            'image-max': random.randint(10, 20),
            'image-source': str(uuid4()),
            'image-dir': str(uuid4()),
            'cron-schedule': 'None',
        }

    @patch('subprocess.check_output')
    def test_install(self, mock_subproc):
        process_mock = Mock()
        mock_subproc.return_value = process_mock
        harness = Harness(SimpleStreamsCharm)
        harness.begin()
        action_event = Mock()
        harness.charm._on_install(action_event)
        self.assertTrue(mock_subproc.called)
        assert mock_subproc.call_args == call(["apt", "install", "-y", "simplestreams"])

    def test_config_changed(self):
        harness = Harness(SimpleStreamsCharm)
        self.addCleanup(harness.cleanup)
        harness.begin()
        default_config = self.default_config()
        self.assertEqual(harness.charm._stored.config, {})
        harness.update_config(default_config)
        assert harness.charm._stored.config == default_config

    @patch('builtins.open', new_callable=mock_open)
    def test_cron_schedule_set(self, mock_open_call):
        harness = Harness(SimpleStreamsCharm)
        self.addCleanup(harness.cleanup)
        harness.begin()
        default_config = self.default_config()
        default_config['cron-schedule'] = str(uuid4())
        self.assertEqual(harness.charm._stored.config, {})
        harness.update_config(default_config)
        self.assertEqual(harness.charm._stored.config, default_config)
        mock_open_call.assert_called_with('/etc/cron.d/{}'.format(harness.charm.model.app.name),
                                          "w")
        mock_open_call.return_value.write.assert_called_once_with(
            "{} root sstream-mirror"
            " --keyring={} --path={} --log-file={} --max={} {} {} \'{}\'\n"
            .format(
                default_config['cron-schedule'],
                default_config['keyring-file'],
                default_config['path'],
                default_config['log-file'],
                default_config['image-max'],
                default_config['image-source'],
                default_config['image-dir'],
                default_config['image-selectors'],
            )
        )

    @patch('subprocess.check_output')
    def test_synchronize_action_defaults(self, mock_subproc):
        process_mock = Mock()
        mock_subproc.return_value = process_mock
        harness = Harness(SimpleStreamsCharm)
        harness.begin()
        minimal_config = {
            'image-selectors': str(uuid4()),
            'verbose': False,
            'image-max': random.randint(10, 20),
            'image-source': str(uuid4()),
            'image-dir': str(uuid4()),
            'cron-schedule': 'None',
        }
        harness.charm._stored.config = minimal_config
        action_event = Mock()
        harness.charm._on_synchronize_action(action_event)
        self.assertTrue(mock_subproc.called)
        assert mock_subproc.call_args == call(['sstream-mirror', '--no-verify', '--max={}'
                                               .format(minimal_config['image-max']),
                                               minimal_config['image-source'],
                                               minimal_config['image-dir'],
                                               minimal_config['image-selectors']],
                                              stderr=-2)

    @patch('subprocess.check_output')
    def test_synchronize_action_all_params(self, mock_subproc):
        process_mock = Mock()
        mock_subproc.return_value = process_mock
        harness = Harness(SimpleStreamsCharm)
        harness.begin()
        default_config = self.default_config()
        default_config['verbose'] = True
        harness.charm._stored.config = default_config
        action_event = Mock()
        harness.charm._on_synchronize_action(action_event)
        self.assertTrue(mock_subproc.called)
        assert mock_subproc.call_args == call(['sstream-mirror',
                                               '--keyring={}'
                                               .format(default_config['keyring-file']),
                                               '--verbose',
                                               '--path={}'.format(default_config['path']),
                                               '--log-file={}'.format(default_config['log-file']),
                                               '--max={}'.format(default_config['image-max']),
                                               default_config['image-source'],
                                               default_config['image-dir'],
                                               default_config['image-selectors']],
                                              stderr=-2)
