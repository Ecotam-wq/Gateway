import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ecotam_gateway as gateway

ROOT = Path(__file__).resolve().parents[1]

class TestFullDashboard(unittest.TestCase):
    def test_all_metrics_and_graphs(self):
        page = (ROOT / 'dashboard.html').read_text(encoding='utf-8')
        scripts = (ROOT / 'dashboard.js').read_text(encoding='utf-8')
        for metric in ('temperature','pressure','humidity','altitude','latitude',
                       'longitude','gps-altitude','satellites','fix','track'):
            self.assertIn(f'id="chart-{metric}"', page)
        for field in ('temperature_c','pressure_pa','humidity_pct','altitude_m',
                      'latitude','longitude','gps_altitude_m','satellites','gps_fix'):
            self.assertIn(field, scripts)

    def test_history_supports_new_fields(self):
        page = (ROOT / 'historico.html').read_text(encoding='utf-8')
        for field in ('latitude','longitude','humidity_pct','gps_altitude_m','satellites'):
            self.assertIn(f'value="{field}"', page)

    def test_status_exposes_240_samples(self):
        with gateway.STATE.lock:
            old_samples = list(gateway.STATE.samples)
            old_count = gateway.STATE.count
            try:
                gateway.STATE.samples.clear()
                for i in range(200):gateway.STATE.samples.append({'timestamp_ms':i,'source':'sim'})
                self.assertEqual(len(gateway.snapshot()['samples']),200)
            finally:
                gateway.STATE.samples.clear();gateway.STATE.samples.extend(old_samples)
                gateway.STATE.count = old_count

    def test_v3_missing_fields_not_fake(self):
        p=gateway.RxLogParser()
        for line in ('[RX] OK seq=22 len=84 valid=22 | from FF:FF:FF:FF:FF:FF',
                     '[RX] altitude=900.00 m | pressure=90800.00 Pa | temp=25.00 C | battery=0.00 V',
                     '[RX] accel=(0.00 0.00 0.00) | gyro=(0.00 0.00 0.00)'):
            self.assertIsNone(p.feed(line))
        r=p.feed('[RX] extras gps_fix=0 lat=0.0000000 lon=0.0000000 gps_alt=0.00 satellites=0 humidity=0.00 humidity_valid=0 altitude_valid=0')
        self.assertIsNotNone(r)
        self.assertFalse(r['gps_fix'])
        self.assertNotIn('latitude',r)
        self.assertNotIn('humidity_pct',r)
        self.assertNotIn('gps_altitude_m',r)

if __name__=='__main__': unittest.main()
