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

import collections
import time
import pickle
import os

import urllib.parse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET

from typing import List

import logging
_log = logging.getLogger(__name__)


Artists = collections.namedtuple('Artists', ['timestamp', 'artists'])

class SimilairArtists:
    """ https://www.last.fm/api/show/artist.getSimilar """
    url = "https://ws.audioscrobbler.com/2.0/"
    api_key = b'F\xee6\xb6O\x0e\x17K\x923\xab\xb7\xb86\xad\x9d'

    persistent_file = 'lastfm.pickle'
    query_timeout = 3600 * 24 * 7 * 4  # that are 4 weeks
    debug_output = False

    def __init__(self, persistent_folder: str = os.curdir):
        self.persistent_path = os.path.join(persistent_folder, self.persistent_file)
        self.known_artists = {}
        self._load()

    def _store(self):
        with open(self.persistent_path, 'wb') as f:
            pickle.dump(self.known_artists, f)

    def _load(self):
        if os.path.exists(self.persistent_path):
            try:
                with open(self.persistent_path, 'rb') as f:
                    self.known_artists = pickle.load(f)
            except Exception as err:
                _log.exception(str(err))
                try:
                    os.unlink(self.persistent_path)
                except Exception:
                    pass

    def query(self, artist: str) -> List[str]:
        """ Query LastFM for artists similar to supplied artist. """
        if artist not in self.known_artists \
            or self.known_artists[artist].timestamp + self.query_timeout < time.time():
            artistSearchResults = collections.OrderedDict()  # keep the order that's important

            params = { 'method': 'artist.getSimilar',
                        'api_key': str(self.api_key.hex()),
                        'artist': artist,
                        'format': 'xml',    # json is possible as well
                        #~ 'limit': str(100)  # optional
                    }
            params_str = urllib.parse.urlencode(params)
            request = '?'.join((self.url, params_str))

            attemps = 3
            while attemps > 0:
                try:
                    with urllib.request.urlopen(request) as f:
                        msg = f.read()
                        if self.debug_output:
                            with open(f'{artist}.xml', 'wb') as x:
                                x.write(msg)

                        root = ET.fromstring(msg)
                        for child in root.iter('artist'):
                            sim_art = child.find('name').text
                            sim_art = sim_art.replace('&amp;', '&').replace('\n', '')
                            artistSearchResults[sim_art] = None
                            #~ print(sim_art)

                        self.known_artists[artist] = Artists(time.time(), list(artistSearchResults.keys()))
                        # store persistent
                        self._store()
                        break

                except urllib.error.URLError:
                    # just retry
                    attemps -= 1
                    time.sleep(1.0)

        return self.known_artists[artist].artists if artist in self.known_artists else []



def _test(artist):
    import sys
    SimilairArtists.debug_output = True
    similair_artists = SimilairArtists()
    artists = similair_artists.query(artist)
    print(str(artists).encode(sys.stdout.encoding, errors="replace"))


if __name__ == "__main__":
    _test('Madonna')
    _test('Elvis')

