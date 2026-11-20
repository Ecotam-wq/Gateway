import datetime as dt
import json
import http.server
import threading
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ecotam_history as history


CSV_SAMPLE = '''#group,false,false,true,true,false,false,true,true,true
#datatype,string,long,dateTime:RFC3339,double,string,string,string,string
#default,_result,,,,,,,
,result,table,_time,_value,_field,_measurement,device,source
,,0,2026-11-14T20:42:30Z,12.3,altitude_m,ecotam_telemetry,pc_simulator,sim
,,0,2026-11-14T20:42:40Z,12.4,altitude_m,ecotam_telemetry,pc_simulator,sim

#group,false,false,true,true,false,false,true,true,true
#datatype,string,long,dateTime:RFC3339,double,string,string,string,string
#default,_result,,,,,,,
,result,table,_time,_value,_field,_measurement,device,source
,,1,2026-11-14T20:42:30Z,101200,pressure_pa,ecotam_telemetry,pc_simulator,sim
,,1,2026-11-14T20:42:40Z,101190,pressure_pa,ecotam_telemetry,pc_simulator,sim
,,1,2026-11-14T20:42:40Z,true,gps_simulated,ecotam_telemetry,pc_simulator,sim
'''


class QueryServer(http.server.BaseHTTPRequestHandler):
    seen = None

    def log_message(self, *args):
        pass

    def do_POST(self):
        self.__class__.seen = {'url': self.path, 'content_type': self.headers.get('Content-Type'),
                               'authorization': self.headers.get('Authorization'),
                               'body': self.rfile.read(int(self.headers['Content-Length'])).decode('utf-8')}
        data = CSV_SAMPLE.encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/csv')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class HistoryTests(unittest.TestCase):
    def test_sprint11_legacy_export_layout(self):
        # Same annotated-CSV format as a Sprint 11 Flux/Data Explorer export.
        rows = history.parse_annotated_csv(CSV_SAMPLE)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r['source'] == 'sim' for r in rows))
        self.assertTrue(all(not r['session_id'] for r in rows))

    def test_annotated_csv_merges_fields_without_booleans(self):
        rows = history.parse_annotated_csv(CSV_SAMPLE)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['altitude_m'], 12.3)
        self.assertEqual(rows[0]['pressure_pa'], 101200)
        self.assertEqual(rows[1]['pressure_pa'], 101190)
        self.assertNotIn('gps_simulated', rows[1])

    def test_legacy_sessions_split_on_gap_and_reset(self):
        points = [
            {'time':'2026-11-14T20:00:00Z', 'source':'sim', 'device':'pc_simulator','session_id':'','sequence':1.0},
            {'time':'2026-11-14T20:00:10Z', 'source':'sim', 'device':'pc_simulator','session_id':'','sequence':2.0},
            {'time':'2026-11-14T20:04:00Z', 'source':'sim', 'device':'pc_simulator','session_id':'','sequence':1.0},
        ]
        result, sessions = history.assign_sessions(points, 10)
        self.assertEqual(len(sessions),2)
        self.assertNotEqual(result[0]['session_key'], result[2]['session_key'])
        self.assertTrue(all(s['approximate'] for s in sessions))

    def test_persisted_session_tags_take_priority(self):
        points = [
            {'time':'2026-11-14T20:00:00Z', 'source':'sim', 'device':'pc_simulator', 'session_id':'id_111'},
            {'time':'2026-11-14T20:20:00Z', 'source':'sim', 'device':'pc_simulator', 'session_id':'id_111'},
        ]
        result, sessions=history.assign_sessions(points, 5)
        self.assertEqual(len(sessions),1)
        self.assertEqual(result[0]['session_key'],'tag:sim:pc_simulator:id_111')
        self.assertFalse(sessions[0]['approximate'])

    def test_period_validation_and_field_filter(self):
        with self.assertRaises(ValueError):history.select_range({'period':'100y'})
        with self.assertRaises(ValueError):history.select_range({'period':'custom','start':'2026-01-01T00:00:00Z','stop':'2026-03-01T00:00:00Z'})
        now=dt.datetime(2026,11,14,21,tzinfo=dt.timezone.utc)
        a,b,every=history.select_range({'period':'24h'},now=now)
        flux=history.build_flux('ecotam_telemetry',a,b,every)
        self.assertIn('aggregateWindow',flux)
        self.assertIn('contains(value: r._field',flux)
        self.assertNotIn('gps_simulated',flux)
        self.assertIn('2026-11-13T21:00:00Z',flux)
        self.assertIn('"session_id"',flux)

    def test_flux_bucket_escaped(self):
        now=dt.datetime(2026,11,14,21,tzinfo=dt.timezone.utc)
        flux=history.build_flux('safe" ) |> drop() //',now-dt.timedelta(hours=1),now,10)
        self.assertIn(json.dumps('safe" ) |> drop() //'),flux)

    def test_query_endpoint_mock(self):
        server = http.server.ThreadingHTTPServer(('127.0.0.1',0),QueryServer)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            config={'url':f'http://127.0.0.1:{server.server_port}','org':'Ecotam','bucket':'ecotam_telemetry','token':'test-token'}
            now=dt.datetime(2026,11,14,21,tzinfo=dt.timezone.utc)
            rows,sessions=history.influx_history(config,now-dt.timedelta(hours=1),now,10)
            self.assertEqual(len(rows),2)
            self.assertEqual(len(sessions),1)
            self.assertEqual(QueryServer.seen['authorization'],'Token test-token')
            self.assertIn('org=Ecotam',QueryServer.seen['url'])
            self.assertEqual(QueryServer.seen['content_type'],'application/vnd.flux')
        finally:
            server.shutdown();server.server_close();thread.join(timeout=2)


if __name__ == '__main__':unittest.main()
