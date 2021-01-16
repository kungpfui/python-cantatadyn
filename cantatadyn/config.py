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


class Config:
	def __init__(self, filepath: str):
		self._dict = {}
		self.load(filepath)

	def load(self, filepath: str):
		""" Attempt to load a config file into self._dict """
		self.clear()
		try:
			with open(filepath, 'r', encoding='utf-8') as f:
				lines = f.read().splitlines()
		except IOError:
			raise Exception(f"Failed to load config {filepath}!")

		for line in lines:
			if not line.startswith('#'):
				if '=' in line:
					key, val = line.split('=', 1)
					key = key.strip()
					val = val.strip()
					try:
						val = int(val)
					except Exception:
						try:
							val = float(val)
						except Exception:
							pass
					self._dict[key] = val
					setattr(self, key, val)

	def __len__(self) -> int:
		return len(self._dict)

	def __getitem__(self, key: str):
		return self._dict[key]

	def __contains__(self, key: str) -> bool:
		return key in self._dict

	def clear(self) -> None:
		for key in self._dict:
			delattr(self, key)
		self._dict = {}

	def keys(self):
		return self._dict.keys()

	def values(self):
		return self._dict.values()

	def items(self):
		return self._dict.items()


if __name__ == "__main__":
	conf = Config('cantata-dynamic.conf')
	print(conf.keys())
	print(conf.values())
	print(conf.items())
	print(conf.filesDir)

