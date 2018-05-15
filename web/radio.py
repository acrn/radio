import datetime
import json
import os
import re
import subprocess

import flask
import jinja2
import yaml


application = flask.Flask(__name__)

CONFIG_FILE='../config/config.yml'
_cached_config = None

strip_whitespace = lambda t: re.sub('^ *', '', t, flags=re.MULTILINE)

MAINPAGE_TEMPLATE = jinja2.Template(strip_whitespace('''\
  <!doctype html>
  <html>
    <head>
      <title>Switches</title>
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <script src="/static/js.js"></script>
      <link rel="stylesheet" type="text/css" href="/static/css.css"/>
      <link rel="shortcut icon" type="image/png" href="/static/bulb_on_24.png"/>
    </head>
    <body>
      <div id="app-container">
        <h1>
          Switches
        </h1>
        <table>
          {% for name, unit in units.items() %}
            <tr>
              <td>
                <p>
                  {{unit.label}}
                </p>
              </td>
              <td>
                <button class="on-button" type="button" onclick="send('{{name}}', 'on');">
                  <img src="/static/bulb_on_24.png">
                </button>
              </td>
              <td>
                <button class="off-button" type="button" onclick="send('{{name}}', 'off');">
                  <img src="/static/bulb_on_24.png">
                </button>
              </td>
            </tr>
          {% endfor %}
        </table>
        <a href="/config">
          Edit configuration file
        </a>
      </div>
    </body>
  </html>'''))

CONFIG_TEMPLATE = jinja2.Template(strip_whitespace('''\
  <!doctype html>
  <html>
    <head>
      <title>Config</title>
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <script src="/static/js.js"></script>
      <link rel="stylesheet" type="text/css" href="/static/css.css"/>
      <link rel="shortcut icon" type="image/png" href="/static/bulb16.png"/>
    </head>
    <body>
      <div id="app-container">
        <h1>Config</h1>
        <textarea id="configArea" rows="40" cols="80">{{raw}}</textarea>
        <br>
        <button type="button" onclick="saveConfig();">
          Save
        </button>
      </div>
    </body>
  </html>'''))


def get_config():
    global _cached_config
    now = datetime.datetime.now()
    if _cached_config and (_cached_config['timestamp'] > os.stat(CONFIG_FILE).st_mtime):
        return _cached_config
    with open(CONFIG_FILE) as f:
        raw = f.read()
    config = yaml.load(raw)
    for name, unit in config['units'].items():
        unit['label'] = unit.get('label', name)
    timestamp = now.timestamp()
    _cached_config = config = dict(config, timestamp=timestamp, raw=raw)
    return config


@application.route('/')
def mainpage():

    return MAINPAGE_TEMPLATE.render(get_config())


@application.route('/nexa/<unit>/<state>', methods=('POST',))
def nexa(unit, state):

    config = get_config()
    remotes = config['remotes']
    units = config['units']
    protocol = config['protocol']
    on_code, off_code = protocol['on_code'], protocol['off_code']

    unit = units[unit]
    remote = remotes[unit['remote']]
    unit_code = protocol['unit_codes'][unit['i']]
    state_code = {
        '1':   on_code,
        'on':  on_code,
        '0':   off_code,
        'off': off_code,
        }[state]

    code = remote | unit_code | state_code
    call = [
        'sudo',
        config['executable'],
        'nexa',
        hex(code)]
    output = subprocess.check_output(call)
    return json.dumps({
        'code': hex(code),
        'call': call,
        'output': output.decode('utf-8'),
        })


@application.route('/config', methods=('GET',))
def config_get():

    return CONFIG_TEMPLATE.render(get_config())


@application.route('/config', methods=('POST',))
def config_post():

    new_config = flask.request.data
    try:
        yaml.load(new_config)
        with open(CONFIG_FILE, 'wb') as f:
            f.write(new_config)
    except yaml.scanner.ScannerError as ex:
        return application.make_response((str(ex), 500))
    return json.dumps({'config': 'saved'})
