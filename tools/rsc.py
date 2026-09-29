"""Helpers for editing the mirrored Next.js pages.

Each page carries its text twice: once in the server-rendered HTML and once in
the React Server Components payload (self.__next_f.push(...) scripts) that React
hydrates from. Both copies must change together or hydration restores the old
text, so every edit goes through Page, which exposes the markup and the decoded
payload separately and re-encodes the payload exactly as Next.js does.
"""
import json
import re

PUSH = re.compile(r'(<script>self\.__next_f\.push\()(\[.*?\])(\)</script>)', re.S)


def encode_push(arr):
    s = json.dumps(arr, ensure_ascii=False, separators=(',', ':'))
    return (s.replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
             .replace('\u2028', '\\u2028').replace('\u2029', '\\u2029'))


class Page:
    def __init__(self, path):
        self.path = path
        html = open(path, encoding='utf-8').read()
        self.parts = []  # alternating markup strings and decoded push arrays
        pos = 0
        for m in PUSH.finditer(html):
            self.parts.append(html[pos:m.start(2)])
            arr = json.loads(m.group(2))
            assert encode_push(arr) == m.group(2), f'{path}: payload does not round-trip'
            self.parts.append(arr)
            pos = m.end(2)
        self.parts.append(html[pos:])

    # markup = everything outside the payload scripts
    @property
    def markup_idx(self):
        return [i for i, p in enumerate(self.parts) if isinstance(p, str)]

    @property
    def payload_idx(self):
        return [i for i, p in enumerate(self.parts) if isinstance(p, list) and len(p) > 1 and isinstance(p[1], str)]

    def sub_markup(self, fn):
        for i in self.markup_idx:
            self.parts[i] = fn(self.parts[i])

    def sub_payload(self, fn):
        for i in self.payload_idx:
            self.parts[i][1] = fn(self.parts[i][1])

    def count(self, s):
        m = sum(self.parts[i].count(s) for i in self.markup_idx)
        p = sum(self.parts[i][1].count(s) for i in self.payload_idx)
        return m, p

    def save(self):
        out = ''.join(p if isinstance(p, str) else encode_push(p) for p in self.parts)
        open(self.path, 'w', encoding='utf-8').write(out)
