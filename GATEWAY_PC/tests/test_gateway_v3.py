import math
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ecotam_gateway as gateway

class TestV3(unittest.TestCase):
    def test_rx_v3_sample(self):
        p=gateway.RxLogParser()
        lines=[
          '[RX] OK seq=201 len=84 valid=1 | from 00:00:00:00:00:00',
          '[RX] uptime=3000 ms | UTC=1795000000000 | GPS valid=1 synced=1',
          '[RX] altitude=1128.00 m | pressure=88490.00 Pa | temp=28.10 C | battery=0.00 V',
          '[RX] accel=(0.00 0.00 0.00) | gyro=(0.00 0.00 0.00)',
          '[RX] extras gps_fix=1 lat=-12.3456789 lon=-34.5678901 gps_alt=1195.90 satellites=10 humidity=61.46 humidity_valid=1 altitude_valid=1',
        ]
        for line in lines[:-1]: self.assertIsNone(p.feed(line))
        s=p.feed(lines[-1]); self.assertIsNotNone(s)
        self.assertEqual(s['protocol_version'],3)
        self.assertEqual(s['humidity_pct'],61.46)
        self.assertEqual(s['satellites'],10)
        self.assertEqual(s['latitude'],-12.3456789)
        self.assertFalse(s['gps_simulated'])
        s['timestamp_ms']=1795000000000
        wire=gateway.line_protocol(s)
        for fragment in ('latitude=', 'longitude=', 'humidity_pct=', 'gps_fix=true', 'protocol_version=3i', 'gps_simulated=false'):
          self.assertIn(fragment,wire)

    def test_no_fix_fields_not_present(self):
        p=gateway.RxLogParser()
        for line in [
          '[RX] OK seq=1 len=84 valid=1 | from 00:00:00:00:00:00',
          '[RX] altitude=5.00 m | pressure=100000.00 Pa | temp=20.00 C | battery=0.00 V',
          '[RX] accel=(0.00 0.00 0.00) | gyro=(0.00 0.00 0.00)',
        ]: self.assertIsNone(p.feed(line))
        s=p.feed('[RX] extras gps_fix=0 lat=0.0000000 lon=0.0000000 gps_alt=0.00 satellites=0 humidity=50.00 humidity_valid=1 altitude_valid=0')
        self.assertFalse(s['gps_fix'])
        self.assertNotIn('latitude',s)
        self.assertNotIn('gps_altitude_m',s)
        s['timestamp_ms']=1795000000000
        self.assertNotIn('latitude=',gateway.line_protocol(s))
        self.assertIn('humidity_pct=',gateway.line_protocol(s))

if __name__=='__main__': unittest.main()
