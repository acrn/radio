#!/usr/bin/env python


import datetime
import yaml
import pytz
import collections


class Unit():

    def __init__(self, name, remote_code, i, protocol):
        self.name = name
        self.remote_code = remote_code
        self.i = i
        self.protocol = protocol

    def code(self, on=False):
        protocol = self.protocol
        return (self.remote_code |
                protocol.unit_codes[self.i - 1] |
                (protocol.on_code if on else protocol.off_code))

def weekday_filter(day, event):
    pass

class Schedule():

    def __init__(self, unit_name, on, off, days=('all',)):
        self.unit_name = unit_name

        hour_and_minute = lambda s: tuple(int(x) for x in s.split(':'))
        self.on = [hour_and_minute(x) for x in on]
        self.off = [hour_and_minute(x) for x in off]

        day_names = {
            'all':      list(range(7)),
            'weekdays': list(range(5)),
            'weekends': list(range(5,7)),
        }
        day_names.update((v, [k]) for k, v in enumerate([
            'monday',
            'tuesday',
            'wednesday',
            'thursday',
            'friday',
            'saturday',
            'sunday',
            ]))
        days_ = set()
        for day_name in days:
            days_.update(day_names[day_name])
        self.days = days_


class State():

    def __init__(self, d):
        self.remotes = remotes = d['remotes']
        self.timezone = pytz.timezone(d['timezone'])

        protocol = collections.namedtuple('Protocol', ['on_code', 'off_code', 'unit_codes'])
        p = d['protocol']
        protocol = self.protocol = protocol(p['on_code'], p['off_code'], p['unit_codes'])

        unit = collections.namedtuple('Unit', ['name', 'remote', 'remote_code', 'i'])
        units = {}
        for key, value in d['units'].items():
            remote = value['remote']
            units[key] = Unit(key,
                              remotes[remote-1],
                              value['i'],
                              protocol)
        self.units = units

        events = collections.defaultdict(list)

        for unit_event in d['schedule']:

            for on_events in unit_event[True]:
                pass
            for off_events in unit_event[True]:
                pass

        self.events = events

        # schedule:
          # - unit: bedroom_light
            # on:
              # - '07:00'
              # - '21:00'
            # off:
              # - '10:00'
              # - '22:00'
            # days: weekdays

        self.timestamp = datetime.datetime.now()


def read_config(filename):
    with open(filename) as f:
        config_file = yaml.load(f)
    return State(config_file)
