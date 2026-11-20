import http.server
import threading
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ecotam_gateway as gateway


class FakeInflux(http.server.BaseHTTPRequestHandler):
    received = []

    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
        else:
            self.send_response(404)
        self.end_headers()

    def do_POST(self):
        body = self.rfile.read(int(self.headers['Content-Length'])).decode()
        self.__class__.received.append((self.path, dict(self.headers), body))
        self.send_response(204)
        self.end_headers()


class GatewayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), FakeInflux)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def test_synthetic_sample_has_all_fields(self):
        sample = gateway.build_simulated_sample(42)
        for key in gateway.FIELDS[1:15]:
            self.assertIn(key, sample)
        self.assertTrue(sample['gps_simulated'])

    def test_rx_v2_serial_log_parser(self):
        p = gateway.RxLogParser()
        lines = [
            '[RX] OK seq=151 len=64 valid=6 | from 44:BD:8D:24:6F:04',
            '[RX] uptime=328063 ms | UTC=1793837016511 | GPS valid=1 synced=1',
            '[RX] altitude=75.50 m | pressure=100421.30 Pa | temp=24.51 C | battery=11.09 V',
            '[RX] accel=(-0.49 0.04 9.81) | gyro=(-0.97 -0.87 -0.48)',
        ]
        for line in lines[:-1]:
            self.assertIsNone(p.feed(line))
        out = p.feed(lines[-1])
        self.assertIsNotNone(out)
        self.assertEqual(out['sequence'], 151)
        self.assertEqual(out['altitude_m'], 75.5)
        self.assertEqual(out['accel_z'], 9.81)
        self.assertEqual(out['source'], 'rx_serial')

    def test_line_protocol_valid(self):
        sample = gateway.build_simulated_sample(4)
        sample['timestamp_ms'] = 1793837016511
        wire = gateway.line_protocol(sample)
        self.assertTrue(wire.startswith('ecotam_telemetry,device=pc_simulator,source=sim,session_id='))
        self.assertIn('sequence=4i', wire)
        self.assertIn('gps_simulated=true', wire)
        self.assertTrue(wire.endswith(' 1793837016511'))
        self.assertIn('altitude_m=', wire)

    def test_local_endpoint_url_only(self):
        self.assertEqual(gateway.normalize_influx_url(self.url), self.url)
        for bad in ('https://example.com:8086', 'http://example.com:8086',
                    'file:///etc/passwd', 'http://localhost:8086/path'):
            with self.assertRaises(ValueError):
                gateway.normalize_influx_url(bad)

    def test_influx_http_write(self):
        cfg = {'url': self.url, 'org': 'ECOTAM Lab', 'bucket': 'telemetry demo', 'token': 'dummy-local-token'}
        sample = gateway.build_simulated_sample(5)
        sample['timestamp_ms'] = 1793837016511
        status = gateway.influx_write(sample, cfg)
        self.assertEqual(status, 204)
        path, headers, body = FakeInflux.received[-1]
        self.assertIn('/api/v2/write?', path)
        self.assertIn('org=ECOTAM+Lab', path)
        self.assertIn('bucket=telemetry+demo', path)
        self.assertIn('precision=ms', path)
        self.assertEqual(headers['Authorization'], 'Token dummy-local-token')
        self.assertIn('altitude_m=', body)

    def test_config_connect_mock(self):
        result = gateway.configure_influx({'url': self.url, 'org': 'org', 'bucket': 'bucket', 'token': 'dummy'})
        self.assertIn('Configuração recebida', result['message'])
        s = gateway.snapshot()
        self.assertTrue(s['influx_configured'])
        self.assertNotIn('token', s)
        with gateway.STATE.lock:
            gateway.STATE.config = None


if __name__ == '__main__':
    unittest.main()
