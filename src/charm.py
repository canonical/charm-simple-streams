#!/usr/bin/env python3
# Copyright 2020 Ubuntu
# See LICENSE file for licensing details.

import logging

from ops.charm import CharmBase
from ops.main import main
from ops.framework import StoredState
from ops.model import ActiveStatus, BlockedStatus

import subprocess
import os
import time

logger = logging.getLogger(__name__)


class SimpleStreamsCharm(CharmBase):
    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.update_status, self._on_update_status)
        self.framework.observe(self.on.synchronize_action, self._on_synchronize_action)
        self._stored.set_default(config={})

    def _on_update_status(self, _):
        path = self._stored.config['image-dir'] + '/.data'
        if os.path.isdir(path):
            stat = os.stat(path)
            self.model.unit.status = \
                ActiveStatus("Last sync: {}".format(time.ctime(stat.st_mtime)))
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
        if 'cron-schedule' in self._stored.config and \
           self._stored.config['cron-schedule'] != 'None':
            self._setup_cron_job(self._stored.config)

    def _on_synchronize_action(self, event):
        selectors = self._stored.config['image-selectors']
        for selector in selectors.splitlines():
            logger.info("Syncing {}".format(selector))
            try:
                subprocess.check_output(self._sync_selector_cmd(selector),
                                        stderr=subprocess.STDOUT)
            except subprocess.CalledProcessError as e:
                logger.info("Error {}".format(e.output))
                event.fail(e.output)
                return

    def _sync_selector_cmd(self, selector, esc_char=None):
        cmd = [
            'sstream-mirror'
        ]
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
        cmd.append(self._stored.config['image-dir'])
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


if __name__ == "__main__":
    main(SimpleStreamsCharm)
