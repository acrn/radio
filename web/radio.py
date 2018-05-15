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

strip_whitespace = lambda t: re.sub('^ *', '', t, flags=re.MULTILINE)

MAINPAGE_TEMPLATE = jinja2.Template(strip_whitespace('''\
  <!doctype html>
  <html>
    <head>
      <title>Switches</title>
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <script src="/static/js.js"></script>
      <link rel="stylesheet" type="text/css" href="/static/css.css"/>
      <link rel="shortcut icon" type="image/png" href="/static/bulb16.png"/>
    </head>
    <body>
      <div id="app-container">
        <table>
          {% for name, unit in units.items() %}
            <tr>
              <td>
                <button class="on-button" type="button" onclick="send('{{name}}', 'on');">
                  <img src="/static/sun.png" height="42" width="42">
                </button>
              </td>
              <td>
                <p>
                  {{unit.label}}
                </p>
              </td>
              <td>
                <button class="off-button" type="button" onclick="send('{{name}}', 'off');">
                  <img src="/static/moon.png" height="42" width="42">
                </button>
              </td>
            </tr>
          {% endfor %}
        </table>
        <div id="cog-div">
          <a href="/config">&#x2699;</a>
        </div>
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
    try:
        cached_config = application.cached_radio_config
        if cached_config['timestamp'] > os.stat(CONFIG_FILE).st_mtime:
            return cached_config
    except AttributeError:
        pass
    timestamp = datetime.datetime.now().timestamp()
    with open(CONFIG_FILE) as file_:
        raw = file_.read()
    config = yaml.load(raw)
    remotes = config['remotes']
    protocol = config['protocol']
    for name, unit in config['units'].items():
        unit['label'] = unit.get('label', name)
        unit_code = protocol['unit_codes'][unit['i']]
        remote = remotes[unit['remote']]
        unit['on_code'] =  remote | unit_code | protocol['on_code']
        unit['off_code'] = remote | unit_code | protocol['off_code']
    application.cached_radio_config = config = dict(config,
                                                    timestamp=timestamp,
                                                    raw=raw)
    return config


@application.route('/')
def mainpage():

    return MAINPAGE_TEMPLATE.render(get_config())


@application.route('/nexa/<unit>/<state>', methods=('POST',))
def nexa(unit, state):

    config = get_config()
    unit = config['units'][unit]
    on_code =  unit['on_code']
    off_code = unit['off_code']
    code = {
        '1':   on_code,
        'on':  on_code,
        '0':   off_code,
        'off': off_code,
        }[state]
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
        with open(CONFIG_FILE, 'wb') as file_:
            file_.write(new_config)
    except yaml.scanner.ScannerError as ex:
        return application.make_response((str(ex), 500))
    return json.dumps({'config': 'saved'})

application.warmup = get_config
