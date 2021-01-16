#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" Cantata-Dynamic

Copyright (c) 2021 Stefan Schwendeler <kungpfui@users.noreply.github.com>

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

import os
import gzip, zlib
import time
import threading
from io import BytesIO
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlsplit, parse_qs
from typing import Union, Tuple, Type, AnyStr

import logging
_log = logging.getLogger(__name__)


class HTTP11RequestHandler(BaseHTTPRequestHandler):
    server_version = 'SimpleServer/0.1'
    protocol_version = "HTTP/1.1"
    files_root = 'www'
    files = {"favicon.ico": 'image/png'}
    GZIP_LEVEL = 6

    def action_handler(self, cmd:str, path: str, query: dict):
        """ override me """
        print(path, query)
        return "Hello World!"

    @staticmethod
    def url_parse(path: str) -> Tuple[str, str]:
        path_split = urlsplit(path)
        path = path_split.path
        if path and path[0] == '/':	path = path[1:]
        return path, parse_qs(path_split.query)

    def internal_error(self) -> None:
        self.send_error(500, 'Internal Server Error')

    def not_found(self, page) -> None:
        self.send_error(404, f'File Not Found: {page}')

    def redirect(self, location) -> None:
        self.send_response(303)
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Location', location)
        self.send_header('Content-Type', 'text/plain')
        self.send_header('Content-Length', '0')
        self.end_headers()
        self.wfile.write(b'')

    def reply(self, data: AnyStr, type: str='text/html; charset=utf-8') -> None:
        if isinstance(data, str):
            http_data = bytes(data, encoding='utf-8')
        else:
            http_data = data
        assert(isinstance(http_data, (bytes, bytearray)))

        self.send_response(200)
        self.send_header('Content-Type', type)

        if len(http_data) > 512 and type.startswith('text/'):
            enc = self.headers.get('accept-encoding')
            if isinstance(enc, str):
                enc_split = [s.strip().lower() for s in enc.split(',')]
                if 'gzip' in enc_split:
                    self.send_header('Content-Encoding', 'gzip')
                    f = BytesIO()
                    gzip.GzipFile(mode='wb', compresslevel=self.GZIP_LEVEL, fileobj=f).write(http_data)
                    http_data = f.getvalue()
                elif 'deflate' in enc_split:
                    self.send_header('Content-Encoding', 'deflate')
                    http_data = zlib.compress(http_data, self.GZIP_LEVEL)

        self.send_header('Content-Length', str(len(http_data)))
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(http_data)

    def _do(self, do) -> None:
        try:
            path, query_dict = self.url_parse(self.path)
            #~ print(path, query_dict)
            #~ if do == 'post':
                #~ content_len = int(self.headers.get('content-length', 0))
                #~ post_data = self.rfile.read(content_len)

            if path is None or query_dict is None:
                self.not_found(self.path)
            elif path in self.files:
                self.reply(open(os.path.join(self.files_root, path),'rb').read(), type=self.files[path])
            else:
                reply = self.action_handler(do, path, query_dict)
                if reply is not None:
                    self.reply(reply)
                else:
                    self.not_found(self.path)
        except (OSError, IOError) as err:
            _log.exception(str(err))
            try:
                self.not_found(self.path)
            except:
                pass
        except Exception as err:
            _log.exception(str(err))
            try:
                self.internal_error()
            except:
                pass

    def do_GET(self) -> None:
        print("GET httserver")
        _log.info(f'GET {self.path}')
        self._do('get')

    def do_POST(self) -> None:
        _log.info(f'POST {self.path}')
        self._do('post')

    def log_error(self, format, *args) -> None:
        _log.error(' - '.join((self.log_date_time_string(), format % args)))

    def log_message(self, format, *args) -> None:
        text = ' - '.join((self.address_string(), self.log_date_time_string(), format % args))
        _log.info(text)


def start_server(port: int, req_handler: Type[HTTP11RequestHandler]):
    server = HTTPServer(('', port), req_handler)
    server_thread = threading.Thread(target=server.serve_forever)
    # Exit the server thread when the main thread terminates
    server_thread.daemon = True
    server_thread.name = 'HttpThread'
    server_thread.start()
    _log.info(f'http server started on port {port}')


if __name__ == '__main__':
    class TestHandler(HTTP11RequestHandler):
        def action_handler(self, _cmd, path, query):
            print(path, query)
            return "Hello World!"

    start_server(6680, TestHandler)
    time.sleep(60.0)
