import calendar
import csv
import hashlib
import json
import os
import queue
import re
import secrets
import socket
import ssl
import subprocess
import sys
import threading
import time
import tkinter as tk
from dataclasses import dataclass
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urldefrag, urljoin, urlparse
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener, urlopen

import socks
import sockshandler


DEFAULT_EXCLUDES = ".jpg,.jpeg,.png,.css,.woff2,.woff,.scss,.gif,.js,.map"
DANGEROUS_EXTS = {
    ".exe",
    ".dll",
    ".scr",
    ".com",
    ".bat",
    ".cmd",
    ".ps1",
    ".vbs",
    ".vbe",
    ".js",
    ".jse",
    ".wsf",
    ".wsh",
    ".hta",
    ".msi",
    ".msp",
    ".lnk",
    ".url",
    ".iso",
    ".img",
    ".vhd",
    ".vhdx",
    ".docm",
    ".xlsm",
    ".pptm",
    ".xlam",
    ".jar",
}
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) OpenDirDownloaderGUI/1.0"
DEFAULT_USER_AGENTS = """# One user-agent per line. Blank lines and comments are ignored.
# CasaLens rotates these in CASALENS_UA_MODE=rotate.
# Crawler/bot user-agents are intentionally ignored.
Googlebot-Image/1.0
Googlebot-News
Googlebot-Video/1.0
AdsBot-Google (+http://www.google.com/adsbot.html)
AdsBot-Google-Mobile (+http://www.google.com/mobile/adsbot.html)
APIs-Google (+https://developers.google.com/webmasters/APIs-Google.html)
Mediapartners-Google
FeedFetcher-Google; (+http://www.google.com/feedfetcher.html)
Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)
Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0 bingbot/2.0
Mozilla/5.0 (compatible; Yahoo! Slurp; http://help.yahoo.com/help/us/ysearch/slurp)
DuckDuckBot/1.1; (+http://duckduckgo.com/duckduckbot.html)
Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)
Mozilla/5.0 (compatible; YandexImages/3.0; +http://yandex.com/bots)
Mozilla/5.0 (compatible; Baiduspider/2.0; +http://www.baidu.com/search/spider.html)
Mozilla/5.0 (compatible; PetalBot; +https://aspiegel.com/petalbot)
Mozilla/5.0 (compatible; Bytespider; +https://bytespider.com/webmaster)
Mozilla/5.0 (compatible; Applebot/0.1; +http://www.apple.com/go/applebot)
facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)
Twitterbot/1.0
Mozilla/5.0 (compatible; LinkedInBot/1.0; +http://www.linkedin.com)
Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)
Discordbot/2.0
TelegramBot (like TwitterBot)
WhatsApp/2.23.20 A
Mozilla/5.0 (compatible; GPTBot/1.0; +https://openai.com/gptbot)
Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ChatGPT-User/1.0; +https://openai.com/bot
Mozilla/5.0 (compatible; ClaudeBot/1.0; +https://www.anthropic.com/bot-details)
Mozilla/5.0 (compatible; anthropic-ai/1.0; +http://www.anthropic.com)
Mozilla/5.0 (compatible; PerplexityBot/1.0; +https://www.perplexity.ai/perplexitybot)
CCBot/2.0 (https://commoncrawl.org/faq/)
Mozilla/5.0 (compatible; AhrefsBot/7.0; +http://ahrefs.com/robot/)
Mozilla/5.0 (compatible; SemrushBot/7~bl; +http://www.semrush.com/bot.html)
Mozilla/5.0 (compatible; MJ12bot/v1.4.8; http://mj12bot.com/)
DotBot/1.2 (+https://opensiteexplorer.org/dotbot)
Mozilla/5.0 (compatible; ia_archiver; +http://archive.org/details/archive.org_bot)
Mozilla/5.0 (compatible; CensysInspect/1.1; +https://about.censys.io/)
Shodan/1.0 (+https://www.shodan.io/)
NetcraftSurveyAgent/1.0
Mozilla/5.0 zgrab/0.x
python-requests/2.31.0
curl/8.5.0
Wget/1.21.4
Go-http-client/1.1
Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/122.0.0.0 Safari/537.36
Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 HeadlessChrome/120.0.0.0
Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36
Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15
Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0
Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1
Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)
"""
STOP = object()
ORIGINAL_SOCKET = socket.socket
ORIGINAL_CREATE_CONNECTION = socket.create_connection
SOCKET_PROXY_LOCK = threading.Lock()
TOR_MAX_WORKERS = 32
DEFAULT_PROXY_SOURCES = (
    "https://raw.githubusercontent.com/j0rd1s3rr4n0/api/refs/heads/main/proxy/http.txt",
    "https://raw.githubusercontent.com/j0rd1s3rr4n0/api/refs/heads/main/proxy/proxies.txt",
)
PROXY_RE = re.compile(r"^(?:(https?|socks(?:4a?|5h?))://)?(?:[^@\s]+@)?([A-Za-z0-9._-]+):(\d{2,5})$", re.I)
SUPPORTED_PROXY_SCHEMES = {"http", "https", "socks4", "socks4a", "socks5", "socks5h"}
PIRATE_FLAG = "\U0001F3F4\u200d\u2620\ufe0f"
COUNTRY_NAMES = {
    "ES": "Spain",
    "US": "United States",
    "FR": "France",
    "DE": "Germany",
    "GB": "United Kingdom",
    "IT": "Italy",
    "PT": "Portugal",
    "NL": "Netherlands",
    "BR": "Brazil",
    "RU": "Russia",
    "CN": "China",
    "JP": "Japan",
    "CA": "Canada",
    "MX": "Mexico",
    "AR": "Argentina",
}


class Cancelled(Exception):
    pass


def parse_socks_proxy(raw: str) -> tuple[int, str, int, bool, str | None, str | None]:
    raw = raw.strip()
    if "://" not in raw:
        raw = "socks5h://" + raw
    parsed = urlparse(raw)
    scheme = parsed.scheme.lower()
    if scheme not in {"socks5", "socks5h", "socks4", "socks4a"}:
        raise ValueError("Proxy Tor invalido. Usa socks5h://127.0.0.1:9050")
    if not parsed.hostname or not parsed.port:
        raise ValueError("Proxy Tor invalido. Indica host y puerto.")
    proxy_type = socks.SOCKS5 if scheme in {"socks5", "socks5h"} else socks.SOCKS4
    return (
        proxy_type,
        parsed.hostname,
        parsed.port,
        scheme.endswith("h") or scheme.endswith("a"),
        unquote(parsed.username) if parsed.username else None,
        unquote(parsed.password) if parsed.password else None,
    )


def add_tor_session_auth(proxy_url: str) -> str:
    raw = proxy_url.strip()
    if "://" not in raw:
        raw = "socks5h://" + raw
    parsed = urlparse(raw)
    if parsed.username or parsed.password:
        return raw
    if not parsed.hostname or not parsed.port:
        parse_socks_proxy(raw)
    host = parsed.hostname or "127.0.0.1"
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    return f"{parsed.scheme}://opendir:{secrets.token_hex(12)}@{host}:{parsed.port}"


def limit_tor_workers(workers: int, use_tor: bool) -> int:
    workers = max(1, workers)
    if use_tor:
        return min(workers, TOR_MAX_WORKERS)
    return workers


def is_onion_url(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return host.lower().endswith(".onion")


def sanitize_path_part(part: str) -> str:
    part = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", part).strip(" .")
    if not part:
        return "_"
    stem = part.split(".", 1)[0].upper()
    reserved = {"CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
                "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"}
    return f"_{part}" if stem in reserved else part


def is_dangerous_url(url: str) -> bool:
    return Path(urlparse(url).path).suffix.lower() in DANGEROUS_EXTS


def mark_windows_download(path: Path, url: str) -> None:
    try:
        with open(str(path) + ":Zone.Identifier", "w", encoding="utf-8") as stream:
            stream.write("[ZoneTransfer]\nZoneId=3\nHostUrl=" + url + "\n")
    except OSError:
        return


def set_download_timestamp(path: Path, last_modified: str) -> None:
    if not last_modified:
        return
    try:
        modified = parsedate_to_datetime(last_modified)
        timestamp = modified.timestamp()
        os.utime(path, (timestamp, timestamp))
    except (OSError, ValueError, TypeError, OverflowError):
        return


def resource_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / name


def config_path() -> Path:
    base = Path(os.environ.get("APPDATA") or Path.home())
    return base / "OpenDirDownloader" / "config.json"


def split_terms(value: str) -> list[str]:
    return [part.strip().lower() for part in re.split(r"[\n,;]+", value) if part.strip()]


def parse_user_agents(value: str) -> list[str]:
    agents: list[str] = []
    seen: set[str] = set()
    for line in value.splitlines():
        agent = line.strip()
        if not agent or agent.startswith("#"):
            continue
        if agent not in seen:
            seen.add(agent)
            agents.append(agent)
    return agents or [USER_AGENT]


class UserAgentRotator:
    def __init__(self, agents: list[str], rotate: bool) -> None:
        self.agents = agents or [USER_AGENT]
        self.rotate = rotate and len(self.agents) > 1
        self.lock = threading.Lock()
        self.index = secrets.randbelow(len(self.agents)) if self.rotate else 0

    def next(self) -> str:
        with self.lock:
            agent = self.agents[self.index % len(self.agents)]
            if self.rotate:
                self.index += 1
            return agent


def split_proxy_sources(value: str) -> list[str]:
    sources = [part.strip() for part in re.split(r"[\n,; ]+", value) if part.strip()]
    return sources or list(DEFAULT_PROXY_SOURCES)


def country_flag(country_code: str) -> str:
    code = (country_code or "").strip().upper()
    if len(code) != 2 or not code.isalpha() or code == "XX":
        return PIRATE_FLAG
    return "".join(chr(0x1F1E6 + ord(char) - ord("A")) for char in code)


def resolve_target_geo(url: str) -> dict[str, str]:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if not host or host.lower().endswith(".onion"):
        return {"flag": PIRATE_FLAG, "country": "Unknown", "country_code": "XX", "ip": "", "host": host}
    try:
        socket.inet_aton(host)
        ip = host
    except OSError:
        try:
            ip = socket.gethostbyname(host)
        except OSError:
            return {"flag": PIRATE_FLAG, "country": "Unknown", "country_code": "XX", "ip": "", "host": host}
    try:
        request = Request(f"https://ipinfo.io/{ip}/json", headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=4) as response:
            data = json.loads(response.read().decode("utf-8", errors="ignore"))
        code = str(data.get("country") or "XX").upper()
        country = str(data.get("country_name") or COUNTRY_NAMES.get(code) or data.get("country") or "Unknown")
        return {"flag": country_flag(code), "country": country, "country_code": code, "ip": ip, "host": host}
    except Exception:
        return {"flag": PIRATE_FLAG, "country": "Unknown", "country_code": "XX", "ip": ip, "host": host}


def source_needs_network(source: str) -> bool:
    return urlparse(source).scheme.lower() in {"http", "https"}


def has_network_proxy_sources(sources: list[str]) -> bool:
    return any(source_needs_network(source) for source in sources)


def normalize_proxy(raw: str) -> str | None:
    raw = raw.strip()
    if not raw or raw.startswith("#"):
        return None
    match = PROXY_RE.match(raw)
    if not match:
        return None
    scheme_raw, host, port_raw = match.groups()
    scheme = (scheme_raw or "http").lower()
    if scheme not in SUPPORTED_PROXY_SCHEMES:
        return None
    try:
        port = int(port_raw)
    except ValueError:
        return None
    if port < 1 or port > 65535:
        return None
    if host in {"0.0.0.0", "127.0.0.1", "localhost"} or host.startswith("0."):
        return None
    if "://" not in raw:
        return f"{scheme}://{host}:{port}"
    return raw


def proxy_scheme(proxy_url: str) -> str:
    return urlparse(proxy_url).scheme.lower()


def tolerant_ssl_context():
    context = ssl._create_unverified_context()
    if hasattr(ssl, "OP_IGNORE_UNEXPECTED_EOF"):
        context.options |= ssl.OP_IGNORE_UNEXPECTED_EOF
    try:
        context.set_ciphers("DEFAULT:@SECLEVEL=0")
    except ssl.SSLError:
        pass
    return context


def is_ssl_eof_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    if "unexpected_eof_while_reading" in text or "eof occurred in violation of protocol" in text:
        return True
    reason = getattr(exc, "reason", None)
    if reason and is_ssl_eof_error(reason):
        return True
    return False


def http_fallback_url(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.scheme.lower() != "https":
        return None
    return parsed._replace(scheme="http").geturl()


def detect_server_tag(html: str, headers=None) -> str:
    server = ""
    try:
        server = headers.get("Server", "") if headers else ""
    except AttributeError:
        server = ""
    haystack = f"{server}\n{html[:20000]}".lower()
    if "proudly served by litespeed web server" in haystack or "litespeed" in server.lower():
        return "LiteSpeed"
    if "index of" in haystack:
        return "Directory listing"
    return ""


def opener_for_proxy(proxy_url: str, ssl_context=None):
    handlers = []
    if ssl_context is not None:
        handlers.append(HTTPSHandler(context=ssl_context))
    scheme = proxy_scheme(proxy_url)
    if scheme in {"http", "https"}:
        return build_opener(ProxyHandler({"http": proxy_url, "https": proxy_url}), *handlers)
    proxy_type, host, port, rdns, username, password = parse_socks_proxy(proxy_url)
    return build_opener(sockshandler.SocksiPyHandler(proxy_type, host, port, rdns, username, password), *handlers)


class HttpProxyPool:
    def __init__(self, sources: list[str], timeout: float, log, source_tor_proxy: str | None = None) -> None:
        self.sources = sources
        self.timeout = max(5.0, min(timeout, 30.0))
        self.log = log
        self.source_tor_proxy = source_tor_proxy
        self.lock = threading.Lock()
        self.proxies: list[str] = []
        self.index = 0

    def read_source(self, source: str) -> str:
        parsed = urlparse(source)
        if parsed.scheme.lower() in {"http", "https"}:
            request = Request(source, headers={"User-Agent": USER_AGENT})
            with urlopen(request, timeout=self.timeout) as response:
                return response.read().decode("utf-8", errors="ignore")
        if parsed.scheme.lower() == "file":
            path_text = unquote(parsed.path)
            if re.match(r"^/[A-Za-z]:/", path_text):
                path_text = path_text[1:]
            return Path(path_text).read_text(encoding="utf-8", errors="ignore")
        return Path(source).read_text(encoding="utf-8", errors="ignore")

    def load(self) -> None:
        seen: set[str] = set()
        loaded: list[str] = []
        routed_sources = self.source_tor_proxy and has_network_proxy_sources(self.sources)
        if routed_sources:
            self.log("[PROXY] Cargando fuentes remotas via Tor para evitar fuga de IP")
            configure_socket_proxy(True, self.source_tor_proxy)
        try:
            for source in self.sources:
                try:
                    text = self.read_source(source)
                except Exception as exc:
                    self.log(f"[PROXY] No se pudo cargar {source}: {exc}")
                    continue
                for line in text.splitlines():
                    proxy = normalize_proxy(line)
                    if proxy and proxy not in seen:
                        seen.add(proxy)
                        loaded.append(proxy)
        finally:
            if routed_sources:
                configure_socket_proxy(False, "")
        self.proxies = loaded
        self.log(f"[PROXY] Cargados {len(self.proxies)} proxies HTTP/HTTPS/SOCKS")

    def next(self) -> str | None:
        with self.lock:
            if not self.proxies:
                return None
            proxy = self.proxies[self.index % len(self.proxies)]
            self.index += 1
            return proxy


def configure_socket_proxy(use_proxy: bool, proxy_url: str) -> None:
    with SOCKET_PROXY_LOCK:
        if use_proxy:
            proxy_type, host, port, rdns, username, password = parse_socks_proxy(proxy_url)
            socks.setdefaultproxy(proxy_type, host, port, rdns=rdns, username=username, password=password)
            socket.socket = socks.socksocket
            socket.create_connection = socks_create_connection
        else:
            socks.setdefaultproxy()
            socket.socket = ORIGINAL_SOCKET
            socket.create_connection = ORIGINAL_CREATE_CONNECTION


def socks_create_connection(address, timeout=None, source_address=None):
    host, port = address
    sock = socks.socksocket()
    if timeout is not None:
        sock.settimeout(timeout)
    if source_address:
        sock.bind(source_address)
    sock.connect((host, port))
    return sock


def tcp_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with ORIGINAL_CREATE_CONNECTION((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def launch_tor_process(
    tor_exe: Path,
    proxy_url: str,
    data_dir: Path,
    timeout: float,
    log,
    stop_event: threading.Event | None = None,
) -> subprocess.Popen | None:
    if not tor_exe.exists():
        raise FileNotFoundError(f"No existe tor.exe: {tor_exe}")
    _, host, port, _, _, _ = parse_socks_proxy(proxy_url)
    if tcp_port_open(host, port):
        log(f"[TOR] {host}:{port} ya esta escuchando; reutilizando Tor/proxy SOCKS existente")
        return None
    data_dir.mkdir(parents=True, exist_ok=True)
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.Popen(
        [
            str(tor_exe),
            "--SocksPort",
            f"{host}:{port} IsolateSOCKSAuth",
            "--DataDirectory",
            str(data_dir),
            "--ClientOnly",
            "1",
            "--SafeSocks",
            "1",
            "--TestSocks",
            "1",
            "--AvoidDiskWrites",
            "1",
            "--CircuitBuildTimeout",
            "30",
            "--MaxCircuitDirtiness",
            "600",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        cwd=str(tor_exe.parent),
        creationflags=creationflags,
    )
    deadline = time.time() + timeout
    recent: list[str] = []
    while time.time() < deadline:
        if stop_event and stop_event.is_set():
            process.terminate()
            raise Cancelled()
        if process.poll() is not None:
            raise RuntimeError("Tor se cerro antes de conectar. " + "".join(recent[-20:]))
        line = process.stdout.readline() if process.stdout else ""
        if line:
            recent.append(line)
            log(f"[TOR] {line.strip()}")
            if "Bootstrapped 100%" in line:
                return process
        else:
            time.sleep(0.1)
    process.terminate()
    raise TimeoutError(f"Tor no llego a Bootstrapped 100% en {timeout:.0f}s")


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        for key, value in attrs:
            if key.lower() == "href" and value:
                self.links.append(value)


@dataclass
class Entry:
    url: str
    is_dir: bool
    size: int = 0
    last_modified: str = ""
    content_type: str = ""

    @property
    def ext(self) -> str:
        if self.is_dir:
            return ""
        return Path(urlparse(self.url).path).suffix.lower() or "[sin extension]"


def clean_url(url: str) -> str:
    clean, _ = urldefrag(url)
    return clean


def normalize_base_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("URL invalida. Usa http:// o https://")
    if not url.endswith("/") and Path(parsed.path).suffix == "":
        url += "/"
    return url


def parse_extensions(raw: str) -> set[str]:
    exts = set()
    for item in re.split(r"[,; ]+", raw.strip().lower()):
        if not item:
            continue
        exts.add(item if item.startswith(".") else "." + item)
    return exts


def parse_links(html: str, current_url: str) -> list[str]:
    parser = LinkParser()
    parser.feed(html)
    links = []
    for href in parser.links:
        href = href.strip()
        if not href or href.startswith(("#", "?", "mailto:", "javascript:")):
            continue
        if href in {"../", "..", "./"}:
            continue
        links.append(clean_url(urljoin(current_url, href)))
    return links


class DirectoryScanner:
    def __init__(
        self,
        base_url: str,
        exclude_exts: set[str],
        dir_threads: int,
        timeout: float,
        retries: int,
        verify_tls: bool,
        use_tor: bool,
        tor_proxy: str,
        start_tor: bool,
        use_http_proxies: bool,
        proxy_sources: list[str],
        no_leak: bool,
        user_agents: list[str],
        rotate_user_agents: bool,
        tor_exe: Path,
        tor_data_dir: Path,
        tor_bootstrap_timeout: float,
        event_queue: queue.Queue,
        stop_event: threading.Event,
    ) -> None:
        self.base_url = base_url
        self.base_parts = urlparse(base_url)
        self.exclude_exts = exclude_exts
        self.http_proxy_active = use_http_proxies and not is_onion_url(base_url)
        self.tor_active = (use_tor or start_tor) and not self.http_proxy_active
        self.source_tor_active = (
            no_leak and self.http_proxy_active and has_network_proxy_sources(proxy_sources) and (use_tor or start_tor)
        )
        self.no_leak = no_leak
        proxy_like = self.tor_active or self.http_proxy_active
        self.dir_threads = limit_tor_workers(dir_threads, proxy_like)
        self.requested_dir_threads = max(1, dir_threads)
        self.timeout = timeout
        self.retries = max(0, retries)
        self.verify_tls = verify_tls
        self.use_tor = use_tor
        self.tor_proxy = add_tor_session_auth(tor_proxy) if (self.tor_active or self.source_tor_active) else tor_proxy
        self.start_tor = start_tor and (self.tor_active or self.source_tor_active)
        self.event_queue = event_queue
        self.stop_event = stop_event
        self.proxy_pool = HttpProxyPool(
            proxy_sources,
            timeout,
            lambda line: self.event_queue.put(("log", line)),
            self.tor_proxy if self.source_tor_active else None,
        ) if self.http_proxy_active else None
        self.tor_exe = tor_exe
        self.tor_data_dir = tor_data_dir
        self.tor_bootstrap_timeout = tor_bootstrap_timeout
        self.tor_process: subprocess.Popen | None = None
        self.user_agents = UserAgentRotator(user_agents, rotate_user_agents)
        self.dir_queue: queue.Queue[str | object] = queue.Queue()
        self.meta_queue: queue.Queue[Entry | object] = queue.Queue()
        self.lock = threading.Lock()
        self.metrics_lock = threading.Lock()
        self.started_at = time.time()
        self.metrics = {
            "dir_active": 0,
            "meta_active": 0,
            "dir_finished": 0,
            "meta_finished": 0,
            "threads_stopped": 0,
            "requests_ok": 0,
            "requests_fail": 0,
            "proxy_attempts": 0,
            "proxy_ok": 0,
            "proxy_fail": 0,
            "direct_or_tor_requests": 0,
        }
        self.seen_dirs = {base_url}
        self.files: dict[str, Entry] = {}
        self.dirs: dict[str, Entry] = {base_url: Entry(base_url, True)}
        self.failed = 0
        self.meta_failed = 0

    def allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        return (
            parsed.scheme in {"http", "https"}
            and parsed.netloc.lower() == self.base_parts.netloc.lower()
            and parsed.path.startswith(self.base_parts.path)
        )

    def excluded(self, url: str) -> bool:
        return Path(urlparse(url).path).suffix.lower() in self.exclude_exts

    def request(self, url: str) -> Request:
        return Request(url, headers={"User-Agent": self.user_agents.next()})

    def head_request(self, url: str) -> Request:
        request = Request(url, headers={"User-Agent": self.user_agents.next()})
        request.get_method = lambda: "HEAD"
        return request

    def ssl_context(self):
        if self.verify_tls:
            return None
        return tolerant_ssl_context()

    def open_url(self, url: str):
        last_error = None
        for attempt in range(self.retries + 1):
            if self.stop_event.is_set():
                raise Cancelled()
            try:
                return self.open_with_route(self.request(url))
            except (HTTPError, URLError, TimeoutError, OSError) as exc:
                last_error = exc
                if is_ssl_eof_error(exc):
                    try:
                        self.event_queue.put(("log", f"[TLS FALLBACK] {url} -> TLS EOF, probando modo tolerante"))
                        return self.open_with_route(self.request(url), tolerant_ssl_context())
                    except (HTTPError, URLError, TimeoutError, OSError) as tls_exc:
                        last_error = tls_exc
                    fallback = http_fallback_url(url)
                    if fallback:
                        try:
                            self.event_queue.put(("log", f"[TLS FALLBACK] {url} -> probando {fallback}"))
                            return self.open_with_route(self.request(fallback), None)
                        except (HTTPError, URLError, TimeoutError, OSError) as http_exc:
                            last_error = http_exc
                if attempt < self.retries:
                    time.sleep(min(2.0, 0.25 * (attempt + 1)))
        raise last_error or RuntimeError("Error desconocido")

    def open_head(self, url: str):
        last_error = None
        for attempt in range(self.retries + 1):
            if self.stop_event.is_set():
                raise Cancelled()
            try:
                return self.open_with_route(self.head_request(url))
            except (HTTPError, URLError, TimeoutError, OSError) as exc:
                last_error = exc
                if is_ssl_eof_error(exc):
                    try:
                        return self.open_with_route(self.head_request(url), tolerant_ssl_context())
                    except (HTTPError, URLError, TimeoutError, OSError) as tls_exc:
                        last_error = tls_exc
                    fallback = http_fallback_url(url)
                    if fallback:
                        try:
                            return self.open_with_route(self.head_request(fallback), None)
                        except (HTTPError, URLError, TimeoutError, OSError) as http_exc:
                            last_error = http_exc
                if attempt < self.retries:
                    time.sleep(min(2.0, 0.25 * (attempt + 1)))
        raise last_error or RuntimeError("Error desconocido")

    def open_with_route(self, request: Request, ssl_context_override=None):
        context = self.ssl_context() if ssl_context_override is None else ssl_context_override
        if not self.proxy_pool:
            if self.no_leak and not self.tor_active:
                raise URLError("Modo sin fugas: no hay proxy/Tor activo para esta URL")
            with self.metrics_lock:
                self.metrics["direct_or_tor_requests"] += 1
            try:
                response = urlopen(request, timeout=self.timeout, context=context)
                with self.metrics_lock:
                    self.metrics["requests_ok"] += 1
                return response
            except Exception:
                with self.metrics_lock:
                    self.metrics["requests_fail"] += 1
                raise
        errors: list[str] = []
        for _ in range(min(12, max(1, len(self.proxy_pool.proxies)))):
            if self.stop_event.is_set():
                raise Cancelled()
            proxy = self.proxy_pool.next()
            if not proxy:
                break
            try:
                with self.metrics_lock:
                    self.metrics["proxy_attempts"] += 1
                opener = opener_for_proxy(proxy, context)
                response = opener.open(request, timeout=self.timeout)
                with self.metrics_lock:
                    self.metrics["proxy_ok"] += 1
                    self.metrics["requests_ok"] += 1
                return response
            except Exception as exc:
                with self.metrics_lock:
                    self.metrics["proxy_fail"] += 1
                    self.metrics["requests_fail"] += 1
                errors.append(f"{proxy}: {exc}")
        raise URLError("Proxies fallaron: " + " | ".join(errors[-3:]))

    def status_snapshot(self, phase: str) -> dict[str, object]:
        meta_total = max(1, min(self.dir_threads * 2, 200))
        total_threads = self.dir_threads + meta_total
        with self.metrics_lock:
            metrics = dict(self.metrics)
        active = metrics["dir_active"] + metrics["meta_active"]
        return {
            "phase": phase,
            "uptime": time.time() - self.started_at,
            "threads_total": total_threads,
            "threads_active": active,
            "threads_waiting": max(0, total_threads - active - metrics["threads_stopped"]),
            "threads_finished": metrics["dir_finished"] + metrics["meta_finished"],
            "threads_stopped": metrics["threads_stopped"],
            "queue_dirs": self.dir_queue.qsize(),
            "queue_meta": self.meta_queue.qsize(),
            "queue_files": 0,
            "dirs": len(self.dirs),
            "files": len(self.files),
            "done": 0,
            "skipped": 0,
            "failed": self.failed + self.meta_failed,
            "mb": 0.0,
            "proxy_total": len(self.proxy_pool.proxies) if self.proxy_pool else 0,
            "proxy_attempts": metrics["proxy_attempts"],
            "proxy_ok": metrics["proxy_ok"],
            "proxy_fail": metrics["proxy_fail"],
            "requests_ok": metrics["requests_ok"],
            "requests_fail": metrics["requests_fail"],
            "route": "Proxies HTTP/HTTPS/SOCKS" if self.proxy_pool else ("Tor" if self.tor_active else "Directo"),
        }

    @staticmethod
    def drain_queue(items: queue.Queue) -> None:
        while True:
            try:
                items.get_nowait()
                items.task_done()
            except queue.Empty:
                return

    def worker(self) -> None:
        try:
            while True:
                try:
                    item = self.dir_queue.get(timeout=0.2)
                except queue.Empty:
                    if self.stop_event.is_set():
                        return
                    continue
                try:
                    if item is STOP:
                        return
                    if self.stop_event.is_set():
                        continue
                    with self.metrics_lock:
                        self.metrics["dir_active"] += 1
                    try:
                        self.scan_dir(str(item))
                    finally:
                        with self.metrics_lock:
                            self.metrics["dir_active"] -= 1
                            self.metrics["dir_finished"] += 1
                finally:
                    self.dir_queue.task_done()
        finally:
            with self.metrics_lock:
                self.metrics["threads_stopped"] += 1

    def scan_dir(self, url: str) -> None:
        try:
            with self.open_url(url) as response:
                html = response.read().decode("utf-8", errors="ignore")
                tag = detect_server_tag(html, response.headers)
            if tag:
                self.event_queue.put(("log", f"[DIR TAG] {url} -> {tag}"))
            found_links = 0
            for child in parse_links(html, url):
                if self.stop_event.is_set():
                    return
                if not self.allowed(child):
                    continue
                found_links += 1
                if child.endswith("/"):
                    with self.lock:
                        if child in self.seen_dirs:
                            continue
                        self.seen_dirs.add(child)
                        self.dirs[child] = Entry(child, True)
                    self.dir_queue.put(child)
                    self.event_queue.put(("entry", self.dirs[child]))
                elif not self.excluded(child):
                    with self.lock:
                        if child in self.files:
                            continue
                        self.files[child] = Entry(child, False)
                        self.meta_queue.put(self.files[child])
                    self.event_queue.put(("entry", self.files[child]))
            if tag == "LiteSpeed" and found_links == 0:
                self.event_queue.put(("log", f"[DIR INFO] {url} -> LiteSpeed visible sin enlaces descargables"))
            self.event_queue.put(("progress", self.counts()))
        except Exception as exc:
            self.failed += 1
            self.event_queue.put(("log", f"[DIR FAIL] {url} -> {exc}"))

    def meta_worker(self) -> None:
        try:
            while True:
                try:
                    item = self.meta_queue.get(timeout=0.2)
                except queue.Empty:
                    if self.stop_event.is_set():
                        return
                    continue
                try:
                    if item is STOP:
                        return
                    if self.stop_event.is_set():
                        continue
                    entry = item
                    with self.metrics_lock:
                        self.metrics["meta_active"] += 1
                    try:
                        try:
                            with self.open_head(entry.url) as response:
                                entry.size = int(response.headers.get("Content-Length", "0") or 0)
                                entry.last_modified = response.headers.get("Last-Modified", "")
                                entry.content_type = response.headers.get("Content-Type", "")
                            self.event_queue.put(("meta", entry))
                            self.event_queue.put(("progress", self.counts()))
                        except Exception:
                            self.meta_failed += 1
                    finally:
                        with self.metrics_lock:
                            self.metrics["meta_active"] -= 1
                            self.metrics["meta_finished"] += 1
                finally:
                    self.meta_queue.task_done()
        finally:
            with self.metrics_lock:
                self.metrics["threads_stopped"] += 1

    def counts(self) -> tuple[int, int, int, int]:
        return len(self.dirs), len(self.files), self.failed + self.meta_failed, (
            self.dir_queue.qsize() + self.meta_queue.qsize()
        )

    def run(self) -> None:
        try:
            if self.start_tor:
                self.event_queue.put(("log", f"[TOR] Arrancando {self.tor_exe}"))
                self.tor_process = launch_tor_process(
                    self.tor_exe,
                    self.tor_proxy,
                    self.tor_data_dir,
                    self.tor_bootstrap_timeout,
                    lambda line: self.event_queue.put(("log", line)),
                    self.stop_event,
                )
            if self.proxy_pool:
                self.proxy_pool.load()
                if not self.proxy_pool.proxies:
                    raise RuntimeError("No hay proxies validos cargados")
                self.event_queue.put(("log", "[PROXY] Usando proxies HTTP/HTTPS/SOCKS para clearnet/IP"))
            configure_socket_proxy(self.tor_active, self.tor_proxy)
            self.event_queue.put(("log", f"[UA] Rotacion {'activa' if self.user_agents.rotate else 'fija'}: {len(self.user_agents.agents)} User-Agents"))
            if (self.tor_active or self.http_proxy_active) and self.dir_threads < self.requested_dir_threads:
                self.event_queue.put(("log", f"[PROXY] Hilos dirs limitados a {self.dir_threads}"))
            self.event_queue.put(("entry", self.dirs[self.base_url]))
            self.dir_queue.put(self.base_url)
            threads = [threading.Thread(target=self.worker, daemon=True) for _ in range(self.dir_threads)]
            meta_threads = [
                threading.Thread(target=self.meta_worker, daemon=True)
                for _ in range(max(1, min(self.dir_threads * 2, 200)))
            ]
            for thread in threads:
                thread.start()
            for thread in meta_threads:
                thread.start()
            last_status = 0.0
            while not self.stop_event.is_set():
                if self.dir_queue.unfinished_tasks == 0 and self.meta_queue.unfinished_tasks == 0:
                    break
                if time.time() - last_status >= 0.5:
                    self.event_queue.put(("runtime_status", self.status_snapshot("Escaneo")))
                    last_status = time.time()
                time.sleep(0.1)
            if self.stop_event.is_set():
                self.drain_queue(self.dir_queue)
                self.drain_queue(self.meta_queue)
                self.event_queue.put(("runtime_status", self.status_snapshot("Escaneo parado")))
                self.event_queue.put(("scan_stopped", self.counts(), list(self.files.values())))
                return
            for _ in threads:
                self.dir_queue.put(STOP)
            for _ in meta_threads:
                self.meta_queue.put(STOP)
            self.dir_queue.join()
            self.meta_queue.join()
            event = "scan_stopped" if self.stop_event.is_set() else "scan_done"
            self.event_queue.put(("runtime_status", self.status_snapshot("Escaneo terminado")))
            self.event_queue.put((event, self.counts(), list(self.files.values())))
        except Cancelled:
            self.event_queue.put(("scan_stopped", self.counts(), list(self.files.values())))
        except Exception as exc:
            self.event_queue.put(("log", f"[TOR/SCAN FAIL] {exc}"))
            self.event_queue.put(("scan_stopped", self.counts(), list(self.files.values())))
        finally:
            if self.tor_process and self.tor_process.poll() is None:
                self.tor_process.terminate()


class FileDownloader:
    def __init__(
        self,
        base_url: str,
        files: list[Entry],
        output_dir: Path,
        threads: int,
        timeout: float,
        retries: int,
        overwrite: bool,
        verify_tls: bool,
        quarantine_dangerous: bool,
        use_tor: bool,
        tor_proxy: str,
        start_tor: bool,
        use_http_proxies: bool,
        proxy_sources: list[str],
        no_leak: bool,
        user_agents: list[str],
        rotate_user_agents: bool,
        tor_exe: Path,
        tor_data_dir: Path,
        tor_bootstrap_timeout: float,
        event_queue: queue.Queue,
        stop_event: threading.Event,
    ) -> None:
        self.base_url = base_url
        self.base_parts = urlparse(base_url)
        self.files = files
        self.output_dir = output_dir
        self.http_proxy_active = use_http_proxies and not is_onion_url(base_url)
        self.tor_active = (use_tor or start_tor) and not self.http_proxy_active
        self.source_tor_active = (
            no_leak and self.http_proxy_active and has_network_proxy_sources(proxy_sources) and (use_tor or start_tor)
        )
        self.no_leak = no_leak
        proxy_like = self.tor_active or self.http_proxy_active
        self.threads = limit_tor_workers(threads, proxy_like)
        self.requested_threads = max(1, threads)
        self.timeout = timeout
        self.retries = max(0, retries)
        self.overwrite = overwrite
        self.verify_tls = verify_tls
        self.quarantine_dangerous = quarantine_dangerous
        self.use_tor = use_tor
        self.tor_proxy = add_tor_session_auth(tor_proxy) if (self.tor_active or self.source_tor_active) else tor_proxy
        self.start_tor = start_tor and (self.tor_active or self.source_tor_active)
        self.tor_exe = tor_exe
        self.tor_data_dir = tor_data_dir
        self.tor_bootstrap_timeout = tor_bootstrap_timeout
        self.tor_process: subprocess.Popen | None = None
        self.user_agents = UserAgentRotator(user_agents, rotate_user_agents)
        self.event_queue = event_queue
        self.stop_event = stop_event
        self.proxy_pool = HttpProxyPool(
            proxy_sources,
            timeout,
            lambda line: self.event_queue.put(("log", line)),
            self.tor_proxy if self.source_tor_active else None,
        ) if self.http_proxy_active else None
        self.file_queue: queue.Queue[Entry | object] = queue.Queue()
        self.lock = threading.Lock()
        self.metrics_lock = threading.Lock()
        self.started_at = time.time()
        self.metrics = {
            "download_active": 0,
            "download_finished": 0,
            "threads_stopped": 0,
            "requests_ok": 0,
            "requests_fail": 0,
            "proxy_attempts": 0,
            "proxy_ok": 0,
            "proxy_fail": 0,
            "direct_or_tor_requests": 0,
        }
        self.index_rows: list[dict[str, str | int]] = []
        self.done = 0
        self.failed = 0
        self.skipped = 0
        self.bytes = 0

    def request(self, url: str) -> Request:
        return Request(url, headers={"User-Agent": self.user_agents.next()})

    def ssl_context(self):
        if self.verify_tls:
            return None
        return tolerant_ssl_context()

    def open_url(self, url: str):
        last_error = None
        for attempt in range(self.retries + 1):
            if self.stop_event.is_set():
                raise Cancelled()
            try:
                return self.open_with_route(self.request(url))
            except (HTTPError, URLError, TimeoutError, OSError) as exc:
                last_error = exc
                if is_ssl_eof_error(exc):
                    try:
                        self.event_queue.put(("log", f"[TLS FALLBACK] {url} -> TLS EOF, probando modo tolerante"))
                        return self.open_with_route(self.request(url), tolerant_ssl_context())
                    except (HTTPError, URLError, TimeoutError, OSError) as tls_exc:
                        last_error = tls_exc
                    fallback = http_fallback_url(url)
                    if fallback:
                        try:
                            self.event_queue.put(("log", f"[TLS FALLBACK] {url} -> probando {fallback}"))
                            return self.open_with_route(self.request(fallback), None)
                        except (HTTPError, URLError, TimeoutError, OSError) as http_exc:
                            last_error = http_exc
                if attempt < self.retries:
                    time.sleep(min(2.0, 0.25 * (attempt + 1)))
        raise last_error or RuntimeError("Error desconocido")

    def open_with_route(self, request: Request, ssl_context_override=None):
        context = self.ssl_context() if ssl_context_override is None else ssl_context_override
        if not self.proxy_pool:
            if self.no_leak and not self.tor_active:
                raise URLError("Modo sin fugas: no hay proxy/Tor activo para esta URL")
            with self.metrics_lock:
                self.metrics["direct_or_tor_requests"] += 1
            try:
                response = urlopen(request, timeout=self.timeout, context=context)
                with self.metrics_lock:
                    self.metrics["requests_ok"] += 1
                return response
            except Exception:
                with self.metrics_lock:
                    self.metrics["requests_fail"] += 1
                raise
        errors: list[str] = []
        for _ in range(min(12, max(1, len(self.proxy_pool.proxies)))):
            if self.stop_event.is_set():
                raise Cancelled()
            proxy = self.proxy_pool.next()
            if not proxy:
                break
            try:
                with self.metrics_lock:
                    self.metrics["proxy_attempts"] += 1
                opener = opener_for_proxy(proxy, context)
                response = opener.open(request, timeout=self.timeout)
                with self.metrics_lock:
                    self.metrics["proxy_ok"] += 1
                    self.metrics["requests_ok"] += 1
                return response
            except Exception as exc:
                with self.metrics_lock:
                    self.metrics["proxy_fail"] += 1
                    self.metrics["requests_fail"] += 1
                errors.append(f"{proxy}: {exc}")
        raise URLError("Proxies fallaron: " + " | ".join(errors[-3:]))

    def status_snapshot(self, phase: str) -> dict[str, object]:
        with self.metrics_lock:
            metrics = dict(self.metrics)
        with self.lock:
            done = self.done
            skipped = self.skipped
            failed = self.failed
            mb = self.bytes / 1024 / 1024
        active = metrics["download_active"]
        return {
            "phase": phase,
            "uptime": time.time() - self.started_at,
            "threads_total": self.threads,
            "threads_active": active,
            "threads_waiting": max(0, self.threads - active - metrics["threads_stopped"]),
            "threads_finished": metrics["download_finished"],
            "threads_stopped": metrics["threads_stopped"],
            "queue_dirs": 0,
            "queue_meta": 0,
            "queue_files": self.file_queue.qsize(),
            "dirs": 0,
            "files": len(self.files),
            "done": done,
            "skipped": skipped,
            "failed": failed,
            "mb": mb,
            "proxy_total": len(self.proxy_pool.proxies) if self.proxy_pool else 0,
            "proxy_attempts": metrics["proxy_attempts"],
            "proxy_ok": metrics["proxy_ok"],
            "proxy_fail": metrics["proxy_fail"],
            "requests_ok": metrics["requests_ok"],
            "requests_fail": metrics["requests_fail"],
            "route": "Proxies HTTP/HTTPS/SOCKS" if self.proxy_pool else ("Tor" if self.tor_active else "Directo"),
        }

    @staticmethod
    def drain_queue(items: queue.Queue) -> None:
        while True:
            try:
                items.get_nowait()
                items.task_done()
            except queue.Empty:
                return

    def local_path_for(self, url: str) -> Path:
        rel_path = unquote(urlparse(url).path)
        if rel_path.startswith(self.base_parts.path):
            rel_path = rel_path[len(self.base_parts.path):]
        rel_path = rel_path.strip("/") or "index.html"
        rel_parts = [sanitize_path_part(part) for part in re.split(r"[\\/]+", rel_path) if part not in {"", ".", ".."}]
        rel_path = str(Path(*rel_parts)) if rel_parts else "index.html"
        if self.quarantine_dangerous and is_dangerous_url(url):
            rel_path = str(Path("_quarantine") / rel_path) + ".download"
        candidate = (self.output_dir / rel_path).resolve()
        root = self.output_dir.resolve()
        if not str(candidate).lower().startswith(str(root).lower()):
            digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
            candidate = root / f"unsafe-path-{digest}"
        return candidate

    def write_index(self) -> Path:
        index_path = self.output_dir / "_download_index.csv"
        index_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock:
            rows = list(self.index_rows)
        with index_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["url", "local_path", "size", "last_modified", "quarantined", "downloaded_at"],
            )
            writer.writeheader()
            writer.writerows(rows)
        return index_path

    def download_one(self, entry: Entry) -> None:
        path = self.local_path_for(entry.url)
        if path.exists() and not self.overwrite:
            with self.lock:
                self.skipped += 1
            return
        try:
            with self.open_url(entry.url) as response:
                last_modified = response.headers.get("Last-Modified", "")
                path.parent.mkdir(parents=True, exist_ok=True)
                temp_path = path.with_name(f"{path.name}.{threading.get_ident()}.part")
                total = 0
                try:
                    with temp_path.open("wb") as handle:
                        while True:
                            if self.stop_event.is_set():
                                raise Cancelled()
                            chunk = response.read(1024 * 512)
                            if not chunk:
                                break
                            handle.write(chunk)
                            total += len(chunk)
                    if path.exists() and not self.overwrite:
                        temp_path.unlink(missing_ok=True)
                        with self.lock:
                            self.skipped += 1
                        return
                    temp_path.replace(path)
                    set_download_timestamp(path, last_modified)
                    mark_windows_download(path, entry.url)
                finally:
                    temp_path.unlink(missing_ok=True)
            with self.lock:
                self.done += 1
                self.bytes += total
                self.index_rows.append(
                    {
                        "url": entry.url,
                        "local_path": str(path.resolve()),
                        "size": total,
                        "last_modified": last_modified,
                        "quarantined": "yes" if self.quarantine_dangerous and is_dangerous_url(entry.url) else "",
                        "downloaded_at": datetime.now().isoformat(timespec="seconds"),
                    }
                )
        except Cancelled:
            with self.lock:
                self.skipped += 1
        except Exception as exc:
            with self.lock:
                self.failed += 1
            self.event_queue.put(("log", f"[FILE FAIL] {entry.url} -> {exc}"))

    def worker(self) -> None:
        try:
            while True:
                try:
                    item = self.file_queue.get(timeout=0.2)
                except queue.Empty:
                    if self.stop_event.is_set():
                        return
                    continue
                try:
                    if item is STOP:
                        return
                    if self.stop_event.is_set():
                        with self.lock:
                            self.skipped += 1
                        continue
                    with self.metrics_lock:
                        self.metrics["download_active"] += 1
                    try:
                        self.download_one(item)
                    finally:
                        with self.metrics_lock:
                            self.metrics["download_active"] -= 1
                            self.metrics["download_finished"] += 1
                    self.event_queue.put(("download_progress", self.counts()))
                finally:
                    self.file_queue.task_done()
        finally:
            with self.metrics_lock:
                self.metrics["threads_stopped"] += 1

    def counts(self) -> tuple[int, int, int, int, float]:
        with self.lock:
            return self.done, self.skipped, self.failed, len(self.files), self.bytes / 1024 / 1024

    def run(self) -> None:
        try:
            if self.start_tor:
                self.event_queue.put(("log", f"[TOR] Arrancando {self.tor_exe}"))
                self.tor_process = launch_tor_process(
                    self.tor_exe,
                    self.tor_proxy,
                    self.tor_data_dir,
                    self.tor_bootstrap_timeout,
                    lambda line: self.event_queue.put(("log", line)),
                    self.stop_event,
                )
            if self.proxy_pool:
                self.proxy_pool.load()
                if not self.proxy_pool.proxies:
                    raise RuntimeError("No hay proxies validos cargados")
                self.event_queue.put(("log", "[PROXY] Usando proxies HTTP/HTTPS/SOCKS para clearnet/IP"))
            configure_socket_proxy(self.tor_active, self.tor_proxy)
            self.event_queue.put(("log", f"[UA] Rotacion {'activa' if self.user_agents.rotate else 'fija'}: {len(self.user_agents.agents)} User-Agents"))
            if (self.tor_active or self.http_proxy_active) and self.threads < self.requested_threads:
                self.event_queue.put(("log", f"[PROXY] Hilos descarga limitados a {self.threads}"))
            self.output_dir.mkdir(parents=True, exist_ok=True)
            for entry in self.files:
                self.file_queue.put(entry)
            threads = [threading.Thread(target=self.worker, daemon=True) for _ in range(self.threads)]
            for thread in threads:
                thread.start()
            last_status = 0.0
            while not self.stop_event.is_set():
                if self.file_queue.unfinished_tasks == 0:
                    break
                if time.time() - last_status >= 0.5:
                    self.event_queue.put(("runtime_status", self.status_snapshot("Descarga")))
                    last_status = time.time()
                time.sleep(0.1)
            if self.stop_event.is_set():
                self.drain_queue(self.file_queue)
                index_path = self.write_index()
                self.event_queue.put(("runtime_status", self.status_snapshot("Descarga parada")))
                self.event_queue.put(("download_stopped", self.counts(), index_path))
                return
            for _ in threads:
                self.file_queue.put(STOP)
            self.file_queue.join()
            index_path = self.write_index()
            event = "download_stopped" if self.stop_event.is_set() else "download_done"
            self.event_queue.put(("runtime_status", self.status_snapshot("Descarga terminada")))
            self.event_queue.put((event, self.counts(), index_path))
        except Cancelled:
            index_path = self.write_index()
            self.event_queue.put(("download_stopped", self.counts(), index_path))
        except Exception as exc:
            self.event_queue.put(("log", f"[TOR/DOWNLOAD FAIL] {exc}"))
            index_path = self.write_index()
            self.event_queue.put(("download_stopped", self.counts(), index_path))
        finally:
            if self.tor_process and self.tor_process.poll() is None:
                self.tor_process.terminate()


class CalendarPopup(tk.Toplevel):
    def __init__(self, parent, target_var: tk.StringVar) -> None:
        super().__init__(parent)
        self.target_var = target_var
        self.title("Seleccionar fecha")
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())
        self.grab_set()

        initial = self.parse_initial(target_var.get())
        self.year = initial.year
        self.month = initial.month

        self.header = ttk.Frame(self, padding=(8, 8, 8, 2))
        self.header.pack(fill=tk.X)
        ttk.Button(self.header, text="<", width=3, command=self.prev_month).pack(side=tk.LEFT)
        self.title_var = tk.StringVar()
        ttk.Label(self.header, textvariable=self.title_var, anchor="center", width=20).pack(side=tk.LEFT, padx=6)
        ttk.Button(self.header, text=">", width=3, command=self.next_month).pack(side=tk.LEFT)

        self.days_frame = ttk.Frame(self, padding=8)
        self.days_frame.pack()
        footer = ttk.Frame(self, padding=(8, 0, 8, 8))
        footer.pack(fill=tk.X)
        ttk.Button(footer, text="Hoy", command=self.pick_today).pack(side=tk.LEFT)
        ttk.Button(footer, text="Limpiar", command=self.clear_date).pack(side=tk.LEFT, padx=6)
        ttk.Button(footer, text="Cerrar", command=self.destroy).pack(side=tk.RIGHT)
        self.render()

    @staticmethod
    def parse_initial(value: str) -> date:
        try:
            return datetime.strptime(value.strip(), "%Y-%m-%d").date()
        except ValueError:
            return date.today()

    def render(self) -> None:
        for child in self.days_frame.winfo_children():
            child.destroy()
        self.title_var.set(f"{calendar.month_name[self.month]} {self.year}")
        for col, name in enumerate(("Lu", "Ma", "Mi", "Ju", "Vi", "Sa", "Do")):
            ttk.Label(self.days_frame, text=name, anchor="center", width=4).grid(row=0, column=col, padx=1, pady=1)
        today = date.today()
        selected = self.parse_initial(self.target_var.get())
        for row, week in enumerate(calendar.monthcalendar(self.year, self.month), start=1):
            for col, day in enumerate(week):
                if day == 0:
                    ttk.Label(self.days_frame, text="", width=4).grid(row=row, column=col, padx=1, pady=1)
                    continue
                current = date(self.year, self.month, day)
                label = f"{day:02d}"
                if current == today:
                    label = f"*{day:02d}"
                if current == selected:
                    label = f"[{day:02d}]"
                ttk.Button(
                    self.days_frame,
                    text=label,
                    width=4,
                    command=lambda picked=current: self.pick_date(picked),
                ).grid(row=row, column=col, padx=1, pady=1)

    def prev_month(self) -> None:
        if self.month == 1:
            self.month = 12
            self.year -= 1
        else:
            self.month -= 1
        self.render()

    def next_month(self) -> None:
        if self.month == 12:
            self.month = 1
            self.year += 1
        else:
            self.month += 1
        self.render()

    def pick_date(self, picked: date) -> None:
        self.target_var.set(picked.isoformat())
        self.destroy()

    def pick_today(self) -> None:
        self.pick_date(date.today())

    def clear_date(self) -> None:
        self.target_var.set("")
        self.destroy()


class DateSelector(ttk.Frame):
    def __init__(self, parent, textvariable: tk.StringVar, width: int = 11) -> None:
        super().__init__(parent)
        self.textvariable = textvariable
        self.entry = ttk.Entry(self, textvariable=textvariable, width=width, state="readonly")
        self.entry.pack(side=tk.LEFT)
        ttk.Button(self, text="Cal", width=4, command=self.open_calendar).pack(side=tk.LEFT, padx=(2, 0))
        ttk.Button(self, text="X", width=2, command=self.clear).pack(side=tk.LEFT, padx=(2, 0))

    def open_calendar(self) -> None:
        CalendarPopup(self, self.textvariable)

    def clear(self) -> None:
        self.textvariable.set("")


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("OpenDir Downloader")
        self.geometry("1120x720")
        self.minsize(900, 560)
        icon_path = resource_path("opendir_downloader.ico")
        if icon_path.exists():
            self.iconbitmap(default=str(icon_path))

        self.events: queue.Queue = queue.Queue()
        self.stop_event = threading.Event()
        self.scanned_files: list[Entry] = []
        self.all_entries: dict[str, Entry] = {}
        self.nodes: dict[str, str] = {}
        self.excluded_download_urls: set[str] = set()
        self.scan_thread: threading.Thread | None = None
        self.download_thread: threading.Thread | None = None
        self.geo_cache: dict[str, dict[str, str]] = {}
        self.geo_lookup_job: str | None = None

        self.url_var = tk.StringVar()
        self.target_geo_var = tk.StringVar(value=f"{PIRATE_FLAG} Ubicacion: sin detectar")
        self.output_var = tk.StringVar(value=str(Path.cwd() / "mirror"))
        self.exclude_var = tk.StringVar(value=DEFAULT_EXCLUDES)
        self.dir_threads_var = tk.IntVar(value=40)
        self.file_threads_var = tk.IntVar(value=200)
        self.timeout_var = tk.DoubleVar(value=30.0)
        self.retries_var = tk.IntVar(value=2)
        self.overwrite_var = tk.BooleanVar(value=False)
        self.insecure_tls_var = tk.BooleanVar(value=True)
        self.quarantine_dangerous_var = tk.BooleanVar(value=True)
        self.use_tor_var = tk.BooleanVar(value=False)
        self.tor_proxy_var = tk.StringVar(value="socks5h://127.0.0.1:9050")
        self.start_tor_var = tk.BooleanVar(value=False)
        self.use_http_proxies_var = tk.BooleanVar(value=True)
        self.no_leak_var = tk.BooleanVar(value=True)
        self.rotate_user_agents_var = tk.BooleanVar(value=True)
        self.user_agents_value = DEFAULT_USER_AGENTS
        self.proxy_sources_var = tk.StringVar(value=";".join(DEFAULT_PROXY_SOURCES))
        self.tor_exe_var = tk.StringVar()
        self.tor_data_dir_var = tk.StringVar(value=str(Path.cwd() / ".tor-data"))
        self.tor_bootstrap_timeout_var = tk.DoubleVar(value=90.0)
        self.filter_ext_var = tk.StringVar()
        self.filter_mode_var = tk.StringVar(value="include")
        self.filter_min_mb_var = tk.StringVar()
        self.filter_max_mb_var = tk.StringVar()
        self.filter_date_mode_var = tk.StringVar(value="en fecha")
        self.filter_date_var = tk.StringVar()
        self.filter_date_to_var = tk.StringVar()
        self.filter_include_text_var = tk.StringVar()
        self.filter_exclude_text_var = tk.StringVar()

        self.load_config()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.build_ui()
        self.url_var.trace_add("write", lambda *_: self.schedule_target_geo_lookup())
        self.after(150, self.poll_events)

    def build_ui(self) -> None:
        controls = ttk.Frame(self, padding=10)
        controls.pack(fill=tk.X)
        controls.columnconfigure(1, weight=1)

        ttk.Label(controls, text="URL").grid(row=0, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.url_var).grid(row=0, column=1, columnspan=5, sticky="ew", padx=6)
        ttk.Button(controls, text="Escanear", command=self.start_scan).grid(row=0, column=6, padx=4)
        ttk.Button(controls, text="Descargar", command=self.start_download).grid(row=0, column=7, padx=4)
        ttk.Button(controls, text="Parar", command=self.stop_current).grid(row=0, column=8, padx=4)
        ttk.Button(controls, text="Copiar URL", command=self.copy_selected_url).grid(row=0, column=9, padx=4)
        ttk.Button(controls, text="Guardar config", command=self.save_config_clicked).grid(row=0, column=10, padx=4)
        ttk.Label(controls, textvariable=self.target_geo_var, anchor="e").grid(
            row=0, column=11, padx=(10, 0), sticky="e"
        )

        ttk.Label(controls, text="Salida").grid(row=1, column=0, sticky="w", pady=6)
        ttk.Entry(controls, textvariable=self.output_var).grid(row=1, column=1, columnspan=5, sticky="ew", padx=6)
        ttk.Button(controls, text="Carpeta", command=self.choose_output).grid(row=1, column=6, padx=4)
        ttk.Checkbutton(controls, text="Sobrescribir", variable=self.overwrite_var).grid(row=1, column=7, sticky="w")

        opts = ttk.Frame(controls)
        opts.grid(row=2, column=0, columnspan=9, sticky="ew", pady=(4, 0))
        for idx in range(12):
            opts.columnconfigure(idx, weight=0)
        ttk.Label(opts, text="Ext excluir").grid(row=0, column=0, sticky="w")
        ttk.Entry(opts, textvariable=self.exclude_var, width=22).grid(row=0, column=1, padx=6)
        ttk.Label(opts, text="Hilos dirs").grid(row=0, column=2)
        ttk.Spinbox(opts, textvariable=self.dir_threads_var, from_=1, to=500, width=7).grid(row=0, column=3, padx=6)
        ttk.Label(opts, text="Hilos descarga").grid(row=0, column=4)
        ttk.Spinbox(opts, textvariable=self.file_threads_var, from_=1, to=1000, width=7).grid(row=0, column=5, padx=6)
        ttk.Label(opts, text="Timeout").grid(row=0, column=6)
        ttk.Spinbox(opts, textvariable=self.timeout_var, from_=1, to=300, increment=1, width=7).grid(row=0, column=7, padx=6)
        ttk.Label(opts, text="Reintentos").grid(row=0, column=8)
        ttk.Spinbox(opts, textvariable=self.retries_var, from_=0, to=20, width=7).grid(row=0, column=9, padx=6)
        ttk.Checkbutton(opts, text="Ignorar errores SSL", variable=self.insecure_tls_var).grid(
            row=0, column=10, padx=8, sticky="w"
        )
        ttk.Checkbutton(opts, text="Cuarentena riesgo", variable=self.quarantine_dangerous_var).grid(
            row=0, column=11, padx=8, sticky="w"
        )
        ttk.Checkbutton(opts, text="Tor", variable=self.use_tor_var).grid(row=0, column=12, padx=4, sticky="w")
        ttk.Entry(opts, textvariable=self.tor_proxy_var, width=24).grid(row=0, column=13, padx=4)

        tor_opts = ttk.Frame(controls)
        tor_opts.grid(row=3, column=0, columnspan=13, sticky="ew", pady=(4, 0))
        tor_opts.columnconfigure(3, weight=1)
        ttk.Checkbutton(tor_opts, text="Arrancar tor.exe", variable=self.start_tor_var).grid(
            row=0, column=0, padx=(0, 6), sticky="w"
        )
        ttk.Label(tor_opts, text="tor.exe").grid(row=0, column=1, sticky="w")
        ttk.Entry(tor_opts, textvariable=self.tor_exe_var, width=42).grid(row=0, column=2, padx=4)
        ttk.Button(tor_opts, text="Buscar", command=self.choose_tor_exe).grid(row=0, column=3, sticky="w", padx=4)
        ttk.Label(tor_opts, text="Data").grid(row=0, column=4, sticky="e")
        ttk.Entry(tor_opts, textvariable=self.tor_data_dir_var, width=28).grid(row=0, column=5, padx=4)
        ttk.Label(tor_opts, text="Timeout").grid(row=0, column=6)
        ttk.Spinbox(tor_opts, textvariable=self.tor_bootstrap_timeout_var, from_=10, to=300, width=7).grid(
            row=0, column=7, padx=4
        )
        ttk.Checkbutton(tor_opts, text="Proxies clearnet", variable=self.use_http_proxies_var).grid(
            row=1, column=0, padx=(0, 6), pady=(4, 0), sticky="w"
        )
        ttk.Label(tor_opts, text="Fuentes").grid(row=1, column=1, sticky="w", pady=(4, 0))
        ttk.Entry(tor_opts, textvariable=self.proxy_sources_var, width=95).grid(
            row=1, column=2, columnspan=6, sticky="ew", padx=4, pady=(4, 0)
        )
        ttk.Checkbutton(tor_opts, text="Sin IP leak", variable=self.no_leak_var).grid(
            row=1, column=8, padx=8, pady=(4, 0), sticky="w"
        )
        ttk.Checkbutton(tor_opts, text="Rotar UA", variable=self.rotate_user_agents_var).grid(
            row=1, column=9, padx=4, pady=(4, 0), sticky="w"
        )
        ttk.Button(tor_opts, text="User-Agents", command=self.edit_user_agents).grid(
            row=1, column=10, padx=4, pady=(4, 0), sticky="w"
        )

        filters = ttk.Frame(controls)
        filters.grid(row=4, column=0, columnspan=13, sticky="ew", pady=(8, 0))
        ttk.Label(filters, text="Extensiones").grid(row=0, column=0, sticky="w")
        ttk.Entry(filters, textvariable=self.filter_ext_var, width=18).grid(row=0, column=1, padx=6)
        ttk.Radiobutton(filters, text="Solo esas", variable=self.filter_mode_var, value="include").grid(
            row=0, column=2
        )
        ttk.Radiobutton(filters, text="Excluir esas", variable=self.filter_mode_var, value="exclude").grid(
            row=0, column=3
        )
        ttk.Label(filters, text="Min MB").grid(row=0, column=4)
        ttk.Entry(filters, textvariable=self.filter_min_mb_var, width=10).grid(row=0, column=5, padx=6)
        ttk.Label(filters, text="Max MB").grid(row=0, column=6)
        ttk.Entry(filters, textvariable=self.filter_max_mb_var, width=10).grid(row=0, column=7, padx=6)
        ttk.Label(filters, text="Fecha").grid(row=0, column=8)
        ttk.Combobox(
            filters,
            textvariable=self.filter_date_mode_var,
            values=("en fecha", "entre", "antes", "despues"),
            state="readonly",
            width=10,
        ).grid(row=0, column=9, padx=4)
        DateSelector(filters, self.filter_date_var).grid(row=0, column=10, padx=4)
        ttk.Label(filters, text="hasta").grid(row=0, column=11)
        DateSelector(filters, self.filter_date_to_var).grid(row=0, column=12, padx=4)
        ttk.Button(filters, text="Aplicar", command=self.apply_filter).grid(row=0, column=13, padx=4)
        ttk.Button(filters, text="Limpiar", command=self.clear_filter).grid(row=0, column=14, padx=4)
        ttk.Label(filters, text="Incl texto").grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Entry(filters, textvariable=self.filter_include_text_var, width=42).grid(
            row=1, column=1, columnspan=4, sticky="ew", padx=6, pady=(4, 0)
        )
        ttk.Label(filters, text="Excl texto").grid(row=1, column=5, sticky="e", pady=(4, 0))
        ttk.Entry(filters, textvariable=self.filter_exclude_text_var, width=42).grid(
            row=1, column=6, columnspan=4, sticky="ew", padx=6, pady=(4, 0)
        )
        ttk.Button(filters, text="Seleccionar visibles", command=self.select_visible).grid(
            row=1, column=10, columnspan=2, padx=4, pady=(4, 0)
        )
        ttk.Button(filters, text="Deseleccionar visibles", command=self.deselect_visible).grid(
            row=1, column=12, columnspan=3, padx=4, pady=(4, 0)
        )

        body = ttk.PanedWindow(self, orient=tk.VERTICAL)
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        tree_frame = ttk.Frame(body)
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(
            tree_frame,
            columns=("selected", "type", "ext", "size", "date", "url"),
            show="tree headings",
        )
        self.checkbox_images = self.create_checkbox_images()
        self.tree.heading("#0", text="Estructura")
        self.tree.heading("selected", text="")
        self.tree.heading("type", text="Tipo")
        self.tree.heading("ext", text="Ext")
        self.tree.heading("size", text="Tamaño")
        self.tree.heading("date", text="Fecha")
        self.tree.heading("url", text="URL")
        self.tree.column("#0", width=360)
        self.tree.column("selected", width=0, minwidth=0, stretch=False, anchor="center")
        self.tree.column("type", width=90, stretch=False)
        self.tree.column("ext", width=90, stretch=False)
        self.tree.column("size", width=110, stretch=False, anchor="e")
        self.tree.column("date", width=220, stretch=False)
        self.tree.column("url", width=520)
        yscroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<Control-c>", self.copy_selected_url)
        self.tree.bind("<Control-C>", self.copy_selected_url)
        self.tree.bind("<space>", self.toggle_selected_item)
        self.tree.bind("<Button-1>", self.on_tree_click)
        self.tree.bind("<Double-1>", self.on_tree_double_click)
        self.tree.bind("<Button-3>", self.show_tree_menu)
        self.tree_menu = tk.Menu(self, tearoff=False)
        self.tree_menu.add_command(label="Copiar URL", command=self.copy_selected_url)
        self.tree_menu.add_separator()
        self.tree_menu.add_command(label="Seleccionar para descargar", command=self.select_selected_item)
        self.tree_menu.add_command(label="Deseleccionar para descargar", command=self.deselect_selected_item)
        body.add(tree_frame, weight=4)

        lower = ttk.PanedWindow(body, orient=tk.HORIZONTAL)
        runtime_frame = ttk.Frame(lower)
        runtime_frame.columnconfigure(0, weight=1)
        runtime_frame.rowconfigure(0, weight=1)
        self.runtime_text = tk.Text(runtime_frame, height=8, width=42, wrap="none")
        runtime_scroll = ttk.Scrollbar(runtime_frame, orient=tk.VERTICAL, command=self.runtime_text.yview)
        self.runtime_text.configure(yscrollcommand=runtime_scroll.set)
        self.runtime_text.grid(row=0, column=0, sticky="nsew")
        runtime_scroll.grid(row=0, column=1, sticky="ns")
        lower.add(runtime_frame, weight=1)

        stats_frame = ttk.Frame(lower)
        stats_frame.columnconfigure(0, weight=1)
        stats_frame.rowconfigure(0, weight=1)
        self.stats_text = tk.Text(stats_frame, height=8, wrap="none")
        stats_scroll = ttk.Scrollbar(stats_frame, orient=tk.VERTICAL, command=self.stats_text.yview)
        self.stats_text.configure(yscrollcommand=stats_scroll.set)
        self.stats_text.grid(row=0, column=0, sticky="nsew")
        stats_scroll.grid(row=0, column=1, sticky="ns")
        lower.add(stats_frame, weight=1)

        log_frame = ttk.Frame(lower)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log_text = tk.Text(log_frame, height=8, wrap="word")
        log_scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        log_scroll.grid(row=0, column=1, sticky="ns")
        lower.add(log_frame, weight=2)
        body.add(lower, weight=1)

        self.status_var = tk.StringVar(value="Listo")
        ttk.Label(self, textvariable=self.status_var, anchor="w").pack(fill=tk.X, padx=10, pady=(0, 8))

    def config_data(self) -> dict[str, object]:
        return {
            "output": self.output_var.get(),
            "exclude_exts": self.exclude_var.get(),
            "dir_threads": self.dir_threads_var.get(),
            "file_threads": self.file_threads_var.get(),
            "timeout": self.timeout_var.get(),
            "retries": self.retries_var.get(),
            "overwrite": self.overwrite_var.get(),
            "ignore_ssl_errors": self.insecure_tls_var.get(),
            "quarantine_dangerous": self.quarantine_dangerous_var.get(),
            "use_tor": self.use_tor_var.get(),
            "tor_proxy": self.tor_proxy_var.get(),
            "start_tor": self.start_tor_var.get(),
            "use_proxies": self.use_http_proxies_var.get(),
            "no_leak": self.no_leak_var.get(),
            "rotate_user_agents": self.rotate_user_agents_var.get(),
            "user_agents": self.user_agents_value,
            "proxy_sources": self.proxy_sources_var.get(),
            "tor_exe": self.tor_exe_var.get(),
            "tor_data_dir": self.tor_data_dir_var.get(),
            "tor_bootstrap_timeout": self.tor_bootstrap_timeout_var.get(),
        }

    def load_config(self) -> None:
        path = config_path()
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return
            self.output_var.set(str(data.get("output", self.output_var.get())))
            self.exclude_var.set(str(data.get("exclude_exts", self.exclude_var.get())))
            self.dir_threads_var.set(int(data.get("dir_threads", self.dir_threads_var.get())))
            self.file_threads_var.set(int(data.get("file_threads", self.file_threads_var.get())))
            self.timeout_var.set(float(data.get("timeout", self.timeout_var.get())))
            self.retries_var.set(int(data.get("retries", self.retries_var.get())))
            self.overwrite_var.set(bool(data.get("overwrite", self.overwrite_var.get())))
            self.insecure_tls_var.set(bool(data.get("ignore_ssl_errors", self.insecure_tls_var.get())))
            self.quarantine_dangerous_var.set(bool(data.get("quarantine_dangerous", self.quarantine_dangerous_var.get())))
            self.use_tor_var.set(bool(data.get("use_tor", self.use_tor_var.get())))
            self.tor_proxy_var.set(str(data.get("tor_proxy", self.tor_proxy_var.get())))
            self.start_tor_var.set(bool(data.get("start_tor", self.start_tor_var.get())))
            self.use_http_proxies_var.set(bool(data.get("use_proxies", self.use_http_proxies_var.get())))
            self.no_leak_var.set(bool(data.get("no_leak", self.no_leak_var.get())))
            self.rotate_user_agents_var.set(bool(data.get("rotate_user_agents", self.rotate_user_agents_var.get())))
            self.user_agents_value = str(data.get("user_agents", self.user_agents_value))
            self.proxy_sources_var.set(str(data.get("proxy_sources", self.proxy_sources_var.get())))
            self.tor_exe_var.set(str(data.get("tor_exe", self.tor_exe_var.get())))
            self.tor_data_dir_var.set(str(data.get("tor_data_dir", self.tor_data_dir_var.get())))
            self.tor_bootstrap_timeout_var.set(float(data.get("tor_bootstrap_timeout", self.tor_bootstrap_timeout_var.get())))
        except Exception:
            return

    def save_config(self) -> Path:
        path = config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.config_data(), indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def save_config_clicked(self) -> None:
        try:
            path = self.save_config()
            self.status_var.set(f"Config guardada: {path}")
        except Exception as exc:
            messagebox.showerror("Config", f"No se pudo guardar la configuracion: {exc}")

    def on_close(self) -> None:
        try:
            self.save_config()
        except Exception:
            pass
        self.stop_event.set()
        self.destroy()

    def choose_output(self) -> None:
        folder = filedialog.askdirectory(initialdir=self.output_var.get() or str(Path.cwd()))
        if folder:
            self.output_var.set(folder)

    def choose_tor_exe(self) -> None:
        path = filedialog.askopenfilename(
            title="Selecciona tor.exe",
            filetypes=[("tor.exe", "tor.exe"), ("Executable files", "*.exe"), ("All files", "*.*")],
        )
        if path:
            self.tor_exe_var.set(path)

    def edit_user_agents(self) -> None:
        window = tk.Toplevel(self)
        window.title("User-Agents")
        window.geometry("900x520")
        window.transient(self)
        window.grab_set()
        frame = ttk.Frame(window, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        text = scrolledtext.ScrolledText(frame, wrap=tk.NONE, height=20)
        text.grid(row=0, column=0, columnspan=4, sticky="nsew")
        text.insert("1.0", self.user_agents_value)
        count_var = tk.StringVar(value=f"{len(parse_user_agents(self.user_agents_value))} User-Agents")
        ttk.Label(frame, textvariable=count_var).grid(row=1, column=0, sticky="w", pady=(8, 0))

        def refresh_count() -> None:
            count_var.set(f"{len(parse_user_agents(text.get('1.0', tk.END)))} User-Agents")

        def restore_defaults() -> None:
            text.delete("1.0", tk.END)
            text.insert("1.0", DEFAULT_USER_AGENTS)
            refresh_count()

        def save() -> None:
            value = text.get("1.0", tk.END).strip() + "\n"
            if not parse_user_agents(value):
                messagebox.showerror("User-Agents", "La lista no puede estar vacia.")
                return
            self.user_agents_value = value
            window.destroy()

        ttk.Button(frame, text="Contar", command=refresh_count).grid(row=1, column=1, padx=4, pady=(8, 0), sticky="e")
        ttk.Button(frame, text="Restaurar", command=restore_defaults).grid(row=1, column=2, padx=4, pady=(8, 0), sticky="e")
        ttk.Button(frame, text="Guardar", command=save).grid(row=1, column=3, padx=4, pady=(8, 0), sticky="e")

    def log(self, message: str) -> None:
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)

    def create_checkbox_images(self) -> dict[str, tk.PhotoImage]:
        def make(state: str) -> tk.PhotoImage:
            image = tk.PhotoImage(width=16, height=16)
            image.put("#ffffff", to=(0, 0, 16, 16))
            image.put("#5f6368", to=(2, 2, 14, 3))
            image.put("#5f6368", to=(2, 13, 14, 14))
            image.put("#5f6368", to=(2, 2, 3, 14))
            image.put("#5f6368", to=(13, 2, 14, 14))
            if state == "checked":
                for x, y in [(4, 8), (5, 9), (6, 10), (7, 9), (8, 8), (9, 7), (10, 6), (11, 5)]:
                    image.put("#0b57d0", to=(x, y, x + 2, y + 2))
            elif state == "mixed":
                image.put("#0b57d0", to=(4, 7, 12, 10))
            return image

        return {
            "checked": make("checked"),
            "unchecked": make("unchecked"),
            "mixed": make("mixed"),
            "empty": tk.PhotoImage(width=16, height=16),
        }

    def render_runtime_status(self, snapshot: dict[str, object]) -> None:
        uptime = float(snapshot.get("uptime", 0.0))
        lines = [
            f"Fase: {snapshot.get('phase', '')}",
            f"Tiempo: {uptime:0.1f}s",
            f"Ruta: {snapshot.get('route', '')}",
            "",
            "Threads",
            f"  Total:       {snapshot.get('threads_total', 0)}",
            f"  Activos:     {snapshot.get('threads_active', 0)}",
            f"  En espera:   {snapshot.get('threads_waiting', 0)}",
            f"  Finalizados: {snapshot.get('threads_finished', 0)}",
            f"  Parados:     {snapshot.get('threads_stopped', 0)}",
            "",
            "Colas",
            f"  Dirs:  {snapshot.get('queue_dirs', 0)}",
            f"  Meta:  {snapshot.get('queue_meta', 0)}",
            f"  Files: {snapshot.get('queue_files', 0)}",
            "",
            "Progreso",
            f"  Dirs:      {snapshot.get('dirs', 0)}",
            f"  Files:     {snapshot.get('files', 0)}",
            f"  Bajados:   {snapshot.get('done', 0)}",
            f"  Omitidos:  {snapshot.get('skipped', 0)}",
            f"  Fallos:    {snapshot.get('failed', 0)}",
            f"  MB:        {float(snapshot.get('mb', 0.0)):0.2f}",
            "",
            "Proxies",
            f"  Cargados:  {snapshot.get('proxy_total', 0)}",
            f"  Intentos:  {snapshot.get('proxy_attempts', 0)}",
            f"  OK:        {snapshot.get('proxy_ok', 0)}",
            f"  Fallos:    {snapshot.get('proxy_fail', 0)}",
            "",
            "Requests",
            f"  Requests OK:    {snapshot.get('requests_ok', 0)}",
            f"  Requests fallo: {snapshot.get('requests_fail', 0)}",
        ]
        self.runtime_text.delete("1.0", tk.END)
        self.runtime_text.insert(tk.END, "\n".join(lines))

    def clear_tree(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.nodes.clear()

    def parent_url_for(self, url: str) -> str:
        parsed = urlparse(url)
        path = parsed.path.rstrip("/")
        if not path:
            return ""
        parent = str(Path(path).parent).replace("\\", "/")
        if parent == ".":
            parent = ""
        if parent and not parent.endswith("/"):
            parent += "/"
        return parsed._replace(path=parent).geturl()

    def display_name(self, url: str) -> str:
        parsed = urlparse(url)
        name = unquote(Path(parsed.path.rstrip("/")).name)
        if not name:
            return parsed.netloc
        return name + ("/" if url.endswith("/") else "")

    def selection_marker(self, entry: Entry) -> str:
        urls = self.file_urls_for_entry(entry)
        if not urls:
            return "empty"
        excluded = sum(1 for url in urls if url in self.excluded_download_urls)
        if excluded == 0:
            return "checked"
        if excluded == len(urls):
            return "unchecked"
        return "mixed"

    def display_label(self, entry: Entry) -> str:
        return self.display_name(entry.url)

    def checkbox_image(self, entry: Entry) -> tk.PhotoImage:
        return self.checkbox_images[self.selection_marker(entry)]

    @staticmethod
    def format_size(size: int) -> str:
        if size <= 0:
            return ""
        units = ["B", "KB", "MB", "GB", "TB"]
        value = float(size)
        unit = units[0]
        for unit in units:
            if value < 1024 or unit == units[-1]:
                break
            value /= 1024
        if unit == "B":
            return f"{int(value)} {unit}"
        return f"{value:.2f} {unit}"

    def insert_entry(self, entry: Entry) -> None:
        if entry.url in self.nodes:
            return
        self.all_entries[entry.url] = entry
        entry_type = "DIR" if entry.is_dir else ("RIESGO" if is_dangerous_url(entry.url) else "FILE")
        selected = self.selection_marker(entry)
        parent_url = self.parent_url_for(entry.url)
        parent_id = self.nodes.get(parent_url, "")
        item_id = self.tree.insert(
            parent_id,
            tk.END,
            text=self.display_label(entry),
            image=self.checkbox_image(entry),
            values=(
                selected,
                entry_type,
                entry.ext,
                self.format_size(entry.size),
                entry.last_modified,
                entry.url,
            ),
            open=entry.is_dir,
        )
        self.nodes[entry.url] = item_id

    def update_entry(self, entry: Entry) -> None:
        self.all_entries[entry.url] = entry
        item_id = self.nodes.get(entry.url)
        if not item_id:
            return
        entry_type = "DIR" if entry.is_dir else ("RIESGO" if is_dangerous_url(entry.url) else "FILE")
        selected = self.selection_marker(entry)
        self.tree.item(
            item_id,
            text=self.display_label(entry),
            image=self.checkbox_image(entry),
            values=(
                selected,
                entry_type,
                entry.ext,
                self.format_size(entry.size),
                entry.last_modified,
                entry.url,
            ),
        )

    def selected_url(self) -> str:
        item_id = self.tree.focus()
        if not item_id:
            selection = self.tree.selection()
            item_id = selection[0] if selection else ""
        if not item_id:
            return ""
        values = self.tree.item(item_id, "values")
        return str(values[-1]) if values else ""

    def copy_selected_url(self, _event=None) -> str:
        url = self.selected_url()
        if not url:
            self.status_var.set("No hay URL seleccionada")
            return "break"
        self.clipboard_clear()
        self.clipboard_append(url)
        self.update()
        self.status_var.set(f"URL copiada: {url}")
        return "break"

    def show_tree_menu(self, event) -> None:
        item_id = self.tree.identify_row(event.y)
        if item_id:
            self.tree.selection_set(item_id)
            self.tree.focus(item_id)
        self.tree_menu.tk_popup(event.x_root, event.y_root)

    def selected_entry(self) -> Entry | None:
        url = self.selected_url()
        return self.all_entries.get(url) if url else None

    def file_urls_for_entry(self, entry: Entry) -> list[str]:
        if not entry.is_dir:
            return [entry.url]
        return [
            item.url
            for item in self.all_entries.values()
            if not item.is_dir and item.url.startswith(entry.url)
        ]

    def set_entry_selected(self, entry: Entry, selected: bool) -> None:
        for url in self.file_urls_for_entry(entry):
            if selected:
                self.excluded_download_urls.discard(url)
            else:
                self.excluded_download_urls.add(url)
        self.refresh_selection_marks()
        self.status_var.set("Seleccionado para descargar" if selected else "Excluido de descarga")

    def refresh_selection_marks(self) -> None:
        for url, entry in list(self.all_entries.items()):
            if url in self.nodes:
                self.update_entry(entry)

    def select_selected_item(self) -> None:
        entry = self.selected_entry()
        if entry:
            self.set_entry_selected(entry, True)

    def deselect_selected_item(self) -> None:
        entry = self.selected_entry()
        if entry:
            self.set_entry_selected(entry, False)

    def toggle_selected_item(self, _event=None) -> str:
        entry = self.selected_entry()
        if entry:
            urls = self.file_urls_for_entry(entry)
            selected = any(url in self.excluded_download_urls for url in urls)
            self.set_entry_selected(entry, selected)
        return "break"

    def on_tree_double_click(self, event) -> None:
        if self.is_checkbox_hit(event):
            self.toggle_selected_item()

    def is_checkbox_hit(self, event) -> bool:
        item_id = self.tree.identify_row(event.y)
        if not item_id or self.tree.identify_column(event.x) != "#0":
            return False
        bbox = self.tree.bbox(item_id, "#0")
        if not bbox:
            return False
        x, _, _, _ = bbox
        return x <= event.x <= x + 26

    def on_tree_click(self, event) -> None:
        item_id = self.tree.identify_row(event.y)
        if item_id and self.is_checkbox_hit(event):
            self.tree.selection_set(item_id)
            self.tree.focus(item_id)
            self.toggle_selected_item()
            return "break"
        return None

    def visible_file_urls(self) -> list[str]:
        urls: list[str] = []
        for item_id in self.tree.get_children(""):
            urls.extend(self.visible_file_urls_from(item_id))
        return urls

    def visible_file_urls_from(self, item_id: str) -> list[str]:
        values = self.tree.item(item_id, "values")
        urls: list[str] = []
        if values:
            url = str(values[-1])
            entry = self.all_entries.get(url)
            if entry and not entry.is_dir:
                urls.append(url)
        for child in self.tree.get_children(item_id):
            urls.extend(self.visible_file_urls_from(child))
        return urls

    def select_visible(self) -> None:
        for url in self.visible_file_urls():
            self.excluded_download_urls.discard(url)
        self.refresh_selection_marks()
        self.status_var.set("Archivos visibles seleccionados")

    def deselect_visible(self) -> None:
        for url in self.visible_file_urls():
            self.excluded_download_urls.add(url)
        self.refresh_selection_marks()
        self.status_var.set("Archivos visibles excluidos de descarga")

    def schedule_target_geo_lookup(self) -> None:
        if self.geo_lookup_job:
            self.after_cancel(self.geo_lookup_job)
        self.geo_lookup_job = self.after(700, self.update_target_geo_async)

    def update_target_geo_async(self, url: str | None = None) -> None:
        raw_url = url or self.url_var.get().strip()
        if not raw_url:
            self.target_geo_var.set(f"{PIRATE_FLAG} Ubicacion: sin detectar")
            return
        try:
            base_url = normalize_base_url(raw_url)
        except ValueError:
            self.target_geo_var.set(f"{PIRATE_FLAG} Ubicacion: URL invalida")
            return
        host = urlparse(base_url).hostname or ""
        if host in self.geo_cache:
            self.render_target_geo(self.geo_cache[host])
            return
        self.target_geo_var.set(f"{PIRATE_FLAG} Ubicacion: consultando...")
        threading.Thread(target=self.resolve_target_geo_worker, args=(base_url, host), daemon=True).start()

    def resolve_target_geo_worker(self, base_url: str, host: str) -> None:
        info = resolve_target_geo(base_url)
        self.geo_cache[host] = info
        self.after(0, lambda: self.render_target_geo(info))

    def render_target_geo(self, info: dict[str, str]) -> None:
        flag = info.get("flag") or PIRATE_FLAG
        country = info.get("country") or "Unknown"
        ip = info.get("ip") or "sin IP"
        host = info.get("host") or "sin host"
        self.target_geo_var.set(f"{flag} {country} | {host} | {ip}")

    def validate_common(self) -> tuple[str, Path, set[str]] | None:
        try:
            base_url = normalize_base_url(self.url_var.get().strip())
            output = Path(self.output_var.get().strip() or "mirror")
            exts = parse_extensions(self.exclude_var.get())
            sources = split_proxy_sources(self.proxy_sources_var.get())
            target_is_onion = is_onion_url(base_url)
            tor_requested = self.use_tor_var.get() or self.start_tor_var.get()
            if self.use_tor_var.get() or self.start_tor_var.get():
                parse_socks_proxy(self.tor_proxy_var.get())
            parse_user_agents(self.user_agents_value)
            if self.no_leak_var.get():
                if target_is_onion and not tor_requested:
                    raise ValueError("Modo sin IP leak: las URL .onion requieren Tor activo o Arrancar tor.exe.")
                if not target_is_onion and not self.use_http_proxies_var.get() and not tor_requested:
                    raise ValueError("Modo sin IP leak: activa Tor o Proxies clearnet para no salir directo.")
                if (
                    not target_is_onion
                    and self.use_http_proxies_var.get()
                    and has_network_proxy_sources(sources)
                    and not tor_requested
                ):
                    raise ValueError(
                        "Modo sin IP leak: activa Tor o Arrancar tor.exe para cargar fuentes remotas de proxies sin fuga, "
                        "o usa una lista local de proxies."
                    )
            if self.start_tor_var.get():
                tor_exe = Path(self.tor_exe_var.get().strip())
                if not tor_exe.exists():
                    raise ValueError("Selecciona un tor.exe valido.")
            return base_url, output, exts
        except Exception as exc:
            messagebox.showerror("Configuracion invalida", str(exc))
            return None

    def start_scan(self) -> None:
        if self.scan_thread and self.scan_thread.is_alive():
            messagebox.showinfo("Escaneo activo", "Ya hay un escaneo en marcha.")
            return
        values = self.validate_common()
        if not values:
            return
        base_url, _, exts = values
        self.stop_event = threading.Event()
        self.scanned_files = []
        self.all_entries.clear()
        self.excluded_download_urls.clear()
        self.clear_tree()
        self.runtime_text.delete("1.0", tk.END)
        self.stats_text.delete("1.0", tk.END)
        self.log_text.delete("1.0", tk.END)
        self.status_var.set("Escaneando estructura...")
        self.update_target_geo_async(base_url)
        scanner = DirectoryScanner(
            base_url=base_url,
            exclude_exts=exts,
            dir_threads=self.dir_threads_var.get(),
            timeout=self.timeout_var.get(),
            retries=self.retries_var.get(),
            verify_tls=not self.insecure_tls_var.get(),
            use_tor=self.use_tor_var.get() or self.start_tor_var.get(),
            tor_proxy=self.tor_proxy_var.get(),
            start_tor=self.start_tor_var.get(),
            use_http_proxies=self.use_http_proxies_var.get(),
            proxy_sources=split_proxy_sources(self.proxy_sources_var.get()),
            no_leak=self.no_leak_var.get(),
            user_agents=parse_user_agents(self.user_agents_value),
            rotate_user_agents=self.rotate_user_agents_var.get(),
            tor_exe=Path(self.tor_exe_var.get().strip() or "tor.exe"),
            tor_data_dir=Path(self.tor_data_dir_var.get().strip() or ".tor-data"),
            tor_bootstrap_timeout=self.tor_bootstrap_timeout_var.get(),
            event_queue=self.events,
            stop_event=self.stop_event,
        )
        self.scan_thread = threading.Thread(target=scanner.run, daemon=True)
        self.scan_thread.start()

    def start_download(self) -> None:
        if self.download_thread and self.download_thread.is_alive():
            messagebox.showinfo("Descarga activa", "Ya hay una descarga en marcha.")
            return
        if not self.scanned_files:
            messagebox.showwarning("Sin indice", "Primero escanea la estructura.")
            return
        values = self.validate_common()
        if not values:
            return
        base_url, output, _ = values
        self.stop_event = threading.Event()
        self.runtime_text.delete("1.0", tk.END)
        self.status_var.set("Descargando archivos...")
        files_to_download = self.filtered_files()
        if not files_to_download:
            messagebox.showwarning("Sin archivos", "El filtro actual no deja archivos para descargar.")
            return
        downloader = FileDownloader(
            base_url=base_url,
            files=files_to_download,
            output_dir=output,
            threads=self.file_threads_var.get(),
            timeout=self.timeout_var.get(),
            retries=self.retries_var.get(),
            overwrite=self.overwrite_var.get(),
            verify_tls=not self.insecure_tls_var.get(),
            quarantine_dangerous=self.quarantine_dangerous_var.get(),
            use_tor=self.use_tor_var.get() or self.start_tor_var.get(),
            tor_proxy=self.tor_proxy_var.get(),
            start_tor=self.start_tor_var.get(),
            use_http_proxies=self.use_http_proxies_var.get(),
            proxy_sources=split_proxy_sources(self.proxy_sources_var.get()),
            no_leak=self.no_leak_var.get(),
            user_agents=parse_user_agents(self.user_agents_value),
            rotate_user_agents=self.rotate_user_agents_var.get(),
            tor_exe=Path(self.tor_exe_var.get().strip() or "tor.exe"),
            tor_data_dir=Path(self.tor_data_dir_var.get().strip() or ".tor-data"),
            tor_bootstrap_timeout=self.tor_bootstrap_timeout_var.get(),
            event_queue=self.events,
            stop_event=self.stop_event,
        )
        self.download_thread = threading.Thread(target=downloader.run, daemon=True)
        self.download_thread.start()

    def parse_size_filter(self, value: str) -> float | None:
        value = value.strip().replace(",", ".")
        if not value:
            return None
        return float(value)

    def parse_user_date(self, value: str):
        value = value.strip()
        if not value:
            return None
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                pass
        raise ValueError("Usa fecha YYYY-MM-DD o DD/MM/YYYY.")

    def parse_http_date(self, value: str):
        if not value:
            return None
        try:
            return parsedate_to_datetime(value).date()
        except (TypeError, ValueError, IndexError, OverflowError):
            return None

    def date_matches_filter(self, entry: Entry) -> bool:
        mode = self.filter_date_mode_var.get()
        raw_from = self.filter_date_var.get().strip()
        raw_to = self.filter_date_to_var.get().strip()
        if not raw_from and not raw_to:
            return True
        if mode == "contiene":
            return raw_from.lower() in entry.last_modified.lower()

        entry_date = self.parse_http_date(entry.last_modified)
        if entry_date is None:
            return False
        from_date = self.parse_user_date(raw_from)
        to_date = self.parse_user_date(raw_to)

        if mode == "en fecha":
            if from_date is None:
                raise ValueError("Selecciona una fecha.")
            return entry_date == from_date
        if mode == "entre":
            if from_date is None or to_date is None:
                raise ValueError("Para entre rellena fecha inicial y fecha final.")
            start, end = sorted((from_date, to_date))
            return start <= entry_date <= end
        if mode == "antes":
            if from_date is None:
                raise ValueError("Para antes rellena la primera fecha.")
            return entry_date < from_date
        if mode == "despues":
            if from_date is None:
                raise ValueError("Para despues rellena la primera fecha.")
            return entry_date > from_date
        return True

    def file_matches_filter(self, entry: Entry, require_selected: bool = False) -> bool:
        if require_selected and entry.url in self.excluded_download_urls:
            return False
        ext_filter = self.filter_ext_var.get().strip().lower()
        try:
            min_mb = self.parse_size_filter(self.filter_min_mb_var.get())
            max_mb = self.parse_size_filter(self.filter_max_mb_var.get())
        except ValueError:
            messagebox.showerror("Filtro invalido", "Min MB y Max MB deben ser numericos.")
            return False

        if ext_filter:
            wanted = parse_extensions(ext_filter)
            if self.filter_mode_var.get() == "include" and entry.ext not in wanted:
                return False
            if self.filter_mode_var.get() == "exclude" and entry.ext in wanted:
                return False
        include_terms = split_terms(self.filter_include_text_var.get())
        exclude_terms = split_terms(self.filter_exclude_text_var.get())
        haystack = f"{self.display_name(entry.url)} {entry.url}".lower()
        if include_terms and not any(term in haystack for term in include_terms):
            return False
        if exclude_terms and any(term in haystack for term in exclude_terms):
            return False
        size_mb = entry.size / 1024 / 1024
        if min_mb is not None and size_mb < min_mb:
            return False
        if max_mb is not None and entry.size > 0 and size_mb > max_mb:
            return False
        try:
            if not self.date_matches_filter(entry):
                return False
        except ValueError as exc:
            self.status_var.set(f"Filtro fecha invalido: {exc}")
            return False
        return True

    def filtered_files(self, require_selected: bool = True) -> list[Entry]:
        return [entry for entry in self.scanned_files if self.file_matches_filter(entry, require_selected)]

    def apply_filter(self) -> None:
        self.clear_tree()
        matching = self.filtered_files(require_selected=False)
        needed_dirs: set[str] = set()
        for entry in matching:
            parent = self.parent_url_for(entry.url)
            while parent:
                needed_dirs.add(parent)
                next_parent = self.parent_url_for(parent.rstrip("/"))
                if next_parent == parent:
                    break
                parent = next_parent
        dirs = [entry for entry in self.all_entries.values() if entry.is_dir and entry.url in needed_dirs]
        for entry in sorted(dirs, key=lambda item: item.url):
            self.insert_entry(entry)
        for entry in sorted(matching, key=lambda item: item.url):
            self.insert_entry(entry)
        self.status_var.set(f"Filtro aplicado: {len(matching)} archivos visibles")

    def clear_filter(self) -> None:
        self.filter_ext_var.set("")
        self.filter_mode_var.set("include")
        self.filter_min_mb_var.set("")
        self.filter_max_mb_var.set("")
        self.filter_date_mode_var.set("en fecha")
        self.filter_date_var.set("")
        self.filter_date_to_var.set("")
        self.filter_include_text_var.set("")
        self.filter_exclude_text_var.set("")
        self.clear_tree()
        for entry in sorted(self.all_entries.values(), key=lambda item: item.url):
            self.insert_entry(entry)
        self.status_var.set("Filtro limpiado")

    def update_stats(self) -> None:
        files = self.scanned_files
        total_files = len(files)
        total_size = sum(entry.size for entry in files)
        by_ext: dict[str, dict[str, int]] = {}
        dated = 0
        unknown_size = 0
        for entry in files:
            stats = by_ext.setdefault(entry.ext, {"count": 0, "bytes": 0})
            stats["count"] += 1
            stats["bytes"] += entry.size
            if entry.last_modified:
                dated += 1
            if entry.size <= 0:
                unknown_size += 1

        lines = [
            f"Archivos: {total_files}",
            f"Tamaño total conocido: {self.format_size(total_size)}",
            f"Con fecha Last-Modified: {dated} ({(dated / total_files * 100) if total_files else 0:.1f}%)",
            f"Sin tamaño conocido: {unknown_size} ({(unknown_size / total_files * 100) if total_files else 0:.1f}%)",
            "",
            "Extensión | Archivos | % archivos | Tamaño | % tamaño",
        ]
        for ext, stats in sorted(by_ext.items(), key=lambda item: item[1]["count"], reverse=True):
            count_pct = (stats["count"] / total_files * 100) if total_files else 0
            size_pct = (stats["bytes"] / total_size * 100) if total_size else 0
            lines.append(
                f"{ext:14} {stats['count']:8} {count_pct:8.2f}% "
                f"{self.format_size(stats['bytes']):>12} {size_pct:8.2f}%"
            )
        self.stats_text.delete("1.0", tk.END)
        self.stats_text.insert(tk.END, "\n".join(lines))

    def stop_current(self) -> None:
        self.stop_event.set()
        self.status_var.set("Parando...")

    def poll_events(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "entry":
                    self.insert_entry(event[1])
                elif kind == "meta":
                    self.update_entry(event[1])
                elif kind == "progress":
                    dirs, files, failed, queued = event[1]
                    self.status_var.set(f"Escaneo: dirs={dirs} files={files} fallos={failed} cola={queued}")
                elif kind == "runtime_status":
                    self.render_runtime_status(event[1])
                elif kind == "scan_done":
                    dirs, files, failed, _ = event[1]
                    self.scanned_files = event[2]
                    for entry in self.scanned_files:
                        self.all_entries[entry.url] = entry
                    self.update_stats()
                    self.status_var.set(f"Estructura lista: dirs={dirs} files={files} fallos={failed}")
                    self.log(f"[SCAN DONE] dirs={dirs} files={files} fallos={failed}")
                elif kind == "scan_stopped":
                    dirs, files, failed, _ = event[1]
                    self.scanned_files = event[2]
                    for entry in self.scanned_files:
                        self.all_entries[entry.url] = entry
                    self.update_stats()
                    self.status_var.set(f"Escaneo parado: dirs={dirs} files={files} fallos={failed}")
                    self.log(f"[SCAN STOPPED] dirs={dirs} files={files} fallos={failed}")
                elif kind == "download_progress":
                    done, skipped, failed, total, mb = event[1]
                    self.status_var.set(
                        f"Descarga: {done}/{total} omitidos={skipped} fallos={failed} MB={mb:.2f}"
                    )
                elif kind == "download_done":
                    done, skipped, failed, total, mb = event[1]
                    index_path = event[2]
                    self.status_var.set(
                        f"Descarga terminada: {done}/{total} omitidos={skipped} fallos={failed} MB={mb:.2f}"
                    )
                    self.log(f"[DOWNLOAD DONE] index={index_path}")
                elif kind == "download_stopped":
                    done, skipped, failed, total, mb = event[1]
                    index_path = event[2]
                    self.status_var.set(
                        f"Descarga parada: {done}/{total} omitidos={skipped} fallos={failed} MB={mb:.2f}"
                    )
                    self.log(f"[DOWNLOAD STOPPED] index={index_path}")
                elif kind == "log":
                    self.log(event[1])
        except queue.Empty:
            pass
        self.after(150, self.poll_events)


if __name__ == "__main__":
    App().mainloop()
