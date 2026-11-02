"""Fetch and clean official web pages for the knowledge base. Plain Python, no Django imports.

Used only by ``manage.py scrape_sources``; never during a chat request. The command stores
the result through the same chunk/embed helper as ``ingest_corpus``.

Safety rules (tests/test_scraper.py checks each one):

1. Allowlist: only hosts named in data/scrape_sources.yaml are fetched. Redirects are
   followed by hand, and every hop must stay on an allowlisted host over https.
2. SSRF guard: the hostname is resolved first, and private, loopback, link-local, reserved
   and other non-public addresses are refused.
3. Limits: a 15 s timeout, a 2 MB body cap (the body is streamed and reading stops at the
   cap), and the content type must be text/html. A PDF link is reported, not read.
4. Polite: an identifiable User-Agent, robots.txt is honoured, and there is a delay between
   requests (2 s by default).
5. Clean text: scripts, styles, navigation, headers, footers, forms, cookie banners and
   hidden elements are removed; headings stay on their own line so the chunker sees them.
6. Scraped text is untrusted: lines that look like prompt injection are dropped before
   chunking, and counted.
7. Nothing is written to disk: everything stays in memory.
"""

from __future__ import annotations

import hashlib
import ipaddress
import re
import socket
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from email.message import Message
from urllib import robotparser
from urllib.parse import urljoin, urlsplit

import httpx
import yaml
from bs4 import BeautifulSoup

USER_AGENT = "SahkarSaathiBot/1.0 (research prototype)"
TIMEOUT_SECONDS = 15.0
MAX_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 5
DEFAULT_DELAY_SECONDS = 2.0

# Mirrors apps.knowledge.models.Document.DocType (tests check that the two agree).
DOC_TYPES = frozenset({"act", "rules", "model-bylaws", "circular", "scheme-guideline"})
REQUIRED_FIELDS = ("id", "url", "title", "publisher", "doc_type", "state", "language")
OPTIONAL_FIELDS = ("selector",)
_SLUG = re.compile(r"^[-a-zA-Z0-9_]{1,64}$")
_STATE = re.compile(r"^(central|[A-Z]{2,3})$")


# --- The source list ------------------------------------------------------------------


@dataclass(frozen=True)
class ScrapeSource:
    id: str
    url: str
    title: str
    publisher: str
    doc_type: str
    state: str
    language: str
    selector: str | None = None

    @property
    def host(self) -> str:
        return normalise_host(urlsplit(self.url).hostname or "")


class SourceListError(ValueError):
    """data/scrape_sources.yaml is malformed. The message names every problem found."""


def parse_sources(data: object) -> list[ScrapeSource]:
    """Validate the parsed YAML (``{"sources": [...]}``) and return the sources.

    Fails loudly on a missing or empty field, an unknown field or doc_type, a duplicate id,
    an id that is not a slug, a state that is not "central" or a state code, and any url
    that is not https with a host name.
    """
    if data is None:
        return []
    # "sources:" with only commented-out entries under it parses as None: an empty list.
    entries = data.get("sources") if isinstance(data, dict) else None
    if not isinstance(data, dict) or not isinstance(entries or [], list):
        raise SourceListError('The file must be a mapping with a "sources" list.')
    entries = entries or []
    problems: list[str] = []
    sources: list[ScrapeSource] = []
    seen: set[str] = set()
    for n, entry in enumerate(entries, start=1):
        where = f"entry {n}"
        if not isinstance(entry, dict):
            problems.append(f"{where}: must be a mapping")
            continue
        where = f"entry {n} ({entry.get('id', 'no id')})"
        missing = [f for f in REQUIRED_FIELDS if not str(entry.get(f) or "").strip()]
        if missing:
            problems.append(f"{where}: missing {', '.join(missing)}")
            continue
        unknown = sorted(set(entry) - set(REQUIRED_FIELDS) - set(OPTIONAL_FIELDS))
        if unknown:
            problems.append(f"{where}: unknown field(s) {', '.join(unknown)}")
        values = {f: str(entry[f]).strip() for f in REQUIRED_FIELDS}
        if not _SLUG.match(values["id"]):
            problems.append(f"{where}: id must be a slug (letters, digits, - and _)")
        if values["id"] in seen:
            problems.append(f"{where}: duplicate id {values['id']!r}")
        seen.add(values["id"])
        if values["doc_type"] not in DOC_TYPES:
            allowed = ", ".join(sorted(DOC_TYPES))
            problems.append(f"{where}: unknown doc_type {values['doc_type']!r} ({allowed})")
        if not _STATE.match(values["state"]):
            problems.append(f'{where}: state must be "central" or a state code such as TN')
        parts = urlsplit(values["url"])
        if parts.scheme != "https" or not parts.hostname:
            problems.append(f"{where}: url must be an https URL, got {values['url']!r}")
        selector = entry.get("selector")
        sources.append(ScrapeSource(**values, selector=str(selector).strip() if selector else None))
    if problems:
        raise SourceListError("data/scrape_sources.yaml: " + "; ".join(problems))
    return sources


def load_sources(text: str) -> list[ScrapeSource]:
    """Parse and validate the YAML text of the source list."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise SourceListError(f"data/scrape_sources.yaml is not valid YAML: {exc}") from exc
    return parse_sources(data)


# --- Errors ---------------------------------------------------------------------------


class ScrapeBlocked(Exception):
    """A safety rule stopped the fetch (allowlist, address, robots.txt, size)."""


class ScrapeError(Exception):
    """The page could not be fetched or used (HTTP error, wrong type, no text)."""


# --- Host and address checks ----------------------------------------------------------


def normalise_host(host: str) -> str:
    return host.strip().rstrip(".").lower()


def is_public_address(address: str) -> bool:
    """True only for a globally routable unicast address."""
    try:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    bad = (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )
    return ip.is_global and not bad


def resolve_host(host: str) -> list[str]:
    """Every address the host name resolves to (IPv4 and IPv6)."""
    infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    return sorted({info[4][0] for info in infos})


def check_url(url: str, allowed_hosts: Iterable[str], resolver: Callable[[str], list[str]]):
    """Raise ScrapeBlocked unless the URL is https, on an allowlisted host, port 443, and
    the host resolves only to public addresses."""
    parts = urlsplit(url)
    if parts.scheme != "https":
        raise ScrapeBlocked(f"not https: {url}")
    host = normalise_host(parts.hostname or "")
    if host not in {normalise_host(h) for h in allowed_hosts}:
        raise ScrapeBlocked(f"host not on the allowlist: {host or url}")
    if parts.username or parts.password:
        raise ScrapeBlocked("URLs with a user name or password are not fetched")
    try:
        port = parts.port
    except ValueError as exc:
        raise ScrapeBlocked(f"bad port in {url}") from exc
    if port not in (None, 443):
        raise ScrapeBlocked(f"only port 443 is fetched, not {port}")
    try:
        addresses = resolver(host)
    except OSError as exc:
        raise ScrapeError(f"could not resolve {host} ({exc.__class__.__name__})") from exc
    if not addresses:
        raise ScrapeError(f"{host} resolved to no address")
    private = [a for a in addresses if not is_public_address(a)]
    if private:
        raise ScrapeBlocked(f"{host} resolves to a non-public address ({', '.join(private)})")


# --- Fetching -------------------------------------------------------------------------


@dataclass
class Response:
    url: str
    status: int
    content_type: str
    charset: str | None
    body: bytes
    location: str = ""  # set for a redirect


def _parse_content_type(value: str) -> tuple[str, str | None]:
    message = Message()
    message["content-type"] = value or "application/octet-stream"
    return message.get_content_type(), message.get_content_charset()


class Fetcher:
    """Fetches allowlisted https pages with every safety rule applied.

    ``client``, ``resolver``, ``sleep`` and ``clock`` are injectable for tests.
    """

    def __init__(
        self,
        allowed_hosts: Iterable[str],
        *,
        client: httpx.Client | None = None,
        resolver: Callable[[str], list[str]] = resolve_host,
        delay: float = DEFAULT_DELAY_SECONDS,
        timeout: float = TIMEOUT_SECONDS,
        max_bytes: int = MAX_BYTES,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.allowed_hosts = frozenset(normalise_host(h) for h in allowed_hosts if h)
        self.client = client or httpx.Client(timeout=timeout, follow_redirects=False)
        self.resolver = resolver
        self.delay = max(0.0, delay)
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.sleep = sleep
        self.clock = clock
        self._last_request: float | None = None
        self._robots: dict[str, robotparser.RobotFileParser] = {}

    def close(self) -> None:
        self.client.close()

    def _wait_turn(self) -> None:
        if self._last_request is not None:
            remaining = self.delay - (self.clock() - self._last_request)
            if remaining > 0:
                self.sleep(remaining)
        self._last_request = self.clock()

    def _request(self, url: str) -> Response:
        """One GET, without following redirects; reads at most max_bytes of the body."""
        self._wait_turn()
        deadline = self.clock() + self.timeout
        headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
        with self.client.stream(
            "GET", url, headers=headers, follow_redirects=False, timeout=self.timeout
        ) as response:
            content_type, charset = _parse_content_type(response.headers.get("content-type", ""))
            if response.is_redirect:
                location = response.headers.get("location", "")
                return Response(url, response.status_code, content_type, charset, b"", location)
            declared = response.headers.get("content-length", "")
            if declared.isdigit() and int(declared) > self.max_bytes:
                raise ScrapeBlocked(f"response is larger than {self.max_bytes // 1024} KB")
            body = bytearray()
            for piece in response.iter_bytes():
                body.extend(piece)
                if len(body) > self.max_bytes:
                    raise ScrapeBlocked(f"response is larger than {self.max_bytes // 1024} KB")
                if self.clock() > deadline:
                    raise ScrapeError(f"timed out after {self.timeout:g} s")
            return Response(url, response.status_code, content_type, charset, bytes(body))

    def get(self, url: str, *, check_robots: bool = True) -> Response:
        """GET with redirects followed by hand. Every hop is checked against the allowlist,
        the address rules and (unless check_robots is false) robots.txt."""
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            check_url(current, self.allowed_hosts, self.resolver)
            if check_robots and not self.allowed_by_robots(current):
                raise ScrapeBlocked(f"robots.txt disallows {current}")
            response = self._request(current)
            if response.status in (301, 302, 303, 307, 308):
                if not response.location:
                    raise ScrapeError(f"redirect without a Location from {current}")
                current = urljoin(current, response.location)
                continue
            return response
        raise ScrapeBlocked(f"more than {MAX_REDIRECTS} redirects from {url}")

    def allowed_by_robots(self, url: str) -> bool:
        parts = urlsplit(url)
        host = normalise_host(parts.hostname or "")
        parser = self._robots.get(host)
        if parser is None:
            parser = self._load_robots(f"https://{host}/robots.txt")
            self._robots[host] = parser
        return parser.can_fetch(USER_AGENT, url)

    def _load_robots(self, robots_url: str) -> robotparser.RobotFileParser:
        """robots.txt as urllib.robotparser reads it: 401/403 disallow everything, another
        4xx allows everything. Any other failure blocks the host, to stay on the safe side."""
        parser = robotparser.RobotFileParser(robots_url)
        try:
            response = self.get(robots_url, check_robots=False)
        except (httpx.HTTPError, ScrapeError) as exc:
            raise ScrapeBlocked(f"robots.txt could not be read ({exc.__class__.__name__})") from exc
        if response.status in (401, 403):
            parser.disallow_all = True
        elif 400 <= response.status < 500:
            parser.allow_all = True
        elif response.status != 200:
            raise ScrapeBlocked(f"robots.txt answered HTTP {response.status}")
        else:
            text = response.body.decode(response.charset or "utf-8", errors="replace")
            parser.parse(text.splitlines())
        return parser

    def fetch_html(self, url: str) -> tuple[str, str]:
        """(final URL, HTML text) of a page. Raises ScrapeBlocked or ScrapeError."""
        response = self.get(url)
        if response.status != 200:
            raise ScrapeError(f"HTTP {response.status} from {response.url}")
        if response.content_type == "application/pdf":
            raise ScrapeError("pdf link, use ingest_corpus (download it to data/raw/)")
        if response.content_type not in ("text/html", "application/xhtml+xml"):
            raise ScrapeError(f"content type is {response.content_type}, not text/html")
        html = response.body.decode(response.charset or "utf-8", errors="replace")
        return response.url, html


# --- Cleaning -------------------------------------------------------------------------

_REMOVE_TAGS = (
    "script", "style", "noscript", "template", "iframe", "svg", "canvas", "nav", "header",
    "footer", "form", "button", "select", "input", "textarea", "dialog",
)  # fmt: skip
_BLOCK_TAGS = (
    "p", "div", "section", "article", "main", "li", "dt", "dd", "tr", "table", "ul", "ol",
    "blockquote", "pre", "address", "figcaption", "caption", "td", "th",
)  # fmt: skip
_HEADING_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6")
_BANNER = re.compile(r"cookie|consent|gdpr|skip[-_]?(link|nav|to)", re.IGNORECASE)
_HIDDEN_STYLE = re.compile(r"display\s*:\s*none|visibility\s*:\s*hidden", re.IGNORECASE)
_HIDDEN_ROLES = {"navigation", "banner", "contentinfo", "search", "dialog", "alertdialog"}
_WHITESPACE = re.compile(r"\s+")
HEADING_MAX_CHARS = 80  # ingest_corpus.is_heading treats upper-case lines up to 80 as headings


def _is_unwanted(tag) -> bool:
    attrs = tag.attrs or {}
    if "hidden" in attrs or str(attrs.get("aria-hidden", "")).lower() == "true":
        return True
    if _HIDDEN_STYLE.search(str(attrs.get("style", ""))):
        return True
    if str(attrs.get("role", "")).lower() in _HIDDEN_ROLES:
        return True
    marker = " ".join([str(attrs.get("id", "")), *map(str, attrs.get("class", []) or [])])
    return bool(_BANNER.search(marker))


def extract_text(html: str, selector: str | None = None) -> str:
    """The readable text of a page: one line per block, headings on their own line in
    capitals (so the chunker keeps them with the text after them), whitespace collapsed."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(_REMOVE_TAGS):
        tag.decompose()
    for tag in [t for t in soup.find_all(True) if _is_unwanted(t)]:
        if not tag.decomposed:
            tag.decompose()

    if selector:
        root = soup.select_one(selector)
        if root is None:
            raise ScrapeError(f"the selector {selector!r} matched nothing on the page")
    else:
        root = soup.find("main") or soup.find(attrs={"role": "main"}) or soup.body or soup

    # Line breaks in the HTML source mean nothing; only the block markers below do.
    for piece in root.find_all(string=True):
        piece.replace_with(_WHITESPACE.sub(" ", str(piece)))
    for br in root.find_all("br"):
        br.replace_with("\n")
    for heading in root.find_all(_HEADING_TAGS):
        text = " ".join(heading.get_text(" ").split())
        if len(text) <= HEADING_MAX_CHARS:
            text = text.upper()
        heading.replace_with(f"\n{text}\n")
    for block in root.find_all(_BLOCK_TAGS):
        block.insert_before("\n")
        block.insert_after("\n")

    lines = (" ".join(line.split()) for line in root.get_text().splitlines())
    return "\n".join(line for line in lines if line)


# --- Prompt-injection filter ----------------------------------------------------------

# Conservative on purpose: each pattern is phrasing aimed at a language model, not wording
# that appears in cooperative law. A bare "act as" is NOT here, because legal text says
# "the Registrar may act as arbitrator"; only "act as an AI / assistant / ..." is.
_EARLIER = r"(?:previous|prior|above|earlier|preceding)"
_INJECTION_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        rf"\bignore\s+(?:all\s+|any\s+)?(?:the\s+|your\s+)?{_EARLIER}\s+"
        r"(?:instructions?|prompts?|messages?|rules|directions)",
        r"\bignore\s+all\s+prior\b",
        rf"\bdisregard\s+(?:all\s+|any\s+)?(?:the\s+|your\s+)?(?:{_EARLIER}|instructions?)",
        rf"\bforget\s+(?:all\s+|everything\s+|your\s+)?(?:{_EARLIER}\s+)?"
        r"(?:instructions?|prompts?|rules)",
        r"\byou\s+are\s+now\b",
        r"\bsystem\s+prompt\b",
        r"\bact\s+as\s+(?:an?\s+|the\s+)?"
        r"(?:ai|assistant|chat\s?bot|llm|language\s+model|unrestricted|jailbroken|dan)\b",
        r"\breveal\s+(?:your|the)\s+(?:system\s+|hidden\s+|secret\s+)?"
        r"(?:instructions|prompt|rules)",
        r"\bdo\s+anything\s+now\b",
        r"\bnew\s+instructions\s*:",
        r"\bjailbreak",
        r"<\|?(?:im_start|im_end|system|endoftext)\|?>",
        # hi: "ignore the previous / all instructions". Machine-written, needs review by a
        # fluent speaker.
        r"(?:पिछले|पूर्व|सभी|ऊपर\s+के)\s+(?:सभी\s+)?निर्देश\S*\s+(?:को\s+)?"
        r"(?:अनदेखा|नज़रअंदाज़|नजरअंदाज|भूल)",
    )
]


def looks_like_injection(line: str) -> bool:
    """True if the line reads like an instruction to a language model."""
    return any(pattern.search(line) for pattern in _INJECTION_PATTERNS)


def drop_injection_lines(text: str) -> tuple[str, int]:
    """(text without the suspicious lines, how many lines were dropped)."""
    kept: list[str] = []
    dropped = 0
    for line in text.splitlines():
        if looks_like_injection(line):
            dropped += 1
        else:
            kept.append(line)
    return "\n".join(kept), dropped


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --- One source -----------------------------------------------------------------------


@dataclass
class ScrapedPage:
    source: ScrapeSource
    final_url: str
    text: str  # cleaned, injection lines removed
    injection_dropped: int


def scrape_source(source: ScrapeSource, fetcher: Fetcher) -> ScrapedPage:
    """Fetch and clean one source. Raises ScrapeBlocked, ScrapeError or httpx.HTTPError."""
    final_url, html = fetcher.fetch_html(source.url)
    text, dropped = drop_injection_lines(extract_text(html, source.selector))
    return ScrapedPage(source, final_url, text, dropped)
