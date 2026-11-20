import datetime as dt
import http.server
import json
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ecotam_quality as quality
import ecotam_gateway as gateway
import ecotam_history as history

NOW = dt.datetime(2026, 11, 14, 21, 0, tzinfo=dt.timezone.utc)
BASE = {'source': 'sim', 'device': 'pc_simulator', 'session_id': 'session-one',
        'session_key': 'tag:sim:pc_simulator:session-one'}


def row(s, seq, **changes):
    result = {**BASE, 'time': f'2026-11-14T20:00:{s:02d}.000Z', 'sequence': float(seq),
              'altitude_m': 11.0, 'pressure_pa': 101325.0, 'temperature_c': 24.0,
              'battery_v': 12.0, 'accel_x': 0.2, 'accel_y': 0.3, 'accel_z': 9.81,
              'gyro_x': 0.1, 'gyro_y': 0.2, 'gyro_z': 0.3}
    result.update(changes)
    return result


def analysis(points):
    _, sessions = history.assign_sessions(points, 1)
    return quality.analyze_rows(points, sessions, now=NOW)


class FakeQueryServer(http.server.BaseHTTPRequestHandler):
    last_body = ''
    last_path = ''
    last_auth = ''
    content = ''

    def log_message(self, *args):
        pass

    def do_POST(self):
        cls = self.__class__
        cls.last_path = self.path
        cls.last_auth = self.headers.get('Authorization')
        cls.last_body = self.rfile.read(int(self.headers['Content-Length'])).decode()
        blob = cls.content.encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/csv')
        self.send_header('Content-Length', str(len(blob)))
        self.end_headers()
        self.wfile.write(blob)


EXAMPLE_CSV = '''#group,false,false,true,true,false,false,true,true,true,true
#datatype,string,long,dateTime:RFC3339,double,string,string,string,string,string
#default,_result,,,,,,,,
,result,table,_time,_value,_field,_measurement,device,source,session_id
,,0,2026-11-14T20:00:00Z,1,sequence,ecotam_telemetry,pc_simulator,sim,test-one
,,0,2026-11-14T20:00:01Z,2,sequence,ecotam_telemetry,pc_simulator,sim,test-one
,,1,2026-11-14T20:00:00Z,101325,pressure_pa,ecotam_telemetry,pc_simulator,sim,test-one
,,1,2026-11-14T20:00:01Z,101320,pressure_pa,ecotam_telemetry,pc_simulator,sim,test-one
'''


class QualityTests(unittest.TestCase):
    def test_no_issues_in_regular_series(self):
        result = analysis([row(0, 1), row(1, 2), row(2, 3)])
        self.assertEqual(result['samples'], 3)
        self.assertEqual(result['score_pct'], 100)
        self.assertEqual(result['gaps'], 0)
        self.assertEqual(result['events_total'], 0)

    def test_gap_and_sequence_jump_count_missing_once(self):
        result = analysis([row(0, 1), row(4, 5)])
        self.assertEqual(result['gaps'], 1)
        self.assertEqual(result['estimated_missing'], 3)
        self.assertEqual(result['missing_by_clock'], 3)
        self.assertEqual(result['missing_by_sequence'], 3)
        self.assertEqual(result['kinds']['salto_sequencia'], 1)

    def test_duplicate_sequence(self):
        result = analysis([row(0, 9), row(1, 9)])
        self.assertEqual(result['duplicates'], 1)
        self.assertEqual(result['bad_samples'], 1)

    def test_sequence_regression(self):
        result = analysis([row(0, 9), row(1, 4)])
        self.assertEqual(result['kinds']['sequencia_retrocesso'], 1)

    def test_missing_and_nonfinite_field(self):
        a = row(0, 1)
        del a['battery_v']
        b = row(1, 2, temperature_c=float('nan'))
        result = analysis([a, b])
        self.assertEqual(result['kinds']['campo_ausente'], 2)
        self.assertEqual(result['bad_samples'], 2)

    def test_unrealistic_pressure_is_not_falsely_called_hardware_failure(self):
        result = analysis([row(0, 1, pressure_pa=-5)])
        self.assertEqual(result['kinds']['faixa_basica'], 1)
        self.assertIn('integridade básica', result['events'][0]['detail'])

    def test_sessions_isolate_sequences(self):
        a, b = row(0, 100), row(1, 1)
        b['session_id'] = 'session-two'
        b['session_key'] = 'tag:sim:pc_simulator:session-two'
        result = analysis([a, b])
        self.assertEqual(result['events_total'], 0)

    def test_empty_results_have_no_score(self):
        result = quality.analyze_rows([], [], now=NOW)
        self.assertIsNone(result['score_pct'])
        self.assertEqual(result['last_status'], 'SEM DADOS')

    def test_no_aggregate_in_quality_flux(self):
        flux = quality.build_quality_flux('ecotam_telemetry', NOW - dt.timedelta(hours=1), NOW)
        self.assertNotIn('aggregateWindow', flux)
        self.assertIn('sequence', flux)
        self.assertNotIn('gps_simulated', flux)
        self.assertIn('keep(columns:', flux)

    def test_escaped_bucket(self):
        bucket = 'name" ) |> drop() //'
        self.assertIn(json.dumps(bucket), quality.build_quality_flux(bucket, NOW-dt.timedelta(hours=1), NOW))

    def test_query_api_mock(self):
        FakeQueryServer.content = EXAMPLE_CSV
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), FakeQueryServer)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            config = {'url': f'http://127.0.0.1:{server.server_port}', 'org': 'Ecotam',
                      'bucket': 'ecotam_telemetry', 'token': 'secret-testing-only'}
            result = quality.quality_result(config, {'period': '1h'})
            self.assertEqual(result['samples'], 2)
            self.assertEqual(result['sessions'][0]['approximate'], False)
            self.assertEqual(FakeQueryServer.last_auth, 'Token secret-testing-only')
            self.assertIn('org=Ecotam', FakeQueryServer.last_path)
            self.assertIn('from(bucket:', FakeQueryServer.last_body)
            self.assertNotIn('aggregateWindow', FakeQueryServer.last_body)
            self.assertNotIn('secret-testing-only', str(result))
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=2)

    def test_gateway_uses_quality_api_and_page(self):
        server = http.server.ThreadingHTTPServer(('127.0.0.1',0), gateway.Handler)
        th = threading.Thread(target=server.serve_forever, daemon=True); th.start()
        try:
            import urllib.request
            base = f'http://127.0.0.1:{server.server_port}'
            with urllib.request.urlopen(base+'/qualidade') as res:
                self.assertIn(b'Qualidade de dados', res.read())
            with urllib.request.urlopen(base+'/qualidade.js') as res:
                self.assertIn(b'/api/quality', res.read())
            req = urllib.request.Request(base+'/api/quality',
                                         data=b'{"period":"1h"}',
                                         headers={'Content-Type':'application/json'}, method='POST')
            with self.assertRaises(Exception) as raised:
                urllib.request.urlopen(req)
            self.assertEqual(raised.exception.code,400)
        finally:
            server.shutdown();server.server_close();th.join(timeout=2)


if __name__ == '__main__':
    unittest.main()
