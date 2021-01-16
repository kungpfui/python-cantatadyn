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

import codecs


class CantataCodec(codecs.Codec):
    chr_repl_order = (
            ('"', '{q}'),
            ('{', '{ob}'),
            ('}', '{cb}'),
            ('\n', '{n}'),
            (':', '{c}'),
            )

    def encode(self, input, error='strict'):
        for a, b in self.chr_repl_order:
            input = input.replace(a, b)
        return (input, len(input))

    def decode(self, input, error='strict'):
        for b, a in reversed(self.chr_repl_order):
            input = input.replace(a, b)
        return (input, len(input))


def cantata_search_function(name):
    """
    Search function for teletex codec that is passed to codecs.register()
    """

    if name != 'cantata':
        return None

    return codecs.CodecInfo(
        name='cantata',
        encode=CantataCodec().encode,
        decode=CantataCodec().decode,
    )

#codecs.register(cantata_search_function)


if __name__ == "__main__":
	a = 'Helo{ab}:"hello":Blub'
	b = codecs.encode(a, 'cantata')
	c = codecs.decode(b, 'cantata')
	print(a)
	print(b)
	print(c)
