import sys
import re
import os

# Copy the exact minisoup and Node classes from default.py

class _Node(object):
    def __init__(self, tag, attrs):
        self.tag      = tag.lower() if tag else ''
        self.attrs    = dict(attrs or [])   # {name: value}
        self.children = []                  # list of _Node or str
        self.parent   = None

    def get(self, attr, default=''):
        return self.attrs.get(attr, default)

    def _classes(self):
        return self.attrs.get('class', '').split()

    def get_text(self, sep=' ', strip=True):
        parts = []
        self._collect_text(parts)
        text = sep.join(parts)
        return text.strip() if strip else text

    def _collect_text(self, buf):
        for child in self.children:
            if isinstance(child, str):
                t = child.strip()
                if t:
                    buf.append(t)
            else:
                child._collect_text(buf)

    def select(self, selector):
        results = []
        self._select(selector.strip(), results)
        return results

    def select_one(self, selector):
        r = self.select(selector)
        return r[0] if r else None

    def _select(self, selector, results):
        parts = _split_selector(selector)
        self._match_parts(parts, results, child_only=False)

    def _match_parts(self, parts, results, child_only):
        if not parts:
            return
        part, combinator, rest = parts[0], parts[1] if len(parts) > 1 else None, parts[2:]

        candidates = self.children if child_only else self._descendants()
        candidates = [c for c in candidates if isinstance(c, _Node)]

        for node in candidates:
            if _matches(node, part):
                if not combinator:
                    results.append(node)
                else:
                    node._match_parts(rest, results,
                                      child_only=(combinator == '>'))

    def _descendants(self):
        for child in self.children:
            if isinstance(child, _Node):
                yield child
                for d in child._descendants():
                    yield d

def _split_selector(selector):
    tokens = []
    for part in re.split(r'\s*(>)\s*|\s+', selector):
        if part:
            tokens.append(part)
    return tokens

def _matches(node, part):
    tag_match = re.match(r'^([a-zA-Z0-9_-]+)?', part)
    tag = tag_match.group(1) or '' if tag_match else ''
    if tag and node.tag != tag.lower():
        return False

    for cls in re.findall(r'\.([\w-]+)', part):
        if cls not in node._classes():
            return False

    id_m = re.search(r'#([\w-]+)', part)
    if id_m and node.attrs.get('id') != id_m.group(1):
        return False

    for attr_m in re.finditer(r'\[([^\]=]+)(?:=["\']?([^"\'=\]]*)["\']?)?\]', part):
        attr_name = attr_m.group(1).strip()
        attr_val  = attr_m.group(2)
        if attr_name not in node.attrs:
            return False
        if attr_val is not None and node.attrs[attr_name] != attr_val:
            return False

    return True

from html.parser import HTMLParser

class _SaxParser(HTMLParser):
    VOID = {'area','base','br','col','embed','hr','img','input',
            'link','meta','param','source','track','wbr'}

    def __init__(self):
        HTMLParser.__init__(self, convert_charrefs=True)
        self.root    = _Node('__root__', [])
        self._stack  = [self.root]

    def handle_starttag(self, tag, attrs):
        node = _Node(tag, attrs)
        node.parent = self._stack[-1]
        self._stack[-1].children.append(node)
        if tag.lower() not in self.VOID:
            self._stack.append(node)

    def handle_endtag(self, tag):
        for i in range(len(self._stack) - 1, 0, -1):
            if self._stack[i].tag == tag.lower():
                self._stack = self._stack[:i]
                break

    def handle_data(self, data):
        if data:
            self._stack[-1].children.append(data)

def minisoup(html):
    p = _SaxParser()
    p.feed(html)
    return p.root

# Load the saved HTML from the step
html_path = r"C:\Users\jaisimha.seelam\.gemini\antigravity-ide\brain\51e22581-287c-4e19-a197-db949013bc0c\.system_generated\steps\29\content.md"
with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

soup = minisoup(html)
cards = soup.select('div.boxed.film')
print(f"Total cards found: {len(cards)}")

for i, card in enumerate(cards):
    print(f"\n--- Card {i+1} ---")
    a_tag   = card.select_one('div.cont_display a')
    img_tag = card.select_one('div.cont_display img')
    p_tag   = card.select_one('p b') or card.select_one('p')
    print(f"a_tag: {a_tag}")
    print(f"img_tag: {img_tag}")
    print(f"p_tag: {p_tag}")
    if a_tag:
        title = (a_tag.get('title') or (p_tag.get_text(strip=True) if p_tag else '')).strip()
        href  = a_tag.get('href', '').strip()
        thumb = (img_tag.get('src', '') if img_tag else '').strip()
        print(f"Extracted Title: {title}")
        print(f"Extracted Href: {href}")
        print(f"Extracted Thumb: {thumb}")
    else:
        print("a_tag is None!")
