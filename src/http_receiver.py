"""
Server HTTP minimal pe Pi (port 5002) care primește date de la ESP8266/DHT11
și le pune într-un queue pentru producătorul Kafka.
"""
import queue
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import json

# Queue partajat cu producer.py
dht11_queue: queue.Queue = queue.Queue()

class _DHT11Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suprimă log-urile verbose ale HTTPServer
        logging.debug(f"[HTTP Receiver] {format % args}")

    def do_POST(self):
        if self.path != "/dht11":
            self.send_response(404)
            self.end_headers()
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            body   = self.rfile.read(length)
            data   = json.loads(body.decode("utf-8"))
            dht11_queue.put(data)
            logging.info(f"[DHT11 ESP] Primit: T={data.get('temperature')}°C H={data.get('humidity')}%")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        except Exception as e:
            logging.error(f"[DHT11 ESP] Eroare parsare: {e}")
            self.send_response(400)
            self.end_headers()

def start_http_receiver(port: int = 5002):
    """Pornește serverul HTTP în background (daemon thread)."""
    server = HTTPServer(("0.0.0.0", port), _DHT11Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True, name="http_receiver")
    t.start()
    logging.info(f"[HTTP Receiver] Ascultă pe portul {port} pentru date ESP8266")