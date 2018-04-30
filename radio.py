#!/usr/bin/env python


import collections
import datetime
import os
import pytz
import subprocess
import sys
import time
import yaml


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
        hour_minute_and_second = lambda s: tuple(int(x) for x in (s+':00:00').split(':'))[:3]
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
                        hour, minute, second = hour_minute_and_second(on)
                        events[(day,hour,minute,second)].append((unit_name, 1))
                    for off in offs:
                        hour, minute, second = hour_minute_and_second(off)
                        events[(day,hour,minute,second)].append((unit_name, 0))

        self.events = dict(events)
        self.executable = d['executable']
        self.timestamp = datetime.datetime.now()


def read_config(filename):
    with open(filename) as f:
        config_file = yaml.load(f)
    return State(config_file)


def send(executable, code):
    output = subprocess.check_output([
        'echo',
        executable,
        'nexa',
        hex(code),
        ])
    return output


def daemonize(configfile, verbose=False):
    print('Starting main loop')
    state = read_config(configfile)
    while True:
        if os.stat(configfile).st_mtime > state.timestamp.timestamp():
            if verbose:
                print('Config file changed, rereading')
            try:
                state = read_config(configfile)
            except Exception as ex:
                print('Reading config failed')
                print(ex)
        now = datetime.datetime.now(state.timezone)
        key = (now.weekday(), now.hour, now.minute, now.second)
        events = state.events.get(key, [])
        if verbose:
            print('Events at {}: {}'.format(now.isoformat(), events))

        for unit_name, on in events:
            try:
                unit = state.units[unit_name]
                code = unit.code(on=on)
                output = send(state.executable, code)
                print(output)
            except Exception as ex:
                print('Event {}: {} failed'.format(unit_name, on))
                print(ex)
        sys.stdout.flush()
        now = datetime.datetime.now(state.timezone)
        if now.second == key[3]:
            time.sleep(1.001 - now.microsecond / 1000000.0)


def parse_args():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-D', '--daemonize', action='store_true')
    parser.add_argument('-c', '--configfile', default='config.yml')
    parser.add_argument('-v', '--verbose', action='store_true')
    parser.add_argument('unit_name', nargs='?')
    parser.add_argument('state', nargs='?')
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    if args.daemonize:
        daemonize(args.configfile, verbose=args.verbose)
    elif args.unit_name and args.state:
        config = read_config('config.yml')
        unit = config.units[args.unit_name]
        on = args.state in ['on', 1]
        code = unit.code(on=on)
        output = send(code)
        print(output)
