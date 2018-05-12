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

        Protocol = collections.namedtuple('Protocol', ['on_code', 'off_code', 'unit_codes'])
        p = d['protocol']
        protocol = self.protocol = Protocol(p['on_code'], p['off_code'], p['unit_codes'])

        units = {}
        for key, value in d['units'].items():
            remote = value['remote']
            units[key] = Unit(key,
                              remotes[remote-1],
                              value['i'],
                              protocol)
        self.units = units

        vacation = set()
        for vacation_row in d.get('vacation', []):
            if type(vacation_row) == datetime.date:
                vacation_row = [vacation_row, vacation_row]
            start, end = vacation_row
            for num in range((end - start).days + 1):
                date = start + datetime.timedelta(days=num)
                vacation.add((date.year, date.month, date.day))
        self.vacation = vacation

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
        'sudo',
        executable,
        'nexa',
        hex(code),
        ])
    return output


def daemonize(configfile, verbose=False):

    make_key = lambda d: (d.weekday(), d.hour, d.minute, d.second)
    state_info = lambda s: 'Read {} events for {} units'.format(
                            len(s.events),
                            len(s.units))

    state = read_config(configfile)
    last = datetime.datetime.now(state.timezone)
    interval = 5

    print(state_info(state))
    print('Starting main loop', flush=True)
    while True:
        now = datetime.datetime.now(state.timezone)
        if now.minute != last.minute:
            try:
                if os.stat(configfile).st_mtime > state.timestamp.timestamp():
                    print('Config file changed, rereading', flush=True)
                    state = read_config(configfile)
                    print(state_info(state), flush=True)
            except Exception as ex:
                print('Reading config failed')
                print(ex, flush=True)
        keys = (make_key(last + datetime.timedelta(seconds=x))
                for x in range((now - last).seconds))
        for key in keys:
            events = state.events.get(key)
            if not events:
                continue
            if (now.year, now.month, now.day) in state.vacation:
                print('Ignoring {} due to vacation'.format(events), flush=True)
                continue
            if verbose:
                print('Events at {}: {}'.format(now.isoformat(), events), flush=True)

            for unit_name, on in events:
                try:
                    unit = state.units[unit_name]
                    code = unit.code(on=on)
                    output = send(state.executable, code)
                    print('Event: {}:{}, output: {}'.format(unit_name, on, output), flush=True)
                except Exception as ex:
                    print('Event {}: {} failed'.format(unit_name, on))
                    print(ex, flush=True)
                time.sleep(0.3)
        last = now
        time.sleep(interval)


def disco(configfile, verbose=False):
    import random
    print('Starting main loop')
    state = read_config(configfile)
    unit_states = dict.fromkeys(state.units.keys(), False)
    while True:
        unit_name = random.choice(list(unit_states.keys()))
        unit_state = not unit_states[unit_name]
        try:
            unit = state.units[unit_name]
            code = unit.code(on=unit_state)
            output = send(state.executable, code)
            print(output)
        except Exception as ex:
            print('Event {}: {} failed'.format(unit_name, unit_state))
            print(ex)
        unit_states[unit_name] = unit_state
        time.sleep(1)


def parse_args():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-D', '--daemonize', action='store_true')
    parser.add_argument('-d', '--disco', action='store_true')
    parser.add_argument('-c', '--configfile', default='config.yml')
    parser.add_argument('-v', '--verbose', action='store_true')
    parser.add_argument('unit_name', nargs='?')
    parser.add_argument('state', nargs='?')
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    if args.daemonize:
        daemonize(args.configfile, verbose=args.verbose)
    elif args.disco:
        disco(args.configfile, verbose=args.verbose)
    elif args.unit_name and args.state:
        config = read_config('config.yml')
        unit = config.units[args.unit_name]
        on = args.state in ['on', 1]
        code = unit.code(on=on)
        output = send(config.executable, code)
        print(output)
