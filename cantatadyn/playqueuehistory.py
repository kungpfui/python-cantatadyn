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

import logging
_log = logging.getLogger(__name__)



class PlayQueueHistory:
    """ Following can_add/store_song are used to remember songs that have been added
        to the playqueue, so that we don't re-add them too soon!
    """
    def __init__(self):
        self.history = []
        self.limit = 0

    def can_add(self, file: str, num_songs: int) -> bool:
        """ check if in history

        :param file:
        :param num_songs: number of songs
        :return: True if not in history
        """
        # Calculate a reasonable level for the history...
        if num_songs == 1:
            return True

        elif num_songs < 5:
            pq_limit = round(num_songs / 2.0)
        else:
            pq_limit = min(round(num_songs * 0.75), 200)

        # If the history level has changed, then so must have the rules/mpd/whatever, so add this song anyway...
        if pq_limit != self.limit:
            self.limit = pq_limit
            self.history = []
            return True

        return file not in self.history

    def store_song(self, file: str) -> None:
        """Append file to history of played files.
        :param file:
        """
        if self.limit <= 0:
            self.limit = 5

        if len(self.history) >= self.limit:
            del self.history[0]

        self.history.append(file)
