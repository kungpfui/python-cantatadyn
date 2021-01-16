#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import socket
import time
import logging
from typing import Callable
from dataclasses import dataclass

_log = logging.getLogger(__name__)


@dataclass
class ConnInfo:
    host: str
    port: int
    passwd: str


class MpdConnection:
    readChannel = "cantata-dynamic-in"
    writeChannel = "cantata-dynamic-out"

    def __init__(self, conn_info, server_mode: bool, handle_client_message: Callable, verbose: bool=False):
        self.sock = None
        self.verbose = verbose

        self.conn_info = conn_info

        self.server_mode = server_mode
        self.handle_client_message = handle_client_message

    def log(self, msg: str, log: Callable=_log.info):
        if self.verbose:
            prefix = 'ERROR: ' if log is _log.error else ''
            print(prefix + msg)
        log(msg)

    def connect(self):
        """ Connect to MPD """
        self.log(f"Connecting to MPD {self.conn_info.host}:{self.conn_info.port}")

        if self.conn_info.host.startswith('/'):
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.sock.connect(self.conn_info.host)
            conn_details = self.conn_info.host
        else:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.conn_info.host, self.conn_info.port))
            conn_details = f"{self.conn_info.host}:{self.conn_info.port}"

        if self.sock is not None:
            data = self.read_reply()
            if data:
                if self.conn_info.passwd:
                    self.log("Send password")

                    self.sock.sendall(bytes(f"password {self.conn_info.passwd}\n", 'utf-8'))
                    data = self.read_reply()
                    if not data:
                        self.log("Invalid password", _log.error)
                        self.sock.close()
                        self.sock = None

                if self.server_mode:
                    self.sock.sendall(bytes(f"subscribe {self.readChannel}\n", 'utf-8'))
                    self.read_reply()

            else:
                self.log(f"Failed to read connection reply fom MPD ({conn_details})", _log.error)
                self.sock.close()
                self.sock = None
        else:
            self.log(f"Failed to connect to MPD ({conn_details})", _log.error)

    def send_command(self, cmd: str) -> str:
        """ Send a command and returns the answer
        :param cmd:
        :return:
        """
        self.log(f'Send command "{cmd}"')

        attemps = 3
        while attemps > 0:
            try:
                if self.sock is None:
                    self.connect()

                data = ''
                if self.sock is not None:
                    self.sock.sendall(bytes(cmd, 'utf-8') + b"\n")
                    data = self.read_reply()

                self.log(f"Received {len(data)} bytes")
                break

            except (IOError, BrokenPipeError):
                attemps -= 1
                if self.sock:
                    self.sock.close()
                    self.sock = None
                time.sleep(0.5)
        else:
            # failed, but what should we do?
            data = ''
        return data

    def read_reply(self) -> str:
        """
        :rtype: str
        """
        socketData = b''
        while self.sock is not None:
            data = self.sock.recv(1024)  # busy wait
            if not data:
                return ''
            socketData += data
            data = b''

            if socketData.startswith(b'OK') or socketData.endswith(b'OK\n'):
                return str(socketData, encoding='utf-8')
            elif socketData.startswith(b'ACK'):
                return ''

    def wait_for_event(self) -> bool:
        """
        :return:
        """
        _log.info('call: wait_for_event')
        while True:
            if self.sock is None:
                self.connect()

            if self.sock is not None:
                if not self.server_mode:
                    self.send_command("idle player playlist")
                    return True

                # server mode
                data = self.send_command("idle player playlist message")
                lines = data.splitlines()
                have_non_msg = False
                for line in lines:
                    if line.startswith('changed: message'):
                        self.handle_client_message(self.read_messages())
                    else:
                        have_non_msg = True
                        self.log(f"Idle message: {line}")
                if have_non_msg:
                    return True
            else:
                return False

    def read_messages(self) -> str:
        self.sock.sendall(b"readmessages\n")
        return self.read_reply()

    def clear(self) -> str:
        return self.send_command("clear")

    def status(self) -> str:
        return self.send_command("status")

    def stats(self) -> str:
        return self.send_command("stats")

    def playlist(self) -> str:
        return self.send_command("playlist")

    def delete(self, idx: int=0) -> str:
        return self.send_command(f"delete {idx}")
