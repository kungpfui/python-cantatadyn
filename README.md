# python-cantatadyn
=================
A Python port of Cantata's dynamic playlist Perl hack-implementation


## Intention
 noticed one day that Cantata's graphical client for MPD has a feature
 called *dynamic playlist*. The dynamic playlist is implemented as a
Unix daemon that is written in Perl.

My Rasperry Pi based music player had no Perl packages installed.
Ok, that's not really a problem, but I was curious. Normally it is
not so difficult to port Perl to Python (which is installed).
So I started porting the code, fixing some bugs and, I'm sure,
adding new ones.

However 51 kB of Perl code is a lot and I removed some features like
- daemonizing - systemd does that job as well
- dbus support, IP (=ServerMode) does the same job as well

but fixed some bugs and added retries on connection problems


## Requirements
- [Python] >=3.7 needed
- [systemd] not needed but recommended
- [MPD - Music Player Deamon](https://github.com/MusicPlayerDaemon/MPD) needed
- [Cantata](https://raw.githubu.com/CDrummond/cantata) needed


## Usage
Install the package
 >sudo python3 setup.py install

 Edit connection informations
 >sudo nano /etc/opt/cantatadyn.conf

 Start the service
 >sudo nano systemctl start cantatadyn.service


## TODO
- there are no unittests
- Only "Server/IP Mode" - Cantata and MPD on the same machine has never been
  tested by me. So I have no idea if dbus works or not.
-
