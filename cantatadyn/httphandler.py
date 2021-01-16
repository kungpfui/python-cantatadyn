#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" Cantata-Dynamic

Copyright (c) 2021 Stefan Schwendeler <kungpfui@users.noreply.github.com>
Copyright (c) 2011-2016 Craig Drummond <craig.p.drummond@gmail.com>

----

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; see the file COPYING.  If not, write to
the Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor,
Boston, MA 02110-1301, USA.
"""

import time
import codecs
import logging
from .httpserver import HTTP11RequestHandler
from .mpd_connect import MpdConnection

from typing import  NoReturn, Dict

_log = logging.getLogger(__name__)


class CDRequestHandler(HTTP11RequestHandler):
    """Cantata Dynamic HTTP-Server's Request Handler"""
    server_version = 'CantataDynamicServer/0.1'

    # needs a new socket connection an there is only one such connection
    conn = None
    mpd = None   # set before use

    def main_page(self, path: str, query: dict) -> str:
        body = "<html><head>" \
               "<title>Dynamic Playlists</title>" \
               "<style>a a:link a:visited { color: Black; } </style>" \
               "</head>" \
               "<body><h2>Dynamic Playlists</h2>" \
               "<p><i>Click on a playlist name to load</i></p>"

        _log.info(f'main_page({path}, {query})')
        rules = self.mpd.list_rules("http", 0, False)
        _log.info(f'rules = {rules}')
        active_filename = self.mpd.get_active()
        _log.info(f'active_filename = {active_filename}')
        ul_list = ['<p><ul>']
        num = 1
        for rule in rules:
            rule = rule.replace('FILENAME:', '').replace('.rules', '').replace('\n', '')
            if rule.startswith('TIME:'):
                pass
            else:
                ## TODO: html and url escaping?
                li = f'<a href="/setActive?name={rule}&start=1">{rule}</a>'
                if rule == active_filename:
                    li = f"<b>{li}</b>"
                ul_list.append(f"<li>{li}</li>")
                num += 1

        ul_list.append('</ul></p>')
        body += ''.join(ul_list)
        body += '<p><form method=post enctype="text/plain" action="/stop">' \
                '<input type="submit" name="submit" value="Stop Dynamizer"></form></p>' \
                '</body></html>'
        return body

    def _send_command(self, command: str, param: Dict) -> NoReturn:
        """ HTTP interface..."""
        param = codecs.encode(param, 'cantata')
        if self.conn is None:
            _log.info(f'connect to mpd')
            CDRequestHandler.conn = MpdConnection(self.mpd.conn_info, server_mode=self.mpd.server_mode,
                                                  handle_client_message=None, verbose=self.mpd.test_mode)
            _log.info(f'mpd connected')
        self.conn.send_command(f'sendmessage {MpdConnection.readChannel} "{command}:http:{param}:1"')
        time.sleep(1.5)

    def setActive(self, path: str, query_dict: Dict) -> NoReturn:
        self._send_command("setActive", query_dict['name'][0])
        self.redirect('/')

    def stop(self, path, query_dict) -> NoReturn:
        self._send_command("control", "stop")
        self.redirect('/')

    def action_handler(self, cmd: str, path: str, query_dict: Dict):
        actions = {'get': {'': self.main_page, 'setActive': self.setActive},
                   'post': {'stop': self.stop},
                   }
        if path in actions[cmd]:
            return actions[cmd][path](path, query_dict)
