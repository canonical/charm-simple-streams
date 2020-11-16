#!/usr/bin/env python3
# Copyright 2020 Ubuntu
# See LICENSE file for licensing details.

import logging
import copy

from ops.charm import CharmBase
from ops.main import main
from ops.framework import StoredState
from ops.model import ActiveStatus, BlockedStatus

import subprocess
import os
import time
from datetime import datetime
import shutil

logger = logging.getLogger(__name__)


class SimpleStreamsCharm(CharmBase):
    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.update_status, self._on_update_status)
        self.framework.observe(self.on.synchronize_action, self._on_synchronize_action)
        self.framework.observe(self.on.create_snapshot_action, self._on_create_snapshot_action)
        self.framework.observe(self.on.publish_snapshot_action, self._on_publish_snapshot_action)
        self.framework.observe(self.on.list_snapshots_action, self._on_list_snapshots_action)
        self.framework.observe(self.on.delete_snapshot_action, self._on_delete_snapshot_action)
        self.framework.observe(self.on.publish_relation_joined,
                               self._on_publish_relation_joined)
        self._stored.set_default(config={})

    def _on_publish_relation_joined(self, event):
        publish_path = self._image_publish_dir()
        event.relation.data[self.model.unit].update({'path': publish_path})

    def _on_update_status(self, _):
        path = self._image_publish_dir() + '/.data'
        if os.path.isdir(path):
            stat = os.stat(path)
            self.model.unit.status = \
                ActiveStatus("Publishes: {}".format(time.ctime(stat.st_mtime)))
        else:
            self.model.unit.status = BlockedStatus("Images not synchronized")

    def _on_install(self, _):
        subprocess.check_output(["apt", "install", "-y", "simplestreams"])

    def _on_config_changed(self, _):
        for key in self.model.config:
            if key not in self._stored.config:
                value = self.model.config[key]
                self._stored.config[key] = value
            if self.model.config[key] != self._stored.config[key]:
                value = self.model.config[key]
                logger.info("Setting {} to: {}".format(key, value))
                self._stored.config[key] = value
        if not os.path.isdir(self._image_download_dir()):
            os.makedirs(self._image_download_dir())
        if not os.path.isdir(self._image_publish_dir()):
            os.symlink(self._image_download_dir(), self._image_publish_dir())
        if 'cron-schedule' in self._stored.config and \
           self._stored.config['cron-schedule'] != 'None':
            self._setup_cron_job(self._stored.config)

    def _on_synchronize_action(self, event):
        selectors = self._stored.config['image-selectors']
        for selector in selectors.splitlines():
            logger.info("Syncing {}".format(selector))
            env = copy.deepcopy(os.environ)
            if 'JUJU_CHARM_HTTP_PROXY' in env:
                env['HTTP_PROXY'] = env['JUJU_CHARM_HTTP_PROXY']
            if 'JUJU_CHARM_HTTPS_PROXY' in env:
                env['HTTPS_PROXY'] = env['JUJU_CHARM_HTTPS_PROXY']
            try:
                subprocess.check_output(self._sync_selector_cmd(selector),
                                        env=env,
                                        stderr=subprocess.STDOUT)
                logger.info("Syncing complete")
            except subprocess.CalledProcessError as e:
                logger.info("Error {}".format(e.output))
                event.fail(e.output)
                return

    def _on_create_snapshot_action(self, event):
        snapshot_name = self._get_snapshot_name()
        logger.info("Create snapshot {}".format(snapshot_name))
        snapshot_root = "{}/{}".format(self._stored.config['image-dir'], snapshot_name)
        download_root = self._image_download_dir()
        if not os.path.exists(snapshot_root):
            os.makedirs(snapshot_root)
        for product in next(os.walk(download_root))[1]:
            if '.data' != product:
                if self._stored.config['copy-on-snapshot']:
                    shutil.copytree("{}/{}".format(download_root, product),
                                    "{}/{}".format(snapshot_root, product))
                else:
                    os.symlink("{}/{}".format(download_root, product),
                               "{}/{}".format(snapshot_root, product))
        shutil.copytree("{}/.data".format(download_root),
                        "{}/.data".format(snapshot_root))

    def _on_delete_snapshot_action(self, event):
        snapshot = event.params["name"]
        logger.info("Delete snapshot {}".format(snapshot))
        shutil.rmtree("{}/{}".format(self._stored.config['image-dir'], snapshot))

    def _on_list_snapshots_action(self, event):
        snapshots = []
        for directory in next(os.walk("{}/".format(self._stored.config['image-dir'])))[1]:
            if directory.startswith("snapshot-"):
                snapshots.append(directory)
        logger.info("List snapshots {}".format(snapshots))
        event.set_results({"snapshots": snapshots})

    def _on_publish_snapshot_action(self, event):
        name = event.params["name"]
        logger.info("Publish snapshot {}".format(name))
        snapshot_path = "{}/{}".format(self._stored.config['image-dir'], name)
        publish_path = self._image_publish_dir()
        if not os.path.isdir(snapshot_path):
            event.fail("Snapshot does not exist")
            return
        if os.path.islink(publish_path):
            os.unlink(publish_path)
        os.symlink(snapshot_path, publish_path)
        event.set_results({name: publish_path})

    def _sync_selector_cmd(self, selector, esc_char=None):
        cmd = [
            'sstream-mirror',
        ]
        if 'keep' not in self._stored.config or\
           self._stored.config['keep']:
            cmd.append("--keep")
        if 'keyring-file' not in self._stored.config or\
           not self._stored.config['keyring-file']:
            cmd.append("--no-verify")
        else:
            cmd.append('--keyring={}'.format(self._stored.config['keyring-file']))
        if self._stored.config['verbose']:
            cmd.append("--verbose")
        if 'path' in self._stored.config and self._stored.config['path']:
            cmd.append('--path={}'.format(self._stored.config['path']))
        if 'log-file' in self._stored.config and self._stored.config['log-file']:
            cmd.append('--log-file={}'.format(self._stored.config['log-file']))
        if self._stored.config['image-max']:
            cmd.append('--max={}'.format(self._stored.config['image-max']))
        cmd.append(self._stored.config['image-source'])
        cmd.append(self._image_download_dir())
        for s in selector.split():
            if esc_char:
                cmd.append("{}{}{}".format(esc_char, s, esc_char))
            else:
                cmd.append(s)
        return cmd

    def _setup_cron_job(self, config):
        with open('/etc/cron.d/{}'.format(self.model.app.name), "w") as f:
            for selector in config['image-selectors'].splitlines():
                f.write(
                    "{} root {}\n".format(
                        config['cron-schedule'],
                        " ".join(self._sync_selector_cmd(selector, '\''))
                    )
                )

    def _image_download_dir(self):
        return "{}/latest".format(self._stored.config['image-dir'])

    def _image_publish_dir(self):
        return "{}/publish".format(self._stored.config['image-dir'])

    def _get_snapshot_name(self):
        return 'snapshot-{}'.format(datetime.now().strftime("%Y%m%d%H%M%S"))


if __name__ == "__main__":
    main(SimpleStreamsCharm)
