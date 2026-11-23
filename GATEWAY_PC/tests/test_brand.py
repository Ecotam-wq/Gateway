"""Identidade CANIDÉ: arquivos oficiais do kit servidos pelo gateway e usados nas páginas."""
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
import http.server
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ecotam_gateway as gateway

ROOT = Path(__file__).resolve().parents[1]
PAGES = ('dashboard.html', 'historico.html', 'qualidade.html')
OFFICIAL = ('#0367A6', '#04ADBF', '#5F7009', '#F29F05', '#F28705')


class BrandAssetRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), gateway.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def fetch(self, path):
        with urllib.request.urlopen(self.base + path) as res:
            return res.status, res.headers.get('Content-Type'), res.read()

    def test_serves_official_files_unchanged(self):
        for rel, ctype in (('logos/01-principal-horizontal.svg', 'image/svg+xml'),
                           ('logos/03-negativa-branca.svg', 'image/svg+xml'),
                           ('logos/05-simbolo.svg', 'image/svg+xml'),
                           ('icons/favicon.ico', 'image/x-icon'),
                           ('icons/07-avatar.png', 'image/png'),
                           ('fonts/OpenSans-Regular.woff', 'font/woff')):
            status, got_type, body = self.fetch('/assets/brand/' + rel)
            self.assertEqual(status, 200, rel)
            self.assertEqual(got_type, ctype, rel)
            self.assertEqual(body, (ROOT / 'assets' / 'brand' / rel).read_bytes(), rel)

    def test_query_string_is_ignored(self):
        status, _, _ = self.fetch('/assets/brand/icons/08-favicon.svg?v=1')
        self.assertEqual(status, 200)

    def test_rejects_traversal_and_unknown_types(self):
        for path in ('/assets/brand/../ecotam_gateway.py',
                     '/assets/brand/%2e%2e/ecotam_gateway.py',
                     '/assets/brand/fonts/licenca-open-sans.txt',
                     '/assets/brand/logos/nao-existe.svg',
                     '/assets/brand/'):
            with self.assertRaises(urllib.error.HTTPError, msg=path) as ctx:
                self.fetch(path)
            self.assertEqual(ctx.exception.code, 404, path)


class BrandUsageTests(unittest.TestCase):
    def test_pages_use_official_favicon_and_fonts(self):
        css = (ROOT / 'dashboard.css').read_text(encoding='utf-8')
        for font in ('OpenSans-Regular.woff', 'OpenSans-Bold.woff', 'NotoSerif-Regular.woff'):
            self.assertIn(f'/assets/brand/fonts/{font}', css)
        for page in PAGES:
            html = (ROOT / page).read_text(encoding='utf-8')
            self.assertIn('/assets/brand/icons/08-favicon.svg', html, page)
            self.assertIn('/assets/brand/icons/favicon.ico', html, page)

    def test_referenced_brand_files_exist(self):
        import re
        sources = ''.join((ROOT / f).read_text(encoding='utf-8')
                          for f in PAGES + ('dashboard.css', 'dashboard.js'))
        refs = set(re.findall(r'/assets/brand/([\w/-]+\.(?:svg|png|ico|woff))', sources))
        # dashboard.js monta o caminho a partir de BRAND_FILE (relativo a /assets/brand/).
        refs |= set(re.findall(r"'((?:logos|icons|patterns|fonts)/[\w.-]+)'", sources))
        self.assertTrue(refs)
        for rel in refs:
            self.assertTrue((ROOT / 'assets' / 'brand' / rel).is_file(), rel)

    def test_improvised_arara_and_off_palette_brand_colors_removed(self):
        sources = ''.join((ROOT / f).read_text(encoding='utf-8')
                          for f in PAGES + ('dashboard.css', 'dashboard.js'))
        for old in ('#024E7F', '#035C94', '#1B83C4', '#95A94F', '#0B2A40', '#061420',
                    '#61B2F6', '#43CCDE', '#A2B65C', 'data:image/svg+xml'):
            self.assertNotIn(old.lower(), sources.lower(), old)

    def test_css_declares_official_palette(self):
        css = (ROOT / 'dashboard.css').read_text(encoding='utf-8')
        for color in OFFICIAL:
            self.assertIn(color, css)


if __name__ == '__main__':
    unittest.main()
