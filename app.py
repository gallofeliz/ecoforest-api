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

    if (str(data['idOperacion']) == '1081'):
        return {}

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
        data[key.strip()] = value

    return data

def get_summary():
    data = call_ecoforest({'idOperacion': '1002'})
    data2 = call_ecoforest({'idOperacion': '1061'})

    co = float(data2['Co'])

    if co < 0:
        convectorSpeed = 'lowest'
    elif co > 0:
        convectorSpeed = 'highest'
    else:
        convectorSpeed = 'normal'

    mode = 'temperature' if  data['modo_operacion'] == '1' else 'power'
    return {
        'temperature': None if data['temperatura'] == '--.-' else float(data['temperatura']),
        'power': int(data['consigna_potencia']),
        'status': int(data['estado']),
        'humanStatus': status_to_str(int(data['estado'])),
        'mode': mode,
        'convector': convectorSpeed,
        **({ 'targetTemperature': float(data['consigna_temperatura']) } if mode == 'temperature' else { 'targetPower': int(data['consigna_potencia']) })
    }

def set_power(power):
    call_ecoforest({'idOperacion': '1004', 'potencia': str(power)})

def set_status(onoff):
    call_ecoforest({'idOperacion': '1013', 'on_off': str(onoff)})

def set_mode(mode):
    call_ecoforest({'idOperacion': '1081', 'modo_operacion': str(mode)})

def set_convector(mode):
    if mode == 'normal' or mode == '"normal"':
        value = 0
    elif mode == 'lowest' or mode == '"lowest"':
        value = -15
    elif mode == 'highest' or mode == '"highest"':
        value = 15
    else:
        value = float(mode)
    call_ecoforest({'idOperacion': '1054', 'delta_convector': str(value)})

class Handler(http.server.BaseHTTPRequestHandler):
    def do_PUT(self):
        path = self.path.split('?')[0]

        try:
            data = None
            if (path == '/super-mode'):
                target_scenario = self.rfile.read(int(self.headers['Content-Length'])).decode('utf8')

                if target_scenario == 'off':
                    set_status(0)
                else:
                    set_status(1)

                    if target_scenario[0:4] == 'temp':
                        raise Exception('Not handled tempX')

                    set_mode(0)
                    if target_scenario == 'soft1' or target_scenario == 'softest':
                        set_convector('lowest')
                        set_power(1)
                    if target_scenario == 'soft2' or target_scenario == 'soft':
                        set_convector('lowest')
                        set_power(2)
                    if target_scenario == 'soft3':
                        set_convector('lowest')
                        set_power(3)
                    if target_scenario == 'mid1':
                        set_convector('normal')
                        set_power(4)
                    if target_scenario == 'mid2' or target_scenario == 'mid' or target_scenario == 'midst':
                        set_convector('normal')
                        set_power(5)
                    if target_scenario == 'mid3':
                        set_convector('normal')
                        set_power(6)
                    if target_scenario == 'hard1':
                        set_convector('highest')
                        set_power(7)
                    if target_scenario == 'hard2' or target_scenario == 'hard':
                        set_convector('highest')
                        set_power(8)
                    if target_scenario == 'hard3' or target_scenario == 'hardest':
                        set_convector('highest')
                        set_power(9)

            elif (path == '/power'):
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
            elif (path == '/convector'):
                target_raw_mode = self.rfile.read(int(self.headers['Content-Length'])).decode('utf8')
                set_convector(target_raw_mode)
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
