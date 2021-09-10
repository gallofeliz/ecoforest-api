#!/usr/bin/env python

import requests, os, logging, socketserver, http.server, json
from retrying import retry
from base64 import b64encode

logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(message)s')

ecoforest_url=os.environ['ECOFOREST_URL']
ecoforest_authbasic = b64encode((os.environ['ECOFOREST_USERNAME'] + ':' + os.environ['ECOFOREST_PASSWORD']).encode('ascii')).decode('ascii') if os.environ.get('ECOFOREST_USERNAME') else None

@retry(stop_max_delay=10000)
def call_ecoforest():
    response = requests.post(
        ecoforest_url + '/recepcion_datos_4.cgi',
        data={'idOperacion': '1002'},
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
        key, value = line.split('=')
        data[key] = value

    return data

def get_status():
    data = call_ecoforest()

    return {
        'temperature': float(data['temperatura']),
        'power': int(data['consigna_potencia']),
        'status': int(data['estado'])
    }

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):

        if (self.path == '/favicon.ico'):
            print('Skipped')
            return

        if (self.path.split('?')[0] != '/status'):
            self.send_response(404)
            self.end_headers()
            return

        try:
            data = get_status()
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
