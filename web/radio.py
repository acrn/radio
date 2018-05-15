import collections
import datetime
import json
import os
import re
import subprocess
import yaml


from flask import Flask, jsonify, request, Response

application = Flask(__name__)

CONFIG_FILE='/var/radio/config/config.yml'
_cached_config = None

strip_whitespace = lambda t: re.sub('^ *', '', t, flags=re.MULTILINE)

TEMPLATE = strip_whitespace('''\
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
          {0}
        </table>
        <a href="/config">
          Edit configuration file
        </a>
      </div>
    </body>
  </html>''')

CONFIG_TEMPLATE = strip_whitespace('''\
  <!doctype html>
  <html>
    <head>
      <script src="/static/js.js"></script>
      <link rel="stylesheet" href="/static/css.css">
    </head>
    <body>
      <h1>Config</h1>
      <textarea id="configArea" rows="40" cols="80">{0}</textarea>
      <br>
      <button type="button" onclick="saveConfig();">Save</button>
    </body>
  </html>''')


def get_config():
    global _cached_config
    now = datetime.datetime.now()
    if _cached_config and (_cached_config['timestamp'] > os.stat(CONFIG_FILE).st_mtime):
        return _cached_config
    with open(CONFIG_FILE) as f:
        raw = f.read()
    config = yaml.load(raw)
    timestamp = now.timestamp()
    _cached_config = config = dict(config, timestamp=timestamp, raw=raw)
    return config


def html(config):

    def tablerows(units):
        for k, v in sorted(units.items(), key=lambda k: k[1].get('label', k[0])):
            yield '''
              <tr>
                <td>{0}</td>
                <td>
                  <button class="on-button" type="button" onclick="send('{1}', 'on');">&#x1F31E</button>
                </td>
                <td>
                  <button class="off-button" type="button" onclick="send('{1}', 'off');">&#x1F31D</button>
                </td>
              </tr>'''.format(v.get('label', k), k)

    return TEMPLATE.format(
            '\n'.join(tablerows(config['units'])))

def html_config(config):

    return CONFIG_TEMPLATE.format(
            config['raw'])

@application.route('/')
def hello():

    return html(get_config())

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
def hello2():

    return html_config(get_config())


@application.route('/config', methods=('POST',))
def post_config():

    new_config = request.data
    try:
        yaml.load(new_config)
        with open(CONFIG_FILE, 'wb') as f:
            f.write(new_config);
    except yaml.scanner.ScannerError as ex:
        return application.make_response((str(ex), 500))
    return json.dumps({'config': 'saved'})
