#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" Cantata-Dynamic

Copyright (c) 2021 Stefan Schwendeler <kungpfui@github.com>
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

import codecs
import os
import random
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from typing import Sequence, Iterable, Optional, Callable, Union, List, Tuple, Type

from .config import Config
from .rules import Rules
from .playqueuehistory import PlayQueueHistory
from .mpd_connect import MpdConnection, ConnInfo

from .httpserver import start_server as start_http_server
from .httphandler import CDRequestHandler
from .cantata_codec import cantata_search_function
codecs.register(cantata_search_function)

import logging, logging.handlers

# logfile stuff
_log = None


def create_logger(log_file, log_level=logging.WARNING, maxsize=2 * 2 ** 20, maxnb=3):
    global _log

    # create rotating logger
    handler = logging.handlers.RotatingFileHandler(log_file, mode='a', maxBytes=maxsize, backupCount=maxnb)
    # create formatter
    formatter = logging.Formatter('%(levelname)s:%(name)s:%(asctime)s:%(message)s')
    handler.setFormatter(formatter)
    # add as root handler
    ml = logging.getLogger('')
    ml.setLevel(log_level)
    ml.addHandler(handler)

    _log = logging.getLogger(__name__)
    _log.info('process (re-)started')


class MPDStatus:
    attributes = ('dynamic', 'text', 'time')

    def __init__(self, **kwargs):
        self.dynamic: bool = kwargs.get('dynamic', False)
        self.text: str = kwargs.get('text', "IDLE")
        self.time: int = kwargs.get('time', self.timestamp())

    def update(self, **kwargs):
        for key, value in kwargs.items():
            if key in MPDStatus.attributes:
                setattr(self, key, value)
            else:
                raise KeyError(f'"{key}" not in {MPDStatus.attributes} attributes')

    def timestamp(self) -> int:
        self.time = int(time.time())
        return self.time


class MPD:
    def __init__(self, conf, server_mode: bool, test_mode: bool):
        """
        :param conf:
        :param test_mode:
        """
        self.active_file = conf.activeFile  # that's the softlink to the current .rules file
        self.server_mode = server_mode
        self.test_mode = test_mode

        self.conn_info = ConnInfo(conf.mpdHost, conf.mpdPort, conf.mpdPassword)
        self.conn = None

        self.rules = Rules(conf.filesDir, conf.activeFile, test_mode)

        self.status = MPDStatus(text="IDLE", dynamid=False)
        self.play_queue_history = PlayQueueHistory()

        self.db_updated = False
        self.songs = []

    def connect(self, handle_client_message: Callable):
        self._read_connection_info()
        self.conn = MpdConnection(self.conn_info, self.server_mode, handle_client_message, self.test_mode)

    def get_active(self) -> str:
        """Filename without extension of active rule file. Identified by de-referencing the softlink."""
        filename = ""
        if os.path.islink(self.active_file) and os.path.isfile(self.active_file):  # sure?
            filename = os.path.splitext(os.path.basename(os.readlink(self.active_file)))[0]
        return filename

    def _read_connection_info(self) -> None:
        """ Read MPDs host, port, and password details from env - if set and update self.conn_info
        """
        hostEnv = os.environ.get('MPD_HOST')
        portEnv = os.environ.get('MPD_PORT')
        if portEnv is not None and len(portEnv) > 2:
            self.conn_info.port = int(portEnv)

        if hostEnv is not None and len(hostEnv) > 2:
            pw_host = hostEnv.split('@', 1)
            if len(pw_host) == 2:
                self.conn_info.passwd, self.conn_info.host = pw_host
            else:
                self.conn_info.host = pw_host[0]

    def query(self: object, command: str, key: Optional[str] = None) -> Union[List[str], List[Tuple[str, str]]]:
        """like send_command but analyses the lines as well"""
        entries = []
        data = self.conn.send_command(command)
        if data:
            for line in data.splitlines():
                key_value = line.split(': ', 1)
                if len(key_value) == 2:
                    if key is None:
                        entries.append(key_value)
                    else:
                        if key == key_value[0]:
                            entries.append(key_value[1])
        return entries

    def _song_rating_in_range(self, sticker_entry: str) -> bool:
        """ Parse sticker value, and check that its in range."""
        parts = sticker_entry.split('=')
        if len(parts) == 2:
            rating = int(parts[1])
            if rating in self.rules.rating or (rating == 0 and self.rules.includeUnrated):
                return True
        return False

    def _get_rated_songs(self) -> List[str]:
        """ Get all songs with a rating between ratingFrom & ratingTo """
        answer = self.query('sticker find song "" rating')
        entries = []
        file = ""
        for key, value in answer:
            if key == 'file':
                file = value
            elif key == 'sticker':
                if self._song_rating_in_range(value):
                    entries.append(file)
        return entries

    def check_song_rating_in_range(self, filename: str, pos: Optional[int] = None) -> bool:
        """ Is a file with rating from .. rating to? """
        if self.rules.rating <= 0:  # No filter, so must be in range!
            return True
        num_mpd_songs = len(self.songs)
        if num_mpd_songs == 0:  # No songs!
            return False

        if not self.rules.include:
            # There were no include rules, so all files matching rating range were chose.
            # Therefore, no need to check ratings now.
            return True

        for entry in self.query(f'sticker get song "{filename}" rating', 'sticker'):
            if self._song_rating_in_range(entry):
                return True

        # Song is not within range, so 'blank' its name out of list
        if self.test_mode:
            print(f"{filename} is NOT in rating range - remove:{pos} total:{num_mpd_songs}!")

        del self.songs[pos]
        return False

    def check_song_duration_in_range(self, file, pos: Optional[int] = None) -> bool:
        """ Check song duration is in range """

        if self.rules.duration <= 0:
            return True

        num_mpd_songs = len(self.songs)
        if num_mpd_songs == 0:  # No songs!
            return False

        entries = self.query(f'lsinfo "{file}"', 'Time')
        if len(entries) == 1:
            val = int(entries[0])
            if (self.rules.duration.min == 0 or val >= self.rules.duration.min) and (
                    self.rules.duration.max == 0 or val <= self.rules.duration.max):
                return True

        # Song is not within range, so 'blank' its name out of list
        if self.test_mode:
            print(f"{file} is NOT in duration range - remove:{pos} total:{num_mpd_songs}!")

        del self.songs[pos]
        return False

    def get_songs(self) -> None:
        """ Use rules to obtain a list of songs from MPD. Modifies self.songs """

        # If we have no current songs, or rules have changed, or MPD has been updated - then we need to run the rules against MPD to get song list...
        if not self.songs or self.rules.changed or self.db_updated:
            exclude_songs = set()
            if self.rules.exclude:
                # Get list of songs that should be removed from the song list...
                for rule in self.rules.exclude:
                    songs = self.query(rule, 'file')
                    exclude_songs |= set(songs)

            songs = set()
            if self.rules.include:
                for rule in self.rules.include:
                    songs |= set(self.query(rule, 'file'))
            elif self.rules.rating.min >= 1 and self.rules.rating.max >= 0:
                if self.test_mode:
                    print(
                        "No include rules, so get all songs in rating range {self.rules.rating.min}..{self.rules.rating.max}...")
                songs = set(self._get_rated_songs())
            else:
                if self.test_mode:
                    print("No include rules, so get all songs...")

                # No 'include' rules => get all songs! Do this by getting all Artists, and then all songs by each...
                tag = 'Artist'
                entries = self.query(f"list {tag}", tag)
                for entry in entries:
                    songs |= set(self.query(f'find {tag} "{entry}"', 'file'))

            self.songs = list(songs - exclude_songs)
            if not self.songs:
                if self.server_mode:
                    self.status.update(dynamic=False, text="NO_SONGS")
                    self.send_status()
                else:
                    self.send_message("showError", "NO_SONGS")
                    sys.exit(0)

            elif self.server_mode:
                self.send_message("status", "HAVE_SONGS")

            if self.test_mode:
                print("SONGS--------------")
                for song in self.songs:
                    print(f"{song}")
                print("---------------------")

    def send_message(self, method: str, argument: str, client_id: Optional[str] = None) -> None:
        """ Send message to Cantata application...

        :param method:
        :param argument:
        :param client_id:
        """
        if self.server_mode:
            if client_id == "http":
                return
            elif client_id:
                self.conn.send_command(f'sendmessage {MpdConnection.writeChannel}-{client_id} "{method}:{argument}"')
            else:
                self.conn.send_command(f'sendmessage {MpdConnection.writeChannel} "{method}:{argument}"')
        else:
            if sys.platform.startswith("darwin"):
                # MacOSX
                pass
            # TODO: How to send a dbus (or other) message to Cantata application?
            else:
                # Linux
                try:
                    subprocess.call(['qdbus', 'mpd.cantata' '/cantata', method, argument])
                except FileNotFoundError:
                    # Maybe qdbus is not installed? Try dbus-send...
                    subprocess.call(['dbus-send', '--type=method_call', '--session', '--dest=mpd.cantata', '/cantata',
                                     f'mpd.cantata.{method}', f'string:{argument}'])

    def populate_play_queue_forever(self):
        """
        This is the 'main' function of the dynamizer
        """

        re_song = re.compile(r'song: (\d+)')
        re_db_update = re.compile(r'db_update: (\d+)')

        lastMpdDbUpdate = -1
        while True:
            socketData = ''
            if self.status.dynamic:
                # Use status to obtain the current song pos, and to check that MPD is running...
                socketData = self.conn.status()
            elif self.server_mode:
                while not self.status.dynamic:
                    self.conn.wait_for_event()

            if socketData:
                lines = socketData.splitlines()
                play_queue_track_pos: int = 0
                isPlaying = False

                for val in lines:
                    mobj = re_song.match(val)
                    if mobj:
                        play_queue_track_pos = int(mobj.group(1))
                    elif val.startswith('state: play'):
                        isPlaying = True

                # Call stats, so that we can obtain the last time MPD was updated.
                # We use this to determine when we need to refresh the searched set of songs
                self.db_updated = False
                socketData = self.conn.stats()
                if socketData:
                    lines = socketData.splitlines()

                    for val in lines:
                        mobj = re_db_update.match(val)
                        if mobj:
                            mpdDbUpdate = int(mobj.group(1))
                            if mpdDbUpdate != lastMpdDbUpdate:
                                lastMpdDbUpdate = mpdDbUpdate
                                self.db_updated = True
                            break

                # Get current playlist info
                socketData = self.conn.playlist()
                if socketData:
                    lines = socketData.splitlines()
                    play_queue_length: int = len(lines)
                    if play_queue_length > 0 and lines[-1].startswith('OK'):
                        play_queue_length -= 1

                    # trim playlist start so that current becomes <= playQueueDesiredLength / 2
                    wantCurrentPos = self.rules.playQueueDesiredLength // 2
                    for i in range(play_queue_track_pos - (wantCurrentPos - 1)):
                        self.conn.delete(0)
                        play_queue_length -= 1

                    if play_queue_length < 0:
                        play_queue_length = 0

                    self.rules.readRules(self.query)
                    self.get_songs()
                    if self.songs:
                        # fill up playlist to 10 random tunes
                        failures = 0
                        added = 0
                        while play_queue_length < self.rules.playQueueDesiredLength and self.songs:
                            pos = random.randrange(len(self.songs))
                            origFile = self.songs[pos]
                            file = origFile.replace('\\', '\\\\').replace('"', '\\"')

                            if self.check_song_duration_in_range(file, pos) and self.check_song_rating_in_range(file,
                                                                                                                pos):
                                if failures > 100 or self.play_queue_history.can_add(origFile, len(self.songs)):
                                    if self.conn.send_command(f'add "{file}"') != '':
                                        self.play_queue_history.store_song(origFile)
                                        play_queue_length += 1
                                        failures = 0
                                        added += 1
                                else:  # Song is already in playqueue history...
                                    failures += 1

                        # If we are not currently playing and we filled playqueue - then play first!
                        if self.songs and isPlaying == 0 and added == self.rules.playQueueDesiredLength:
                            self.conn.send_command("play 0")

                    if self.songs:
                        self.conn.wait_for_event()
                    else:
                        if self.server_mode:
                            self.status.update(text="NO_SONGS", dynamic=False)
                            self.send_status()
                        else:
                            self.send_message("showError", "NO_SONGS")
                            sys.exit(0)
                elif not self.server_mode:
                    time.sleep(2.0)

            elif not self.server_mode:
                time.sleep(2.0)

    # #################################################################################################
    # SERVER MODE
    # #################################################################################################
    @staticmethod
    def read_rules_file(filename: str) -> List[str]:
        """ Read the content of the given rules file
        :param filename: the filename
        :return: list with lines of rules
        """
        filename = urllib.parse.unquote(filename)
        with open(filename, 'r') as f:
            lines = f.read().splitlines()

        return [(line if line.endswith('\n') else line + '\n') for line in lines]

    def list_rules(self, req: str, client_id: str, show_contents: bool = True) -> None:
        """find all files in 'rules' folder"""
        result = []

        for root, dirs, files in os.walk(self.rules.dir):
            for file in files:
                if file.endswith('.rules'):
                    result.append(f'FILENAME:{file}\n')

                    if show_contents:
                        fp = os.path.join(root, file)
                        result += self.read_rules_file(fp)

        if req == "http":
            return result

        response = codecs.encode(''.join(result), 'cantata')
        self.send_message(req, response, client_id)

    def get_rules(self, req: str, client_id: str, orig_name: str) -> None:
        name = codecs.decode(orig_name, 'cantata').replace('/', '')

        # active = self.rules.determineActiveRules()
        filepath = f"{self.rules.dir}/{name}.rules"
        result = self.read_rules_file(filepath)
        response = codecs.encode(''.join(result), 'cantata')
        self.send_message(req, response, client_id)

    def save_rules(self, req: str, client_id: str, orig_name: str, content=""):
        name = codecs.decode(orig_name, 'cantata').replace('/', '')
        if not name:
            self.send_message(req, "1", client_id)
            return

        if name.endswith('.rules') or '/' in name:
            self.send_message(req, f"2:{orig_name}", client_id)
            return

        content = codecs.decode(content, 'cantata')
        # TODO: Parse content!!!
        filepath = f"{self.rules.dir}/{name}.rules"

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)

            self.status.timestamp()
            self.send_message(req, f"0:{orig_name}", client_id)
            self.send_status(client_id)
        except OSError:
            self.send_message(req, f"3:{orig_name}", client_id)

    def delete_rules(self, req: str, client_id: str, orig_name: str):
        """
        :param req:
        :param client_id:
        :param orig_name:
        :return:
        """
        name = codecs.decode(orig_name, 'cantata').replace('/', '')
        active_filename = self.get_active()
        filepath = f"{self.rules.dir}/{name}.rules"
        try:
            os.unlink(filepath)
        except OSError:
            self.send_message(req, f"4:{orig_name}", client_id)
            return

        self.status.timestamp()
        if name == active_filename:
            self.control(req, client_id, "stop", "true")

        self.send_message(req, f"0:{orig_name}", client_id)
        self.send_status(client_id)

    def control(self, req, client_id, command, clear_on_stop=""):
        if command == "start":
            self.status.update(dynamic=True, text="STARTING")
            self.conn.clear()
            self.send_message(req, f"0:{command}", client_id)

        elif command == "stop":
            self.status.update(dynamic=False, text="IDLE")
            if clear_on_stop == "true" or clear_on_stop == "1" or clear_on_stop == "clear":
                self.conn.clear()

            self.send_message(req, f"0:{command}", client_id)
            self.send_status(client_id)
        else:
            self.send_message(req, f"5:{command}", client_id)

    def setActive_rules(self, req, client_id, origName, start=""):
        name = codecs.decode(origName, 'cantata')
        if name == "":
            self.send_message(req, "1", client_id)
            return

        rulesName = name
        active_filename = self.get_active()
        if rulesName == active_filename:
            if start in ("start", "1") and self.status.text == "IDLE":
                self.status.update(dynamic=True, text="STARTING")
                self.conn.clear()
                self.send_status()

            self.send_message(req, f"0:{origName}", client_id)
            return

        rulesName = f"{self.rules.dir}/{rulesName}.rules"
        if os.path.isfile(rulesName):
            if os.path.islink(self.active_file):
                try:
                    os.unlink(self.active_file)
                except OSError:
                    _log.error(f'setActiveRules: {req}, 6, {client_id}')
                    self.send_message(req, "6", client_id)
                    return

            elif os.path.isfile(self.active_file):
                _log.error(f'setActiveRules: {req}, 7:{origName}, {client_id}')
                self.send_message(req, f"7:{origName}", client_id)
                return

            try:
                os.symlink(rulesName, self.active_file)
            except OSError:
                _log.error(
                    f'setActiveRules: {req}, 8:{origName}, {client_id}; os.symlink({rulesName}, {self.active_file})')
                self.send_message(req, f"8:{origName}", client_id)
                return

            if start == "start" or start == "1":
                self.status.update(dynamic=True, text="STARTING")
                self.conn.clear()

            self.send_message(req, f"0:{origName}", client_id)
            self.send_status(client_id)
        else:
            self.send_message(req, f"9:{origName}", client_id)

    def status_response(self, req, client_id: Optional[str] = None) -> None:
        """
        :param req:
        :param client_id:
        :return:
        """
        active_filename = self.get_active()
        active = codecs.encode(active_filename, 'cantata')
        self.send_message(req, f'{self.status.text}:{self.status.time}:{active}', client_id)

    def send_status(self, client_id: Optional[str] = None) -> None:
        self.status_response("status", client_id)

    def handle_client_message(self, data: str) -> None:
        for line in data.splitlines():
            if line.startswith('message: '):
                line = line.replace('message: ', '')
                parts = line.split(":")
                length = len(parts)
                if self.test_mode:
                    print(f"Message: {line} ({parts[0]}, {length})")

                if length >= 2:
                    if parts[0].endswith('status'):
                        self.status_response(parts[0], parts[1])
                    elif parts[0].endswith('list'):
                        self.list_rules(*parts)
                    elif parts[0].startswith('get'):
                        self.get_rules(*parts)
                    elif parts[0].startswith('save'):
                        self.save_rules(*parts)
                    elif parts[0].startswith('delete'):
                        self.delete_rules(*parts)
                    elif parts[0].startswith('setActive'):
                        self.setActive_rules(*parts)
                    elif parts[0].startswith('control'):
                        self.control(*parts)
                    else:
                        self.send_message(parts[0], "11", parts[1])
                else:
                    self.send_message(parts[0], "10", parts[1])


_mpd: Union[MPD, None] = None

def load_config(app_config):
    """ Attempt to load a config file that will specify MPD connection settings and dynamic folder location """

    if not app_config or app_config.startswith('default'):
        app_config = "/etc/opt/cantatadyn.conf"

    return Config(app_config)


def start_server(config=None, test_mode=False):
    global _mpd
    conf = load_config(config)

    log_file = os.path.join(conf.logDir, 'cantata-dynamic.log')
    log_level = logging.INFO if test_mode else logging.WARNING
    create_logger(log_file, log_level)

    _mpd = MPD(conf, server_mode=True, test_mode=test_mode)
    _mpd.connect(_mpd.handle_client_message)

    if conf.httpPort > 0:
        CDRequestHandler.mpd = _mpd
        start_http_server(conf.httpPort, CDRequestHandler)

    _mpd.populate_play_queue_forever()



if __name__ == '__main__':
    main()
