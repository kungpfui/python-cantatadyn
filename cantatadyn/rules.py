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

import os
import sys
import time
from typing import Callable, Union, List, Sequence, Iterable, Set
import logging

from .lastfm import SimilairArtists


_log = logging.getLogger(__name__)

MinMaxParam = Union[int, float, str]
class MinMax:
    def __init__(self, _min: MinMaxParam=None, _max: MinMaxParam=None):
        if isinstance(_min, str): _min = int(_min)
        if isinstance(_max, str): _max = int(_max)
        self.min = _min if _min is not None else 0
        self.max = _max if _max is not None else 0

        if self.min > self.max and self.max > 0:
            self.min = _max
            self.max = _min

    def __contains__(self, value: Union[int, float]) -> bool:
        return self.min <= value <= self.max

    def __eq__(self, other) -> bool:
        """equal"""
        return self.min == other.min and self.max == other.max

    def __ne__(self, other) -> bool:
        """not equal"""
        return self.min != other.min or self.max != other.max

    def __le__(self, other: Union[int, float]) -> bool:
        """lower or equal"""
        return self.min <= other and self.max <= other

    def copy(self):
        """shallow copy"""
        return MinMax(self.min, self.max)


class RulesParam:
    attrs = ('include', 'exclude', 'rating', 'duration')

    def __init__(self):
        self.include: set = set()
        self.exclude: set = set()
        self.rating: MinMax = MinMax()
        self.duration: MinMax = MinMax()

    def __ne__(self, other):
        """not equal"""
        return self.include ^ other.include \
               or self.exclude ^ other.exclude \
               or self.rating != other.rating \
               or self.duration != other.duration

    def copy(self):
        """shallow copy"""
        dup = RulesParam()
        for attr in self.attrs:
            setattr(dup, attr, getattr(self, attr).copy())
        return dup


class Rules:
    PLAY_QUEUE_DESIRED_LENGTH = MinMax(10, 500)
    PLAY_QUEUE_DESIRED_LENGTH_DEFAULT = 10
    # max_similair_artists = 20  not used

    def __init__(self, rules_dir: str, active_file: str, test_mode: bool):
        self.test_mode = test_mode
        self.dir = rules_dir
        self.similair_artists = SimilairArtists(rules_dir)
        self.active_file = active_file

        self.__initial_read = True
        self.__modified = False

        self.__param = [RulesParam()] * 2

        self.includeUnrated = False

        self.__rules_timestamp = 0
        self.__active_links_to = None

        self.playQueueDesiredLength = 10

    # how to do that in a loop?
    include = property(lambda self: getattr(self.__param[0], 'include'), lambda self, val: setattr(self.__param[0], 'include', val))
    exclude = property(lambda self: getattr(self.__param[0], 'exclude'), lambda self, val: setattr(self.__param[0], 'exclude', val))
    rating = property(lambda self: getattr(self.__param[0], 'rating'), lambda self, val: setattr(self.__param[0], 'rating', val))
    duration = property(lambda self: getattr(self.__param[0], 'duration'), lambda self, val: setattr(self.__param[0], 'duration', val))

    @property
    def changed(self):
        return self.__modified

    def checkRulesChanged(self):
        """ Determine if rules file has been updated.
        :return:
        """
        if not self.__modified:
            self.__modified = (self.__param[0] != self.__param[1])
            print('rules modifed')

        if self.__modified:
            self.__param[1] = self.__param[0].copy()

    def saveRule(self, rule: str, dates: Sequence[str], artistList: Iterable[str], genreList: Iterable[str], ruleMatch, isInclude: bool, maxAge: int):
        """ Add a rule to the list of rules that will be used to query MPD
        :param rule:
        :param dates:
        :param artistList:
        :param genreList:
        :param ruleMatch:
        :param isInclude:
        :param maxAge:
        :return:
        """
        ref = self.include if isInclude else self.exclude

        # We iterate through the list of artists - so if this is empty, add a blank artist.
        # artistList will only be set if we have been told to find tracks by similar artists...
        if not artistList:
            artistList = [""]

        if not genreList:
            genreList = [""]

        for genre in genreList:
            for artist in artistList:
                ### gibt es gar nicht  ###  $line =~ s/\"//g;
                if len(dates) > 0:
                    # Create rule for each date (as MPDs search does not take ranges)
                    baseRule = rule
                    for date in dates:
                        text = f'{ruleMatch} {baseRule} Date "{date}"'
                        if artist:
                            text += f' Artist "{artist}"'
                        if genre:
                            text += f' Genre "{genre}"'
                        if isInclude and maxAge > 0:
                            text += f' modified-since {maxAge}'
                        ref.add(text)

                elif artist or genre or rule or (isInclude and maxAge > 0):
                    text = f"{ruleMatch} {rule}"
                    if artist:
                        text += f' Artist "{artist}"'
                    if genre != "":
                        text += f' Genre "{genre}"'
                    if maxAge > 0:
                        text += f" modified-since {maxAge}"
                    ref.add(text)

    @staticmethod
    def baseDir() -> str:
        if sys.platform.startswith("darwin"):
            #    # MacOSX
            return os.path.join(os.environ['HOME'], 'Library/Caches/cantata/cantata/dynamic')

        # Linux
        cacheDir = os.environ.get('XDG_CACHE_HOME')
        if not cacheDir:
            cacheDir = os.path.join(os.environ['HOME'], ".cache")

        cacheDir = os.path.join(cacheDir, 'cantata', 'dynamic')
        return cacheDir

    def readRules(self, query: Callable) -> Union[None, bool]:
        """
        Read rules from ~/.cache/cantata/dynamic/rules
        (or from ${filesDir}/rules in server mode)

        File format:

        Rating:<Range>
        Duration:<Range>
        Rule
        <Tag>:<Value>
        <Tag>:<Value>
        Rule

        e.g.

        Rating:1-5
        Duration:30-900
        Rule
        AlbumArtist:Various Artists
        Genre:Dance
        Rule
        AlbumArtist:Wibble
        Date:1980-1989
        Exact:false
        Exclude:true

        :param query:
        :return:
        """
        if self.active_file is None:
            self.active_file = os.path.join(self.baseDir(), "rules")

        if not os.path.exists(self.active_file):
            self.__modified = False
            return

        # Check if rules (well, the file it points to), has changed since the last read...
        currentActiveLink = os.path.abspath(self.active_file)
        fileTime = os.stat(currentActiveLink).st_mtime
        if not self.__initial_read and fileTime == self.__rules_timestamp and self.__active_links_to == currentActiveLink:
            # No change, so no need to read it again!
            self.__modified = False
            return

        self.__active_links_to = currentActiveLink
        self.__rules_timestamp = fileTime

        for i in range(10):
            if os.path.exists(self.active_file):
                with open(self.active_file, 'r', encoding='utf-8') as fileHandle:
                    lines = fileHandle.read().splitlines()

                ruleMatch: str = "find"
                currentRule: str = ""
                dates: List[int] = []
                similarArtists: Set[str] = set()
                isInclude: bool = True
                genres: List[str] = []
                maxAge: int = 0

                self.__param[0] = RulesParam()
                self.includeUnrated = False
                self.playQueueDesiredLength = self.PLAY_QUEUE_DESIRED_LENGTH_DEFAULT


                for line in lines:
                    line = line.rstrip()
                    if not line.startswith('#'):
                        key_val = line.split(':', 1)
                        if len(key_val) == 2:
                            key, val = key_val
                        else:
                            key, val = (line, "")

                        if key.startswith('Rule'):  # New rule...
                            if len(currentRule) > 1 or similarArtists or dates or genres:
                                self.saveRule(currentRule, dates, similarArtists, genres, ruleMatch, isInclude, maxAge)

                            ruleMatch = "find"
                            currentRule = ""
                            dates = []
                            similarArtists = set()
                            isInclude = True
                            genres = []


                        elif key.startswith('Rating'):
                            vals = val.split("-")
                            if len(vals) == 2:
                                self.rating = MinMax(*vals)

                                # Check id we have a rating range of 0..MAX - if so, then we need to include
                                # all songs => can't filter on rating. Issue #1334
                                if self.rating.min == 0 and self.rating.max == 10:
                                    self.rating.max = 0

                        elif key.startswith('IncludeUnrated'):
                            if val:
                                self.includeUnrated = (val == "true")

                        elif key.startswith('Duration'):
                            vals = val.split("-")
                            if len(vals) == 2:
                                self.duration = MinMax(*vals)

                        elif key.startswith('NumTracks'):
                            val = int(val)
                            if val in self.PLAY_QUEUE_DESIRED_LENGTH:
                                self.playQueueDesiredLength = val
                                if self.playQueueDesiredLength % 2 > 0:
                                    self.playQueueDesiredLength += 1

                        elif key.startswith('MaxAge'):
                            if val > 0:
                                maxAge = int(time.time()) - (val * 24 * 60 * 60)

                        else:
                            if key == "Date":
                                dateVals = val.split("-")
                                if len(dateVals) == 2:
                                    fromDate = int(dateVals[0])
                                    toDate = int(dateVals[1])
                                    if fromDate > toDate:  # Fix dates if from>to!!!
                                        tmp = fromDate
                                        fromDate = toDate
                                        toDate = tmp

                                    dates = list(range(fromDate, toDate + 1))
                                else:
                                    dates = [int(val)]

                            elif key == "Genre" and '*' in val:
                                # Wildcard genre - get list of genres from MPD, and find the ones that contain the genre string.
                                val = val.replace('*', '')
                                mpd_genres = query("list genre", 'Genre')

                                for genre in mpd_genres:
                                    if genre and genre.casefold().startswith(val.casefold()):
                                        genres.append(genre)

                                if not genres:
                                    # No genres matching pattern - add dummy genre, so that no tracks will be found
                                    genres.append("XXXXXXXX")

                            elif key in ("Artist", "Album", "AlbumArtist", "Composer", "Comment", "Title", "Genre", "File"):
                                currentRule = f'{currentRule} {key} "{val}"'

                            elif key == "SimilarArtists":
                                # Perform a last.fm query to find similar artists
                                artistSearchResults = self.similair_artists.query(val)
                                if len(artistSearchResults) > 1:
                                    # Get MPD artists...
                                    mpdResponse = set(query("list artist", 'Artist'))

                                    # mpdArtists = [artist for artist in mpdResponse if artist and artist != val]
                                    # mpdArtists = list(set(mpdArtists))

                                    # Now check which last.fm artists MPD actually has...
                                    stop = False
                                    for artist in artistSearchResults:
                                        for mpdArtist in mpdResponse:
                                            if mpdArtist and mpdArtist != val:
                                                if artist.casefold() == mpdArtist.casefold():
                                                    similarArtists.add(artist)
                                                    #~ if len(similarArtists) >= self.max_similair_artists:
                                                        #~ stop = True
                                                        #~ break
                                        #~ if stop: break

                                similarArtists.add(val)  # Add ourselves

                            elif key == "Exact" and val == "false":
                                ruleMatch = "search"

                            elif key == "Exclude" and val == "true":
                                isInclude = False

                if len(currentRule) > 1 or similarArtists or dates or genres:
                    self.saveRule(currentRule, dates, similarArtists, genres, ruleMatch, isInclude, maxAge)
                elif maxAge > 0 and not self.include:
                    # No include rules but have max-age, so create a rule
                    self.saveRule("", "", "", "", "find", True, maxAge)

                if self.test_mode:
                    print("INCLUDE--------------")
                    for rule in self.include:
                        print(rule)

                    print("EXCLUDE--------------")
                    for rule in self.exclude:
                        print(rule)

                    print("---------------------")
                    print(f"RATING: {self.rating.min} -> {self.rating.max}  (unrated:{self.includeUnrated})")
                    print(f"DURATION: {self.duration.min} -> {self.duration.max}")

                self.checkRulesChanged()
                return True

        self.checkRulesChanged()
        return False

if __name__ == "__main__":
    a = MinMax(1, 4)
    b = a.copy()
    b.min = 2
    print(a.min)
    print(b.min)

    a = RulesParam()
    a.duration = MinMax(2.0, 4.5)
    b = a.copy()
    b.duration = MinMax(3.0, 5.5)
    print(a.duration.min)
    print(b.duration.min)
