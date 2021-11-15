#!/usr/bin/env python

import requests, os, logging, socketserver, http.server, json
from retrying import retry
from base64 import b64encode

logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(message)s')

ecoforest_url=os.environ['ECOFOREST_URL']
ecoforest_authbasic = b64encode((os.environ['ECOFOREST_USERNAME'] + ':' + os.environ['ECOFOREST_PASSWORD']).encode('ascii')).decode('ascii') if os.environ.get('ECOFOREST_USERNAME') else None

def status_to_str(status):
    if status == 7:
        return 'running'
    if status == 0 or status == 1:
        return 'stopped'
    if status == 8 or status == -2 or status == 11 or status == 9:
        return 'stopping'
    if status < 0:
        return 'error'
    if status == 2 or status == 3 or status == 4 or status == 10:
        return 'starting'
    if status == 5 or status == 6:
        return 'running' # It's not fully starting because there is fire, but not fully running because there is no heat
    if status == 20:
        return 'standby'

    raise Exception('Unknown')

@retry(stop_max_delay=10000)
def call_ecoforest(data):
    response = requests.post(
        ecoforest_url + '/recepcion_datos_4.cgi',
        data=data,
        headers=(
            {'Authorization': 'Basic ' + ecoforest_authbasic}
            if ecoforest_authbasic else {}
        )
      )
    response.raise_for_status()

    lines = response.text.split('\n')

    code = lines.pop()

    if code != '0':
        raise Exception('Invalid code')

    data = {}

    for line in lines:
        if ('=' in line):
            key, value = line.split('=')
        else:
            key = line
            value = ''
        data[key] = value

    return data

def get_summary():
    data = call_ecoforest({'idOperacion': '1002'})
    mode = 'temperature' if  data['modo_operacion'] == '1' else 'power'
    return {
        'temperature': None if data['temperatura'] == '--.-' else float(data['temperatura']),
        'power': int(data['consigna_potencia']),
        'status': int(data['estado']),
        'humanStatus': status_to_str(int(data['estado'])),
        'mode': mode,
        **({ 'targetTemperature': float(data['consigna_temperatura']) } if mode == 'temperature' else { 'targetPower': int(data['consigna_potencia']) })
    }

def set_power(power):
    call_ecoforest({'idOperacion': '1004', 'potencia': str(temp)})

def set_status(onoff):
    call_ecoforest({'idOperacion': '1013', 'on_off': str(onoff)})

def set_mode(mode):
    call_ecoforest({'idOperacion': '1081', 'modo_operacion': str(mode)})

class Handler(http.server.BaseHTTPRequestHandler):
    def do_PUT(self):
        path = self.path.split('?')[0]

        try:
            data = None
            if (path == '/power'):
                target_power = self.rfile.read(int(self.headers['Content-Length'])).decode('utf8')
                set_power(target_power)
            elif (path == '/status'):
                target_raw_status = self.rfile.read(int(self.headers['Content-Length'])).decode('utf8')
                target_status = 0
                if (target_raw_status == '1' or target_raw_status == 'true' or target_raw_status.lower() == 'on' or target_raw_status.lower() == '"on"'):
                    target_status = 1

                set_status(target_status)
            elif (path == '/mode'):
                target_raw_mode = self.rfile.read(int(self.headers['Content-Length'])).decode('utf8')

                if (target_raw_mode == 'power'):
                    target_mode = 0
                elif (target_raw_mode == 'temperature'):
                    target_mode = 1
                else:
                    target_mode = int(target_raw_mode)

                set_mode(target_mode)
            else:
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header('Content-type','application/json')
            self.end_headers()
            self.wfile.write(bytes(json.dumps(data), 'utf8'))
        except Exception as inst:
            self.send_response(500)
            self.send_header('Content-type','text/html')
            self.end_headers()
            self.wfile.write(bytes(str(inst), 'utf8'))
            logging.exception('Request error')

    def do_GET(self):

        if (self.path == '/favicon.ico'):
            print('Skipped')
            return

        path = self.path.split('?')[0]

        try:
            data = None
            if (path == '/summary'):
                data = get_summary()
            else:
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header('Content-type','application/json')
            self.end_headers()
            self.wfile.write(bytes(json.dumps(data), 'utf8'))
        except Exception as inst:
            self.send_response(500)
            self.send_header('Content-type','text/html')
            self.end_headers()
            self.wfile.write(bytes(str(inst), 'utf8'))
            logging.exception('Request error')

port = int(os.environ.get('PORT', 80))
httpd = socketserver.TCPServer(('', port), Handler)
try:
   httpd.serve_forever()
except KeyboardInterrupt:
   pass
httpd.server_close()
