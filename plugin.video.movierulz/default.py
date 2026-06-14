"""
MovieRulz Kodi Addon — default.py
────────────────────────────────────────────────────────────────────────────────
Zero external dependencies.  Uses only Python stdlib:
  • urllib / urllib2  →  HTTP fetching
  • html.parser       →  HTML parsing  (MiniSoup — lightweight wrapper below)
  • re                →  regex helpers
────────────────────────────────────────────────────────────────────────────────
"""

import sys
import re
import os
import ssl

try:
    from urllib.parse import urlencode, parse_qsl, quote_plus, unquote_plus
    from urllib.request import Request, urlopen
    from urllib.error import URLError
except ImportError:
    from urlparse import parse_qsl
    from urllib import urlencode, quote_plus, unquote_plus
    from urllib2 import Request, urlopen, URLError

try:
    from html.parser import HTMLParser
except ImportError:
    from HTMLParser import HTMLParser

import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon

# ─── Addon globals ────────────────────────────────────────────────────────────
_ADDON    = xbmcaddon.Addon()
_URL      = sys.argv[0]
_HANDLE   = int(sys.argv[1])
_BASE_URL = _ADDON.getSetting('base_url')

# Auto-migrate from the legacy broken domain to the new working one
if not _BASE_URL or '5movierulz.discount' in _BASE_URL:
    _BASE_URL = 'https://www.5movierulz.school'
    try:
        _ADDON.setSetting('base_url', _BASE_URL)
    except Exception:
        pass


_HEADERS = [
    ('User-Agent',
     'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
     'AppleWebKit/537.36 (KHTML, like Gecko) '
     'Chrome/124.0.0.0 Safari/537.36'),
    ('Accept',
     'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'),
    ('Accept-Language', 'en-US,en;q=0.5'),
    ('Referer', _BASE_URL),
]


# ══════════════════════════════════════════════════════════════════════════════
#  MiniSoup — a lightweight HTML parser built on Python's stdlib html.parser
#  Supports: select(css), select_one(css), get_text(), get(attr)
# ══════════════════════════════════════════════════════════════════════════════

class _Node(object):
    """Represents a single HTML element node."""

    def __init__(self, tag, attrs):
        self.tag      = tag.lower() if tag else ''
        self.attrs    = dict(attrs or [])   # {name: value}
        self.children = []                  # list of _Node or str
        self.parent   = None
        self._text_cache = None

    # ── attribute helpers ──

    def get(self, attr, default=''):
        return self.attrs.get(attr, default)

    def _classes(self):
        return self.attrs.get('class', '').split()

    # ── text extraction ──

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

    # ── CSS selector (subset: tag, .class, #id, tag.class, [attr], combinator space/>) ──

    def select(self, selector):
        results = []
        self._select(selector.strip(), results)
        return results

    def select_one(self, selector):
        r = self.select(selector)
        return r[0] if r else None

    def _select(self, selector, results):
        """Multi-part selector split by spaces (descendant) or > (child)."""
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
    """Split 'div.foo > span.bar a' into ['div.foo', '>', 'span.bar', ' ', 'a']."""
    s = re.sub(r'\s+', ' ', selector.strip())
    s = re.sub(r'\s*>\s*', ' > ', s)
    raw_tokens = s.split(' ')
    tokens = []
    for t in raw_tokens:
        if t == '>':
            tokens.append('>')
        elif t == '':
            continue
        else:
            if tokens and tokens[-1] != '>' and tokens[-1] != ' ':
                tokens.append(' ')
            tokens.append(t)
    return tokens


def _matches(node, part):
    """Check whether *node* matches a simple selector part like 'div', '.foo', '#id', 'a.bar[href]'."""
    # Extract tag, classes, id, attribute filter
    tag_match = re.match(r'^([a-zA-Z0-9_-]+)?', part)
    tag = tag_match.group(1) or '' if tag_match else ''
    if tag and node.tag != tag.lower():
        return False

    # .class checks
    for cls in re.findall(r'\.([\w-]+)', part):
        if cls not in node._classes():
            return False

    # #id check
    id_m = re.search(r'#([\w-]+)', part)
    if id_m and node.attrs.get('id') != id_m.group(1):
        return False

    # [attr] / [attr=value] checks
    for attr_m in re.finditer(r'\[([^\]=]+)(?:=["\']?([^"\'=\]]*)["\']?)?\]', part):
        attr_name = attr_m.group(1).strip()
        attr_val  = attr_m.group(2)
        if attr_name not in node.attrs:
            return False
        if attr_val is not None and node.attrs[attr_name] != attr_val:
            return False

    return True


class _SaxParser(HTMLParser):
    """Builds a tree of _Node objects."""

    VOID = {'area','base','br','col','embed','hr','img','input',
            'link','meta','param','source','track','wbr'}

    def __init__(self):
        try:
            HTMLParser.__init__(self, convert_charrefs=True)
        except TypeError:
            HTMLParser.__init__(self)
        self.root    = _Node('__root__', [])
        self._stack  = [self.root]

    def handle_starttag(self, tag, attrs):
        node = _Node(tag, attrs)
        node.parent = self._stack[-1]
        self._stack[-1].children.append(node)
        if tag.lower() not in self.VOID:
            self._stack.append(node)

    def handle_endtag(self, tag):
        # pop back to the matching open tag
        for i in range(len(self._stack) - 1, 0, -1):
            if self._stack[i].tag == tag.lower():
                self._stack = self._stack[:i]
                break

    def handle_data(self, data):
        if data:
            self._stack[-1].children.append(data)

    def handle_entityref(self, name):
        pass  # convert_charrefs handles most; ignore rest

    def handle_charref(self, name):
        pass


def minisoup(html):
    """Parse *html* string and return the root _Node."""
    xbmc.log('[MovieRulz] minisoup parsing started for HTML length: %d' % len(html), xbmc.LOGDEBUG)
    p = _SaxParser()
    p.feed(html)
    xbmc.log('[MovieRulz] minisoup parsing completed.', xbmc.LOGDEBUG)
    return p.root


# ══════════════════════════════════════════════════════════════════════════════
#  HTTP helper
# ══════════════════════════════════════════════════════════════════════════════

def fetch(url):
    xbmc.log('[MovieRulz] Fetching URL: %s' % url, xbmc.LOGINFO)
    
    # Create unverified context to bypass certificate errors
    context = None
    try:
        context = ssl._create_unverified_context()
        xbmc.log('[MovieRulz] Created unverified SSL context successfully.', xbmc.LOGDEBUG)
    except Exception as ssl_exc:
        xbmc.log('[MovieRulz] Failed to create unverified SSL context: %s' % ssl_exc, xbmc.LOGDEBUG)

    try:
        req = Request(url)
        for k, v in _HEADERS:
            req.add_header(k, v)
        
        if context:
            resp = urlopen(req, context=context, timeout=20)
        else:
            resp = urlopen(req, timeout=20)
            
        with resp:
            raw = resp.read()
            
        xbmc.log('[MovieRulz] Successfully fetched %d bytes from %s' % (len(raw), url), xbmc.LOGINFO)
            
        # detect charset
        ct = ''
        try:
            ct = resp.headers.get('Content-Type', '')
        except Exception:
            pass
        m = re.search(r'charset=([^\s;]+)', ct, re.I)
        charset = m.group(1) if m else 'utf-8'
        return raw.decode(charset, errors='replace')
        
    except Exception as exc:
        xbmc.log('[MovieRulz] Fetch error for %s: %s' % (url, exc), xbmc.LOGERROR)
        
        # If HTTPS failed, try falling back to HTTP
        if url.startswith('https://'):
            fallback_url = url.replace('https://', 'http://', 1)
            xbmc.log('[MovieRulz] Retrying with HTTP fallback: %s' % fallback_url, xbmc.LOGINFO)
            try:
                req = Request(fallback_url)
                for k, v in _HEADERS:
                    req.add_header(k, v)
                resp = urlopen(req, timeout=20)
                with resp:
                    raw = resp.read()
                xbmc.log('[MovieRulz] HTTP fallback successfully fetched %d bytes' % len(raw), xbmc.LOGINFO)
                ct = ''
                try:
                    ct = resp.headers.get('Content-Type', '')
                except Exception:
                    pass
                m = re.search(r'charset=([^\s;]+)', ct, re.I)
                charset = m.group(1) if m else 'utf-8'
                return raw.decode(charset, errors='replace')
            except Exception as fb_exc:
                xbmc.log('[MovieRulz] HTTP fallback also failed: %s' % fb_exc, xbmc.LOGERROR)

        xbmcgui.Dialog().notification(
            'MovieRulz',
            'Network error — check internet / VPN.',
            xbmcgui.NOTIFICATION_ERROR, 4000
        )
        return None


# ─── URL builder ─────────────────────────────────────────────────────────────

def plugin_url(**kwargs):
    return '%s?%s' % (_URL, urlencode(kwargs))


def get_playable_url(magnet):
    player = _ADDON.getSetting('torrent_player') or 'Auto-detect'
    xbmc.log('[MovieRulz] Resolving magnet via torrent_player setting: %s' % player, xbmc.LOGDEBUG)
    
    if player == 'Auto-detect':
        # Try Elementum
        try:
            xbmcaddon.Addon('plugin.video.elementum')
            xbmc.log('[MovieRulz] Auto-detected Elementum player.', xbmc.LOGINFO)
            return 'plugin://plugin.video.elementum/play?uri=%s' % quote_plus(magnet)
        except Exception:
            pass

        # Try Torrest
        try:
            xbmcaddon.Addon('plugin.video.torrest')
            xbmc.log('[MovieRulz] Auto-detected Torrest player.', xbmc.LOGINFO)
            return 'plugin://plugin.video.torrest/play?uri=%s' % quote_plus(magnet)
        except Exception:
            pass

        # Try Quasar
        try:
            xbmcaddon.Addon('plugin.video.quasar')
            xbmc.log('[MovieRulz] Auto-detected Quasar player.', xbmc.LOGINFO)
            return 'plugin://plugin.video.quasar/play?uri=%s' % quote_plus(magnet)
        except Exception:
            pass
            
        return magnet

    elif player == 'Elementum':
        return 'plugin://plugin.video.elementum/play?uri=%s' % quote_plus(magnet)
    elif player == 'Torrest':
        return 'plugin://plugin.video.torrest/play?uri=%s' % quote_plus(magnet)
    elif player == 'Quasar':
        return 'plugin://plugin.video.quasar/play?uri=%s' % quote_plus(magnet)
    else:
        return magnet


def play_torrent(magnet):
    xbmc.log('[MovieRulz] play_torrent called for magnet link', xbmc.LOGINFO)
    playable_url = get_playable_url(magnet)
    if playable_url == magnet:
        xbmc.log('[MovieRulz] No torrent player found. Showing warning dialog.', xbmc.LOGWARNING)
        xbmcgui.Dialog().ok(
            'MovieRulz',
            'No BitTorrent player detected.\n'
            'Please install Elementum or Torrest to stream torrent magnet links.'
        )
        xbmcplugin.setResolvedUrl(_HANDLE, False, xbmcgui.ListItem())
    else:
        xbmc.log('[MovieRulz] Resolving torrent playback to: %s' % playable_url, xbmc.LOGINFO)
        li = xbmcgui.ListItem(path=playable_url)
        xbmcplugin.setResolvedUrl(_HANDLE, True, li)


# ══════════════════════════════════════════════════════════════════════════════
#  MENU DEFINITIONS
# ══════════════════════════════════════════════════════════════════════════════

YEARS = list(range(2026, 2014, -1))

MAIN_MENU = [
    ('🏠  Home — Latest Movies',   'list_movies', _BASE_URL + '/'),
    ('⭐  Featured',               'list_movies', _BASE_URL + '/movies?sort=featured'),
    ('🔍  Search',                 'search',      ''),
    ('🎬  Bollywood',              'sub_menu',    'bollywood'),
    ('🎭  Telugu',                 'sub_menu',    'telugu'),
    ('🎪  Tamil',                  'sub_menu',    'tamil'),
    ('🌴  Malayalam',              'sub_menu',    'malayalam'),
    ('🎥  Hollywood',              'sub_menu',    'hollywood'),
    ('🔊  Dubbed',                 'sub_menu',    'dubbed'),
    ('🌐  Others',                 'sub_menu',    'others'),
    ('📀  By Quality',             'sub_menu',    'quality'),
]

SUB_MENUS = {
    'bollywood': (
        [('Bollywood Featured', _BASE_URL + '/category/bollywood-featured')] +
        [('Bollywood %d' % y,   _BASE_URL + '/category/bollywood-movies-%d' % y) for y in YEARS]
    ),
    'telugu': (
        [('Telugu Featured',    _BASE_URL + '/category/telugu-featured')] +
        [('Telugu %d' % y,      _BASE_URL + '/category/telugu-movies-%d' % y) for y in YEARS]
    ),
    'tamil': (
        [('Tamil Featured',     _BASE_URL + '/category/tamil-featured')] +
        [('Tamil %d' % y,       _BASE_URL + '/category/tamil-movies-%d' % y) for y in YEARS]
    ),
    'malayalam': (
        [('Malayalam Featured', _BASE_URL + '/category/malayalam-featured')] +
        [('Malayalam %d' % y,   _BASE_URL + '/category/malayalam-movies-%d' % y) for y in YEARS]
    ),
    'hollywood': (
        [('Hollywood Featured', _BASE_URL + '/category/hollywood-featured')] +
        [('Hollywood %d' % y,   _BASE_URL + '/category/hollywood-movies-%d' % y) for y in YEARS]
    ),
    'dubbed': [
        ('Hindi Dubbed',  _BASE_URL + '/language/hindi-dubbed'),
        ('Tamil Dubbed',  _BASE_URL + '/language/tamil-dubbed'),
        ('Telugu Dubbed', _BASE_URL + '/language/telugu-dubbed'),
    ],
    'others': [
        ('Bengali Movies', _BASE_URL + '/language/bengali'),
        ('Punjabi Movies', _BASE_URL + '/language/punjabi'),
    ],
    'quality': [
        ('DVDScr', _BASE_URL + '/quality/dvdscr'),
        ('DVDRip', _BASE_URL + '/quality/dvdrip'),
        ('HDRip',  _BASE_URL + '/quality/hdrip'),
        ('BRRip',  _BASE_URL + '/quality/brrip'),
    ],
}


# ══════════════════════════════════════════════════════════════════════════════
#  VIEWS
# ══════════════════════════════════════════════════════════════════════════════

def show_main_menu():
    xbmcplugin.setPluginCategory(_HANDLE, 'MovieRulz')
    xbmcplugin.setContent(_HANDLE, 'files')
    for label, action, extra in MAIN_MENU:
        li = xbmcgui.ListItem(label=label)
        li.setArt({'icon': 'DefaultFolder.png', 'thumb': 'DefaultFolder.png'})
        li.setInfo('video', {'title': label})
        url = plugin_url(action=action, extra=extra)
        xbmcplugin.addDirectoryItem(_HANDLE, url, li, isFolder=True)
    xbmcplugin.endOfDirectory(_HANDLE)


def show_sub_menu(key):
    entries = SUB_MENUS.get(key, [])
    xbmcplugin.setPluginCategory(_HANDLE, key.title())
    xbmcplugin.setContent(_HANDLE, 'files')
    for label, cat_url in entries:
        li = xbmcgui.ListItem(label=label)
        li.setArt({'icon': 'DefaultFolder.png', 'thumb': 'DefaultFolder.png'})
        li.setInfo('video', {'title': label})
        url = plugin_url(action='list_movies', extra=cat_url)
        xbmcplugin.addDirectoryItem(_HANDLE, url, li, isFolder=True)
    xbmcplugin.endOfDirectory(_HANDLE)


def show_movie_list(page_url):
    xbmc.log('[MovieRulz] show_movie_list invoked for URL: %s' % page_url, xbmc.LOGINFO)
    html = fetch(page_url)
    if not html:
        xbmc.log('[MovieRulz] show_movie_list failed: HTML fetch returned empty content', xbmc.LOGERROR)
        xbmcplugin.endOfDirectory(_HANDLE)
        return

    soup = minisoup(html)
    xbmcplugin.setContent(_HANDLE, 'movies')

    # Each card: div.boxed.film > div.cont_display > a[href] + img[src]
    cards = soup.select('div.boxed.film')
    xbmc.log('[MovieRulz] show_movie_list parsed HTML. Found %d cards.' % len(cards), xbmc.LOGINFO)
    if not cards:
        xbmc.log('[MovieRulz] No boxed film cards found in HTML structure.', xbmc.LOGWARNING)
        xbmcgui.Dialog().notification(
            'MovieRulz', 'No movies found on this page.', xbmcgui.NOTIFICATION_INFO, 3000
        )

    for card in cards:
        a_tag   = card.select_one('div.cont_display a')
        img_tag = card.select_one('div.cont_display img')
        p_tag   = card.select_one('p b') or card.select_one('p')
        xbmc.log('[MovieRulz] Card tags found - a_tag: %s, img_tag: %s, p_tag: %s' % (
            a_tag.tag if a_tag else 'None',
            img_tag.tag if img_tag else 'None',
            p_tag.tag if p_tag else 'None'
        ), xbmc.LOGDEBUG)
        if not a_tag:
            xbmc.log('[MovieRulz] Skipping card: a_tag is None', xbmc.LOGDEBUG)
            continue

        title = (a_tag.get('title') or
                 (p_tag.get_text(strip=True) if p_tag else '')).strip()
        href  = a_tag.get('href', '').strip()
        thumb = (img_tag.get('src', '') if img_tag else '').strip()
        xbmc.log('[MovieRulz] Parsed Movie - Title: "%s" | URL: %s' % (title, href), xbmc.LOGINFO)
        if not href:
            continue
        if not href.startswith('http'):
            href = _BASE_URL + href

        li = xbmcgui.ListItem(label=title)
        li.setArt({'thumb': thumb, 'poster': thumb, 'icon': thumb})
        li.setInfo('video', {'title': title, 'mediatype': 'movie'})
        li.setProperty('IsPlayable', 'false')
        url = plugin_url(action='show_movie', extra=href,
                         title=title, thumb=thumb)
        xbmcplugin.addDirectoryItem(_HANDLE, url, li, isFolder=True)

    # ── Pagination: look for "Next Page" link ──
    nav = soup.select_one('nav#posts-nav')
    if nav:
        older = nav.select_one('div.nav-newer a')
        if older and older.get('href'):
            next_url = older.get('href')
            if not next_url.startswith('http'):
                next_url = _BASE_URL + next_url
            li = xbmcgui.ListItem(label='▶  Next Page →')
            li.setArt({'icon': 'DefaultFolder.png'})
            li.setInfo('video', {'title': 'Next Page'})
            xbmcplugin.addDirectoryItem(
                _HANDLE,
                plugin_url(action='list_movies', extra=next_url),
                li, isFolder=True
            )

    xbmcplugin.addSortMethod(_HANDLE, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    xbmcplugin.endOfDirectory(_HANDLE)


def show_movie(movie_url, title, thumb):
    html = fetch(movie_url)
    if not html:
        xbmcplugin.endOfDirectory(_HANDLE)
        return

    soup = minisoup(html)
    xbmcplugin.setPluginCategory(_HANDLE, title)
    xbmcplugin.setContent(_HANDLE, 'movies')

    # ── Synopsis ──
    synopsis = ''
    syn_p = soup.select_one('div.synopsis-section p')
    if syn_p:
        synopsis = syn_p.get_text(' ', strip=True)

    # ── Movie metadata ──
    director = cast = genre = quality = language = ''
    info_block = soup.select_one('div.movie-info-block')
    if info_block:
        for p in info_block.select('p'):
            strong = p.select_one('strong')
            if not strong:
                continue
            key = strong.get_text(strip=True).lower()
            val = p.get_text(' ', strip=True)
            # Strip the label itself from val
            val = val.replace(strong.get_text(strip=True), '').strip().lstrip(':').strip()
            if 'direct' in key:
                director = val
            elif 'starring' in key or 'cast' in key:
                cast = val
            elif 'genre' in key:
                genre = val
            elif 'quality' in key:
                quality = val
            elif 'language' in key:
                language = val

    # ── Torrent / Magnet links ──
    #  <a href="magnet:?xt=..." class="torrent-btn" …>
    #     <span class="btn-size">3 gb 1080p</span>
    #  </a>
    magnet_links = []
    torrent_section = soup.select_one('div.torrent-section')
    if torrent_section:
        for a in torrent_section.select('a.torrent-btn'):
            magnet = a.get('href', '').strip()
            if not magnet.startswith('magnet:'):
                continue
            size_span = a.select_one('span.btn-size')
            size_label = size_span.get_text(strip=True).upper() if size_span else 'UNKNOWN'
            magnet_links.append((size_label, magnet))

    # Fallback: regex scan entire page for magnet URIs (in case markup changes)
    if not magnet_links:
        for m in re.finditer(r'href=["\']?(magnet:\?[^"\'>\s]+)', html):
            raw = m.group(1)
            # extract dn= filename as label
            dn_m = re.search(r'[?&]dn=([^&]+)', raw)
            label = unquote_plus(dn_m.group(1)) if dn_m else raw[:60]
            magnet_links.append((label, raw))

    if not magnet_links:
        li = xbmcgui.ListItem(label='⚠  No torrent links found for this movie')
        li.setInfo('video', {'title': 'No torrents'})
        xbmcplugin.addDirectoryItem(_HANDLE, '', li, isFolder=False)
        xbmcplugin.endOfDirectory(_HANDLE)
        return

    # ── Add one playable entry per magnet link ──
    for size_label, magnet in magnet_links:
        item_title = '%s  [%s]' % (title, size_label)
        li = xbmcgui.ListItem(label=item_title)
        li.setArt({'thumb': thumb, 'poster': thumb, 'icon': thumb, 'fanart': thumb})
        li.setInfo('video', {
            'title':     item_title,
            'plot':      synopsis,
            'director':  director,
            'cast':      [c.strip() for c in cast.split(',')] if cast else [],
            'genre':     genre,
            'mediatype': 'movie',
        })
        # IsPlayable=true → Kodi calls our addon's play_torrent action to resolve
        li.setProperty('IsPlayable', 'true')
        url = plugin_url(action='play_torrent', extra=magnet)
        xbmcplugin.addDirectoryItem(_HANDLE, url, li, isFolder=False)

    xbmcplugin.endOfDirectory(_HANDLE)


def do_search():
    query = xbmcgui.Dialog().input(
        'Search MovieRulz', type=xbmcgui.INPUT_ALPHANUM
    )
    if not query:
        xbmcplugin.endOfDirectory(_HANDLE)
        return
    search_url = _BASE_URL + '/search_movies?s=' + quote_plus(query)
    show_movie_list(search_url)


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTER
# ══════════════════════════════════════════════════════════════════════════════

def router(paramstring):
    params = dict(parse_qsl(paramstring.lstrip('?')))
    action = params.get('action', '')
    extra  = params.get('extra', '')
    title  = unquote_plus(params.get('title', ''))
    thumb  = unquote_plus(params.get('thumb', ''))

    if not action:
        show_main_menu()
    elif action == 'sub_menu':
        show_sub_menu(extra)
    elif action == 'list_movies':
        show_movie_list(extra)
    elif action == 'show_movie':
        show_movie(extra, title, thumb)
    elif action == 'play_torrent':
        play_torrent(extra)
    elif action == 'search':
        do_search()
    else:
        xbmc.log('[MovieRulz] Unknown action: %s' % action, xbmc.LOGWARNING)
        show_main_menu()


if __name__ == '__main__':
    router(sys.argv[2] if len(sys.argv) > 2 else '')
