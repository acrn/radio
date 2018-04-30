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


day_names = {
    'none':     set(),
    'all':      set(range(7)),
    'weekdays': set(range(5)),
    'weekends': set(range(5,7)),
}
day_names_l = [
    'monday',
    'tuesday',
    'wednesday',
    'thursday',
    'friday',
    'saturday',
    'sunday',
    ]
day_names.update((v, {k}) for k, v in enumerate(day_names_l))
day_names.update((v, {k}) for k, v in enumerate(d + 's' for d in day_names_l))

def which_days(days=('all',), not_days=None):
    days_ = set()

    for day_name in days or []:
        days_ |= day_names[day_name]
    for day_name in not_days or []:
        days_ ^= day_names[day_name]

    return days_

class ScheduleEvent():

    def __init__(self, unit_name, hour, minute, is_on=False, days=[]):
        self.unit_name = unit_name

        # hour_and_minute = lambda s: tuple(int(x) for x in s.split(':'))
        # self.on = hour_and_minute(on)
        # self.off = hour_and_minute(off)
        self.hour = hour
        self.minute = minute
        self.is_on = is_on
        self.days = days


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

        events = {}
        hour_and_minute = lambda s: tuple(int(x) for x in s.split(':'))
        for unit_event in d['schedule']:
            unit_name = unit_event['unit']

            for event in unit_event.get('events', []):
                # def __init__(self, unit_name, on, off, days=('all',), not_days=None):
                days = event[True]  # 'on' in yml == True
                not_days = event.get('but_not_on', [])
                if type(days) == str:
                    days = [days]
                if type(not_days) == str:
                    not_days = [not_days]
                ons = event.get('turn_on', [])
                offs = event.get('turn_off', [])
                if type(ons) == str:
                    ons = [ons]
                if type(offs) == str:
                    offs = [offs]
                for day in which_days(days, not_days):
                    for on in ons:
                        hour, minute = hour_and_minute(on)
                        events[(day,hour,minute)] = (unit_name, 1)
                    for off in offs:
                        hour, minute = hour_and_minute(off)
                        events[(day,hour,minute)] = (unit_name, 0)

        self.events = events

        self.timestamp = datetime.datetime.now()


def read_config(filename):
    with open(filename) as f:
        config_file = yaml.load(f)
    return State(config_file)
