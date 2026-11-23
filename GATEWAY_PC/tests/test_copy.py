"""Linguagem da interface CANIDÉ: sem emoji, estrelas, travessões, reticências de três pontos ou exclamações.

O travessão sozinho ("—") continua permitido como marca de valor ausente num campo de dado:
é um sinal da tabela, não pontuação de texto.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES = ('dashboard.html', 'historico.html', 'qualidade.html')
SCRIPTS = ('dashboard.js', 'historico.js', 'qualidade.js')

EMOJI = re.compile('[\U0001F000-\U0001FAFF☀-➿⬀-⯿️]')
RULES = {
    'emoji': EMOJI,
    'estrela ou brilho': re.compile('[★☆✦-✰⭐✨]'),
    'travessão em texto': re.compile('[—–]'),
    'reticências com três pontos': re.compile(r'\.\.\.'),
    'exclamação': re.compile('!'),
    'seta decorativa': re.compile('[←-⇿]'),
}
STRING = re.compile(r"'((?:\\.|[^'\\\n])*)'|\"((?:\\.|[^\"\\\n])*)\"|`((?:\\.|[^`\\])*)`")


def strip_js_comments(source):
    out, i, n = [], 0, len(source)
    while i < n:
        c = source[i]
        if c in '\'"`':
            j = i + 1
            while j < n and source[j] != c:
                j += 2 if source[j] == '\\' else 1
            out.append(source[i:j + 1])
            i = j + 1
        elif source.startswith('//', i) and (i == 0 or source[i - 1] != ':'):
            j = source.find('\n', i)
            i = n if j < 0 else j
        elif source.startswith('/*', i):
            i = source.find('*/', i) + 2
        else:
            out.append(c)
            i += 1
    return ''.join(out)


def visible_texts():
    """Textos que chegam à tela: nós e atributos do HTML, strings com palavras nos scripts."""
    for name in PAGES:
        html = (ROOT / name).read_text(encoding='utf-8')
        html = re.sub(r'<!--.*?-->', '', html, flags=re.S)
        html = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html, flags=re.S)
        for m in re.finditer(r'>([^<>]+)<|(?:aria-label|title|placeholder|alt)="([^"]*)"', html):
            yield name, (m.group(1) or m.group(2) or '').strip()
    for name in SCRIPTS:
        js = strip_js_comments((ROOT / name).read_text(encoding='utf-8'))
        for m in STRING.finditer(js):
            text = next(g for g in m.groups() if g is not None)
            if re.search(r'[A-Za-zÀ-ú]{2,}', text) or EMOJI.search(text):
                # Trechos de código dentro de template strings não são texto de interface.
                text = re.sub(r'\$\{[^}]*\}', '', text)
                text = re.sub(r'<[^>]+>', ' ', text)
                yield name, text.strip()


class CopyRulesTests(unittest.TestCase):
    def test_interface_text_follows_writing_rules(self):
        problems = []
        for name, text in visible_texts():
            if not text or text == '—':
                continue
            for rule, rx in RULES.items():
                if rx.search(text):
                    problems.append(f'{name}: {rule}: {text[:90]}')
        self.assertEqual(problems, [], '\n'.join(problems))

    def test_icons_share_one_stroke(self):
        sources = ''.join((ROOT / f).read_text(encoding='utf-8') for f in PAGES + SCRIPTS)
        widths = set(re.findall(r'<svg[^>]*stroke-width="([\d.]+)"', sources))
        self.assertEqual(widths, {'1.5'})


if __name__ == '__main__':
    unittest.main()
