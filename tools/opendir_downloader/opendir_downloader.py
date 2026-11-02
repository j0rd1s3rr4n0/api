import argparse
import concurrent.futures
import csv
import hashlib
import logging
import queue
import re
import secrets
import socket
import ssl
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urldefrag, urljoin, urlparse
from urllib.request import Request, urlopen

import socks


LOGGER = logging.getLogger("opendir_downloader")
DEFAULT_EXCLUDES = {".jpg", ".jpeg", ".png"}
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
INDEX_NAMES = {"", "/", "index.html", "index.htm"}
WORKER_STOP = object()
ORIGINAL_SOCKET = socket.socket
ORIGINAL_CREATE_CONNECTION = socket.create_connection
SOCKET_PROXY_LOCK = threading.Lock()
TOR_MAX_WORKERS = 32


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


@dataclass(frozen=True)
class Config:
    start_url: str
    output_dir: Path
    workers: int
    timeout: float
    retries: int
    exclude_exts: frozenset[str]
    user_agent: str
    overwrite: bool
    same_host: bool
    same_tree: bool
    keep_indexes: bool
    log_file: Path
    verify_tls: bool
    use_tor: bool
    tor_proxy: str
    start_tor: bool
    tor_exe: Path
    tor_data_dir: Path
    tor_bootstrap_timeout: float
    quarantine_dangerous: bool


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
    user = "opendir"
    password = secrets.token_hex(12)
    return f"{parsed.scheme}://{user}:{password}@{host}:{parsed.port}"


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
    if stem in {"CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
                "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"}:
        return f"_{part}"
    return part


def mark_windows_download(path: Path, url: str) -> None:
    try:
        with open(str(path) + ":Zone.Identifier", "w", encoding="utf-8") as stream:
            stream.write("[ZoneTransfer]\nZoneId=3\nHostUrl=" + url + "\n")
    except OSError:
        return


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


def launch_tor_process(tor_exe: Path, proxy_url: str, data_dir: Path, timeout: float) -> subprocess.Popen:
    if not tor_exe.exists():
        raise FileNotFoundError(f"No existe tor.exe: {tor_exe}")
    _, host, port, _, _, _ = parse_socks_proxy(proxy_url)
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
        if process.poll() is not None:
            raise RuntimeError("Tor se cerro antes de conectar. " + "".join(recent[-20:]))
        line = process.stdout.readline() if process.stdout else ""
        if line:
            recent.append(line)
            LOGGER.info("[TOR] %s", line.strip())
            if "Bootstrapped 100%" in line:
                return process
        else:
            time.sleep(0.1)
    process.terminate()
    raise TimeoutError(f"Tor no llego a Bootstrapped 100% en {timeout:.0f}s")


class OpenDirDownloader:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.tor_process: subprocess.Popen | None = None
        if config.start_tor and config.use_tor:
            LOGGER.info("Arrancando Tor: %s", config.tor_exe)
            self.tor_process = launch_tor_process(
                config.tor_exe,
                config.tor_proxy,
                config.tor_data_dir,
                config.tor_bootstrap_timeout,
            )
        configure_socket_proxy(config.use_tor, config.tor_proxy)
        self.start_url = self.normalize_dir_url(config.start_url)
        self.start_parts = urlparse(self.start_url)
        self.url_queue: queue.Queue[str | object] = queue.Queue()
        self.seen: set[str] = set()
        self.seen_lock = threading.Lock()
        self.stats_lock = threading.Lock()
        self.stats = {
            "indexed": 0,
            "downloaded": 0,
            "skipped": 0,
            "failed": 0,
            "bytes": 0,
        }
        self.index_rows: list[dict[str, str | int]] = []

    @staticmethod
    def normalize_dir_url(url: str) -> str:
        parsed = urlparse(url)
        if not parsed.scheme:
            raise ValueError("La URL debe incluir http:// o https://")
        if not parsed.path.endswith("/") and Path(parsed.path).suffix == "":
            url += "/"
        return url

    @staticmethod
    def clean_url(url: str) -> str:
        clean, _ = urldefrag(url)
        return clean

    def enqueue(self, url: str) -> None:
        url = self.clean_url(url)
        if not self.allowed_url(url):
            return
        with self.seen_lock:
            if url in self.seen:
                return
            self.seen.add(url)
        self.url_queue.put(url)

    def allowed_url(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return False
        if self.config.same_host and parsed.netloc.lower() != self.start_parts.netloc.lower():
            return False
        if self.config.same_tree and not parsed.path.startswith(self.start_parts.path):
            return False
        return True

    def request(self, url: str):
        headers = {"User-Agent": self.config.user_agent}
        return Request(url, headers=headers)

    def ssl_context(self):
        if self.config.verify_tls:
            return None
        return ssl._create_unverified_context()

    def open_url(self, url: str):
        last_error: Exception | None = None
        for attempt in range(self.config.retries + 1):
            try:
                return urlopen(self.request(url), timeout=self.config.timeout, context=self.ssl_context())
            except (HTTPError, URLError, TimeoutError, OSError) as exc:
                last_error = exc
                if attempt < self.config.retries:
                    time.sleep(min(2.0, 0.25 * (attempt + 1)))
        raise last_error or RuntimeError("Error desconocido")

    def is_directory_url(self, url: str, content_type: str | None = None) -> bool:
        parsed = urlparse(url)
        name = Path(parsed.path).name.lower()
        if parsed.path.endswith("/"):
            return True
        if name in INDEX_NAMES:
            return True
        return bool(content_type and "text/html" in content_type.lower())

    def should_skip_file(self, url: str) -> bool:
        suffix = Path(urlparse(url).path).suffix.lower()
        return suffix in self.config.exclude_exts

    def is_dangerous_file(self, url: str) -> bool:
        suffix = Path(urlparse(url).path).suffix.lower()
        return suffix in DANGEROUS_EXTS

    def local_path_for(self, url: str, is_dir_index: bool = False) -> Path:
        parsed = urlparse(url)
        root = self.config.output_dir
        rel_path = unquote(parsed.path)
        start_path = self.start_parts.path
        if self.config.same_tree and rel_path.startswith(start_path):
            rel_path = rel_path[len(start_path):]
        rel_path = rel_path.strip("/")

        if not rel_path:
            rel_path = "index.html"
        if is_dir_index:
            rel_path = str(Path(rel_path) / "index.html") if rel_path else "index.html"
        rel_parts = [sanitize_path_part(part) for part in re.split(r"[\\/]+", rel_path) if part not in {"", ".", ".."}]
        rel_path = str(Path(*rel_parts)) if rel_parts else "index.html"
        if self.config.quarantine_dangerous and not is_dir_index and self.is_dangerous_file(url):
            rel_path = str(Path("_quarantine") / rel_path) + ".download"

        candidate = (root / rel_path).resolve()
        root_resolved = root.resolve()
        if not str(candidate).lower().startswith(str(root_resolved).lower()):
            digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
            candidate = root_resolved / f"unsafe-path-{digest}"
        return candidate

    def parse_index(self, url: str, html: str) -> Iterable[str]:
        parser = LinkParser()
        parser.feed(html)
        for href in parser.links:
            href = href.strip()
            if not href or href.startswith(("#", "?", "mailto:", "javascript:")):
                continue
            if href in {"../", ".."}:
                continue
            yield self.clean_url(urljoin(url, href))

    def handle_index(self, url: str, response_body: bytes) -> None:
        html = response_body.decode("utf-8", errors="ignore")
        for child_url in self.parse_index(url, html):
            if self.should_skip_file(child_url):
                self.increment("skipped")
                continue
            self.enqueue(child_url)
        if self.config.keep_indexes:
            self.write_file(url, self.local_path_for(url, is_dir_index=True), response_body)
        self.increment("indexed")

    def write_file(
        self,
        url: str,
        path: Path,
        response_body: bytes,
        last_modified: str = "",
    ) -> None:
        if path.exists() and not self.config.overwrite:
            self.increment("skipped")
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(f"{path.name}.{threading.get_ident()}.part")
        try:
            temp_path.write_bytes(response_body)
            if path.exists() and not self.config.overwrite:
                temp_path.unlink(missing_ok=True)
                self.increment("skipped")
                return
            temp_path.replace(path)
            mark_windows_download(path, url)
        finally:
            temp_path.unlink(missing_ok=True)
        self.increment("downloaded")
        self.increment("bytes", len(response_body))
        self.add_index_row(url, path, len(response_body), last_modified)

    def add_index_row(self, url: str, path: Path, size: int, last_modified: str) -> None:
        with self.stats_lock:
            self.index_rows.append(
                {
                    "url": url,
                    "local_path": str(path.resolve()),
                    "size": size,
                    "last_modified": last_modified,
                    "quarantined": "yes" if self.config.quarantine_dangerous and self.is_dangerous_file(url) else "",
                    "downloaded_at": datetime.now().isoformat(timespec="seconds"),
                }
            )

    def write_download_index(self) -> Path:
        index_path = self.config.output_dir / "_download_index.csv"
        with self.stats_lock:
            rows = list(self.index_rows)
        with index_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["url", "local_path", "size", "last_modified", "quarantined", "downloaded_at"],
            )
            writer.writeheader()
            writer.writerows(rows)
        return index_path

    def download_file(self, url: str, response_body: bytes, last_modified: str = "") -> None:
        if self.should_skip_file(url):
            self.increment("skipped")
            return
        self.write_file(url, self.local_path_for(url), response_body, last_modified)

    def process_url(self, url: str) -> None:
        try:
            with self.open_url(url) as response:
                content_type = response.headers.get("Content-Type", "")
                last_modified = response.headers.get("Last-Modified", "")
                body = response.read()
            if self.is_directory_url(url, content_type):
                self.handle_index(url, body)
            else:
                self.download_file(url, body, last_modified)
        except Exception as exc:
            self.increment("failed")
            LOGGER.warning("Fallo %s: %s", url, exc)

    def increment(self, key: str, amount: int = 1) -> None:
        with self.stats_lock:
            self.stats[key] += amount

    def worker(self) -> None:
        while True:
            item = self.url_queue.get()
            try:
                if item is WORKER_STOP:
                    return
                self.process_url(str(item))
            finally:
                self.url_queue.task_done()

    def progress(self) -> None:
        while True:
            time.sleep(5)
            with self.stats_lock:
                stats = dict(self.stats)
            LOGGER.info(
                "Progreso: vistos=%s cola=%s indices=%s descargados=%s omitidos=%s fallos=%s MB=%.2f",
                len(self.seen),
                self.url_queue.qsize(),
                stats["indexed"],
                stats["downloaded"],
                stats["skipped"],
                stats["failed"],
                stats["bytes"] / 1024 / 1024,
            )
            if self.url_queue.unfinished_tasks == 0:
                return

    def run(self) -> None:
        try:
            self.config.output_dir.mkdir(parents=True, exist_ok=True)
            self.enqueue(self.start_url)
            LOGGER.info("Inicio: %s", self.start_url)
            LOGGER.info("Salida: %s", self.config.output_dir.resolve())
            LOGGER.info("Hilos: %s", self.config.workers)

            progress_thread = threading.Thread(target=self.progress, daemon=True)
            progress_thread.start()

            with concurrent.futures.ThreadPoolExecutor(max_workers=self.config.workers) as executor:
                futures = [executor.submit(self.worker) for _ in range(self.config.workers)]
                self.url_queue.join()
                for _ in futures:
                    self.url_queue.put(WORKER_STOP)
                self.url_queue.join()

            with self.stats_lock:
                stats = dict(self.stats)
            index_path = self.write_download_index()
            LOGGER.info(
                "Terminado: indices=%s descargados=%s omitidos=%s fallos=%s MB=%.2f index=%s",
                stats["indexed"],
                stats["downloaded"],
                stats["skipped"],
                stats["failed"],
                stats["bytes"] / 1024 / 1024,
                index_path.resolve(),
            )
        finally:
            if self.tor_process and self.tor_process.poll() is None:
                self.tor_process.terminate()


def parse_extensions(raw: str) -> frozenset[str]:
    exts = set()
    for item in re.split(r"[,; ]+", raw.strip()):
        if not item:
            continue
        item = item.lower()
        if not item.startswith("."):
            item = "." + item
        exts.add(item)
    return frozenset(exts)


def configure_logging(log_file: Path) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler(log_file, encoding="utf-8"), logging.StreamHandler()],
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mirror recursivo multi-hilo para directory listings/open directories"
    )
    parser.add_argument("url", help="URL inicial del directory listing")
    parser.add_argument("-o", "--output", default="download", help="Carpeta de salida")
    parser.add_argument("-t", "--threads", type=int, default=128, help="Numero de hilos")
    parser.add_argument("--timeout", type=float, default=15.0, help="Timeout por request")
    parser.add_argument("--retries", type=int, default=1, help="Reintentos por URL")
    parser.add_argument(
        "--exclude",
        default="jpg,jpeg,png",
        help="Extensiones a excluir separadas por coma",
    )
    parser.add_argument("--overwrite", action="store_true", help="Sobrescribe archivos existentes")
    parser.add_argument("--allow-other-hosts", action="store_true", help="Permite salir a otros hosts")
    parser.add_argument("--allow-parent", action="store_true", help="Permite salir del arbol inicial")
    parser.add_argument("--keep-indexes", action="store_true", help="Guarda tambien index.html")
    parser.add_argument("--insecure", action="store_true", help="Ignora errores de certificado TLS/SSL")
    parser.add_argument("--tor", action="store_true", help="Usa Tor/SOCKS5 para acceder tambien a .onion")
    parser.add_argument(
        "--tor-proxy",
        default="socks5h://127.0.0.1:9050",
        help="Proxy Tor SOCKS. Tor servicio: socks5h://127.0.0.1:9050; Tor Browser: socks5h://127.0.0.1:9150",
    )
    parser.add_argument("--start-tor", action="store_true", help="Arranca un tor.exe externo antes de escanear")
    parser.add_argument("--tor-exe", default="tor.exe", help="Ruta a tor.exe del Tor Expert Bundle")
    parser.add_argument("--tor-data-dir", default=".tor-data", help="Directorio DataDirectory para tor.exe")
    parser.add_argument("--tor-bootstrap-timeout", type=float, default=90.0, help="Segundos para esperar a Tor")
    parser.add_argument(
        "--no-quarantine",
        action="store_true",
        help="No pone en cuarentena extensiones ejecutables/scripts/ofimatica activa",
    )
    parser.add_argument("--log-file", default="opendir_downloader.log", help="Archivo de log")
    parser.add_argument(
        "--user-agent",
        default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) OpenDirDownloader/1.0",
        help="User-Agent HTTP",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    tor_requested = args.tor or args.start_tor
    tor_proxy = add_tor_session_auth(args.tor_proxy) if tor_requested else args.tor_proxy
    workers = limit_tor_workers(args.threads, tor_requested)
    config = Config(
        start_url=args.url,
        output_dir=Path(args.output),
        workers=workers,
        timeout=args.timeout,
        retries=max(0, args.retries),
        exclude_exts=parse_extensions(args.exclude),
        user_agent=args.user_agent,
        overwrite=args.overwrite,
        same_host=not args.allow_other_hosts,
        same_tree=not args.allow_parent,
        keep_indexes=args.keep_indexes,
        log_file=Path(args.log_file),
        verify_tls=not args.insecure,
        use_tor=tor_requested,
        tor_proxy=tor_proxy,
        start_tor=args.start_tor,
        tor_exe=Path(args.tor_exe),
        tor_data_dir=Path(args.tor_data_dir),
        tor_bootstrap_timeout=args.tor_bootstrap_timeout,
        quarantine_dangerous=not args.no_quarantine,
    )
    configure_logging(config.log_file)
    if tor_requested and workers < max(1, args.threads):
        LOGGER.info("Tor activo: hilos limitados de %s a %s", args.threads, workers)
    try:
        OpenDirDownloader(config).run()
        return 0
    except KeyboardInterrupt:
        LOGGER.warning("Cancelado por usuario")
        return 130
    except Exception as exc:
        LOGGER.error("Error fatal: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
