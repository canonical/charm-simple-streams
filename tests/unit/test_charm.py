# Copyright 2020 Ubuntu
# See LICENSE file for licensing details.

import os
import random
import unittest
from unittest.mock import Mock, call, mock_open, patch
from uuid import uuid4

from ops.testing import Harness

from charm import SimpleStreamsCharm, _get_env


@patch.dict(
    os.environ,
    {
        "JUJU_CHARM_HTTP_PROXY": "http_proxy",
        "JUJU_CHARM_HTTPS_PROXY": "https_proxy",
        "JUJU_CHARM_NO_PROXY": "no_proxy",
        "TEST": "test",
    },
    clear=True,
)
def test_get_env():
    env = _get_env()
    assert env.get("JUJU_CHARM_HTTP_PROXY") == "http_proxy"
    assert env.get("JUJU_CHARM_HTTPS_PROXY") == "https_proxy"
    assert env.get("JUJU_CHARM_NO_PROXY") == "no_proxy"
    assert env.get("TEST") == "test"


class TestCharm(unittest.TestCase):
    def default_config(self):
        return {
            "image-selectors": str(uuid4()),
            "keyring-file": str(uuid4()),
            "path": str(uuid4()),
            "log-file": str(uuid4()),
            "verbose": False,
            "image-max": random.randint(10, 20),
            "image-source": str(uuid4()),
            "image-dir": str(uuid4()),
            "cron-schedule": "None",
            "copy-on-snapshot": False,
            "keep": True,
        }

    @patch("subprocess.check_output")
    def test_install(self, mock_subproc):
        process_mock = Mock()
        mock_subproc.return_value = process_mock
        harness = Harness(SimpleStreamsCharm)
        harness.begin()
        action_event = Mock()
        harness.charm._on_install(action_event)
        self.assertTrue(mock_subproc.called)
        assert mock_subproc.call_args == call(["apt", "install", "-y", "simplestreams"])

    @patch("os.symlink")
    @patch("os.makedirs")
    @patch("os.path.isdir")
    def test_config_changed(self, os_path_isdir, os_makedirs, os_symlink):
        harness = Harness(SimpleStreamsCharm)
        self.addCleanup(harness.cleanup)
        os_path_isdir.return_value = False
        harness.begin()
        default_config = self.default_config()
        self.assertEqual(harness.charm._stored.config, {})
        harness.update_config(default_config)
        self.assertTrue(os_path_isdir.called)
        self.assertTrue(os_makedirs.called)
        self.assertTrue(os_symlink.called)
        assert harness.charm._stored.config == default_config

    @patch("os.symlink")
    @patch("os.makedirs")
    @patch("os.path.isdir")
    @patch("builtins.open", new_callable=mock_open)
    def test_cron_schedule_set(self, mock_open_call, os_path_isdir, os_makedirs, os_symlink):
        harness = Harness(SimpleStreamsCharm)
        self.addCleanup(harness.cleanup)
        harness.begin()
        default_config = self.default_config()
        default_config["cron-schedule"] = str(uuid4())
        self.assertEqual(harness.charm._stored.config, {})
        harness.update_config(default_config)
        self.assertEqual(harness.charm._stored.config, default_config)
        mock_open_call.assert_called_with(
            "/etc/cron.d/{}".format(harness.charm.model.app.name), "w"
        )
        mock_open_call.return_value.write.assert_called_once_with(
            "{} root sstream-mirror --keep"
            " --keyring={} --path={} --log-file={} --max={} {} {} '{}'\n".format(
                default_config["cron-schedule"],
                default_config["keyring-file"],
                default_config["path"],
                default_config["log-file"],
                default_config["image-max"],
                default_config["image-source"],
                "{}/latest".format(default_config["image-dir"]),
                default_config["image-selectors"],
            )
        )
        self.assertTrue(os_path_isdir.called)
        self.assertFalse(os_makedirs.called)
        self.assertFalse(os_symlink.called)

    @patch.dict(os.environ, {"foo": "bar"}, clear=True)
    @patch("subprocess.check_output")
    def test_synchronize_action_defaults(self, mock_subproc):
        process_mock = Mock()
        mock_subproc.return_value = process_mock
        harness = Harness(SimpleStreamsCharm)
        harness.begin()
        minimal_config = {
            "image-selectors": str(uuid4()),
            "verbose": False,
            "image-max": random.randint(10, 20),
            "image-source": str(uuid4()),
            "image-dir": str(uuid4()),
            "cron-schedule": "None",
            "copy-on-snapshot": False,
        }
        harness.charm._stored.config = minimal_config
        action_event = Mock()
        harness.charm._on_synchronize_action(action_event)
        self.assertTrue(mock_subproc.called)
        assert mock_subproc.call_args == call(
            [
                "sstream-mirror",
                "--keep",
                "--no-verify",
                "--max={}".format(minimal_config["image-max"]),
                minimal_config["image-source"],
                "{}/latest".format(minimal_config["image-dir"]),
                minimal_config["image-selectors"],
            ],
            env={"foo": "bar"},
            stderr=-2,
        )

    @patch.dict(os.environ, {"JUJU_CHARM_HTTP_PROXY": "proxy"}, clear=True)
    @patch("subprocess.check_output")
    def test_synchronize_action_all_params(self, mock_subproc):
        process_mock = Mock()
        mock_subproc.return_value = process_mock
        harness = Harness(SimpleStreamsCharm)
        harness.begin()
        default_config = self.default_config()
        default_config["verbose"] = True
        harness.charm._stored.config = default_config
        action_event = Mock()
        harness.charm._on_synchronize_action(action_event)
        self.assertTrue(mock_subproc.called)
        assert mock_subproc.call_args == call(
            [
                "sstream-mirror",
                "--keep",
                "--keyring={}".format(default_config["keyring-file"]),
                "--verbose",
                "--path={}".format(default_config["path"]),
                "--log-file={}".format(default_config["log-file"]),
                "--max={}".format(default_config["image-max"]),
                default_config["image-source"],
                "{}/latest".format(default_config["image-dir"]),
                default_config["image-selectors"],
            ],
            env={"JUJU_CHARM_HTTP_PROXY": "proxy", "HTTP_PROXY": "proxy"},
            stderr=-2,
        )

    @patch("os.symlink")
    @patch("os.makedirs")
    @patch("os.path.isdir")
    @patch("builtins.open", new_callable=mock_open)
    def test_publish_relation_joined(self, mock_open_call, os_path_isdir, os_makedirs, os_symlink):
        harness = Harness(SimpleStreamsCharm)
        harness.begin()
        default_config = self.default_config()
        self.assertEqual(harness.charm._stored.config, {})
        harness.update_config(default_config)
        relation_id = harness.add_relation("publish", "webserver")
        harness.add_relation_unit(relation_id, "webserver/0")
        assert harness.get_relation_data(relation_id, harness._unit_name) == {
            "path": "{}/publish".format(default_config["image-dir"])
        }

    @patch("os.walk")
    @patch("shutil.copytree")
    @patch("os.path.exists")
    @patch("os.symlink")
    @patch("os.makedirs")
    def test_create_snapshot_action(
        self, os_makedirs, os_symlink, os_path_exists, shutil_copytree, os_walk
    ):
        def a2g(x):
            return ([n, ["{}".format(n)]] for n in x)

        rand_n = random.randint(10, 100)
        os_walk.side_effect = iter([a2g([rand_n])])
        os_path_exists.return_value = False
        default_config = self.default_config()
        harness = Harness(SimpleStreamsCharm)
        harness.begin()
        harness.charm._stored.config = default_config
        harness.charm._get_snapshot_name = Mock()
        snapshot_name = uuid4()
        harness.charm._get_snapshot_name.return_value = snapshot_name
        action_event = Mock()
        harness.charm._on_create_snapshot_action(action_event)
        self.assertTrue(os_symlink.called)
        assert os_symlink.call_args == call(
            "{}/latest/{}".format(default_config["image-dir"], rand_n),
            "{}/{}/{}".format(default_config["image-dir"], snapshot_name, rand_n),
        )
        assert shutil_copytree.call_args == call(
            "{}/latest/.data".format(default_config["image-dir"]),
            "{}/{}/.data".format(default_config["image-dir"], snapshot_name),
        )

    @patch("os.walk")
    @patch("shutil.copytree")
    @patch("os.path.exists")
    @patch("os.makedirs")
    def test_create_snapshot_copy_action(
        self, os_makedirs, os_path_exists, shutil_copytree, os_walk
    ):
        def a2g(x):
            return ([n, ["{}".format(n)]] for n in x)

        rand_n = random.randint(10, 100)
        os_walk.side_effect = iter([a2g([rand_n])])
        os_path_exists.return_value = False
        default_config = self.default_config()
        default_config["copy-on-snapshot"] = True
        harness = Harness(SimpleStreamsCharm)
        harness.begin()
        harness.charm._stored.config = default_config
        harness.charm._get_snapshot_name = Mock()
        snapshot_name = uuid4()
        harness.charm._get_snapshot_name.return_value = snapshot_name
        action_event = Mock()
        harness.charm._on_create_snapshot_action(action_event)
        assert shutil_copytree.call_args_list[0] == call(
            "{}/latest/{}".format(default_config["image-dir"], rand_n),
            "{}/{}/{}".format(default_config["image-dir"], snapshot_name, rand_n),
        )
        assert shutil_copytree.call_args_list[1] == call(
            "{}/latest/.data".format(default_config["image-dir"]),
            "{}/{}/.data".format(default_config["image-dir"], snapshot_name),
        )

    @patch("os.walk")
    def test_list_snapshots_action(self, os_walk):
        def a2g(x):
            return ([n, ["snapshot-{}".format(n)]] for n in x)

        rand_n = random.randint(10, 100)
        os_walk.return_value = a2g([rand_n])
        default_config = self.default_config()
        harness = Harness(SimpleStreamsCharm)
        harness.begin()
        harness.charm._stored.config = default_config
        harness.charm._get_snapshot_name = Mock()
        action_event = Mock()
        harness.charm._on_list_snapshots_action(action_event)
        assert action_event.set_results.call_args == call(
            {"snapshots": ["snapshot-{}".format(rand_n)]}
        )

    @patch("shutil.rmtree")
    def test_delete_snapshot_action(self, shutil_rmtree):
        default_config = self.default_config()
        harness = Harness(SimpleStreamsCharm)
        harness.begin()
        harness.charm._stored.config = default_config
        harness.charm._get_snapshot_name = Mock()
        snapshot_name = uuid4()
        action_event = Mock(params={"name": snapshot_name})
        harness.charm._on_delete_snapshot_action(action_event)
        assert shutil_rmtree.call_args == call(
            "{}/{}".format(default_config["image-dir"], snapshot_name)
        )

    @patch("os.path.isdir")
    @patch("os.path.islink")
    @patch("os.symlink")
    @patch("os.unlink")
    def test_publish_snapshot_action_success(
        self, os_unlink, os_symlink, os_path_islink, os_path_isdir
    ):
        default_config = self.default_config()
        harness = Harness(SimpleStreamsCharm)
        harness.begin()
        harness.charm._stored.config = default_config
        harness.charm._get_snapshot_name = Mock()
        snapshot_name = uuid4()
        action_event = Mock(params={"name": snapshot_name})
        harness.charm._on_publish_snapshot_action(action_event)
        assert os_symlink.call_args == call(
            "{}/{}".format(default_config["image-dir"], snapshot_name),
            "{}/publish".format(default_config["image-dir"]),
        )

    @patch("os.path.isdir")
    @patch("os.path.islink")
    @patch("os.symlink")
    @patch("os.unlink")
    def test_publish_snapshot_action_fail(
        self, os_unlink, os_symlink, os_path_islink, os_path_isdir
    ):
        os_path_isdir.return_value = False
        default_config = self.default_config()
        harness = Harness(SimpleStreamsCharm)
        harness.begin()
        harness.charm._stored.config = default_config
        harness.charm._get_snapshot_name = Mock()
        snapshot_name = uuid4()
        action_event = Mock(params={"name": snapshot_name})
        harness.charm._on_publish_snapshot_action(action_event)
        assert action_event.fail.call_args == call("Snapshot does not exist")
