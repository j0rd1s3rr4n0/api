import argparse
import ipaddress
import json
import logging
import multiprocessing
import os
import random
import re
import socket
import subprocess
import threading
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Sequence, Set
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


LOGGER = logging.getLogger("proxy_scraper")
PROXY_PATTERN = re.compile(
    r"(?:(?P<scheme>https?|socks(?:4a?|5h?)|quic)://)?"
    r"(?P<host>\b\d{1,3}(?:\.\d{1,3}){3}\b):(?P<port>\d{2,5})",
    re.IGNORECASE,
)
THREAD_LOCAL = threading.local()
DEFAULT_PROXY_SCHEME = "http"
SUPPORTED_PROXY_SCHEMES = {"http", "https", "socks4", "socks4a", "socks5", "socks5h", "quic"}
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


@dataclass(frozen=True)
class Config:
    proxy_sources_file: Path = Path("urls.txt")
    raw_proxies_file: Path = Path("proxies.txt")
    valid_proxies_file: Path = Path("http.txt")
    proxy_list_dir: Path = Path("proxieslist")
    log_file: Path = Path("proxy_scraper.log")
    timeout: float = 2.0
    socket_timeout: float = 1.0
    scrape_workers: int = 128
    validation_threads: int = 128
    validation_processes: int = max(1, min(os.cpu_count() or 1, 4))
    max_validation_proxies: int = 30_000
    max_response_bytes: int = 5_000_000
    test_url: str = "http://httpbin.org/ip"
    batch_size: int = 5_000
    batch_pause: float = 0.0
    low_priority: bool = False
    geo_enabled: bool = True
    geo_workers: int = 12
    geo_timeout: float = 3.0
    github_sources: bool = True
    git_enabled: bool = False


SCRAPE_URLS = {
    "proxyscrape": [
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all",
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=https&timeout=10000&country=all",
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks4&timeout=10000&country=all",
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5&timeout=10000&country=all",
    ],
    "free-proxy-list": ["https://free-proxy-list.net/"],
    "sslproxies": ["https://www.sslproxies.org/"],
    "us-proxy": ["https://www.us-proxy.org/"],
    "openproxy": [
        "https://openproxy.space/list/http",
        "https://openproxy.space/list/https",
        "https://openproxy.space/list/socks4",
        "https://openproxy.space/list/socks5",
    ],
    "proxy-list.download": [
        "https://www.proxy-list.download/api/v1/get?type=http",
        "https://www.proxy-list.download/api/v1/get?type=https",
        "https://www.proxy-list.download/api/v1/get?type=socks4",
        "https://www.proxy-list.download/api/v1/get?type=socks5",
    ],
}


GITHUB_PROXY_URLS = [
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies_anonymous/http.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies_anonymous/socks4.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies_anonymous/socks5.txt",
    "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/https.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks4.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks5.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS4_RAW.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS5_RAW.txt",
    "https://raw.githubusercontent.com/proxy4parsing/proxy-list/main/http.txt",
    "https://raw.githubusercontent.com/proxy4parsing/proxy-list/main/socks4.txt",
    "https://raw.githubusercontent.com/proxy4parsing/proxy-list/main/socks5.txt",
    "https://raw.githubusercontent.com/ALIILAPRO/Proxy/main/http.txt",
    "https://raw.githubusercontent.com/ALIILAPRO/Proxy/main/socks4.txt",
    "https://raw.githubusercontent.com/ALIILAPRO/Proxy/main/socks5.txt",
    "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/xResults/Proxies.txt",
    "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/xResults/RAW.txt",
    "https://raw.githubusercontent.com/thenasty1337/free-proxy-list/main/data/latest/proxies.txt",
    "https://raw.githubusercontent.com/thenasty1337/free-proxy-list/main/data/latest/types/http/proxies.txt",
    "https://raw.githubusercontent.com/thenasty1337/free-proxy-list/main/data/latest/types/socks4/proxies.txt",
    "https://raw.githubusercontent.com/thenasty1337/free-proxy-list/main/data/latest/types/socks5/proxies.txt",
    "https://raw.githubusercontent.com/r00tee/Proxy-List/main/Https.txt",
    "https://raw.githubusercontent.com/r00tee/Proxy-List/main/Socks4.txt",
    "https://raw.githubusercontent.com/r00tee/Proxy-List/main/Socks5.txt",
    "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/http/data.txt",
    "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/socks4/data.txt",
    "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/socks5/data.txt",
    "https://raw.githubusercontent.com/ProxyScraper/ProxyScraper/main/http.txt",
    "https://raw.githubusercontent.com/ProxyScraper/ProxyScraper/main/socks4.txt",
    "https://raw.githubusercontent.com/ProxyScraper/ProxyScraper/main/socks5.txt",
]


def configure_logging(log_file: Path) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler(log_file, encoding="utf-8"), logging.StreamHandler()],
    )


def set_low_process_priority() -> None:
    try:
        if os.name == "nt":
            import ctypes

            below_normal = 0x00004000
            kernel32 = ctypes.windll.kernel32
            if kernel32.SetPriorityClass(kernel32.GetCurrentProcess(), below_normal):
                LOGGER.info("Prioridad del proceso: below normal")
            return
        os.nice(10)
        LOGGER.info("Prioridad del proceso reducida con nice +10")
    except Exception as exc:
        LOGGER.warning("No se pudo reducir la prioridad del proceso: %s", exc)


def create_session(retries: int, timeout_pool: int) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=retries,
        connect=retries,
        read=retries,
        backoff_factor=0.25,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "HEAD", "OPTIONS"),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(
        max_retries=retry,
        pool_connections=timeout_pool,
        pool_maxsize=timeout_pool,
        pool_block=False,
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
            "Accept": "text/plain,text/html,application/json,*/*;q=0.8",
            "Connection": "close",
        }
    )
    return session


def get_validation_session() -> requests.Session:
    session = getattr(THREAD_LOCAL, "validation_session", None)
    if session is None:
        session = create_session(retries=0, timeout_pool=8)
        THREAD_LOCAL.validation_session = session
    return session


def normalize_proxy(host: str, port: str, scheme: str | None = None) -> str | None:
    try:
        ipaddress.ip_address(host)
        port_number = int(port)
    except ValueError:
        return None

    if not 1 <= port_number <= 65535:
        return None

    normalized_scheme = (scheme or DEFAULT_PROXY_SCHEME).lower()
    if normalized_scheme not in SUPPORTED_PROXY_SCHEMES:
        return None
    return f"{normalized_scheme}://{host}:{port_number}"


def parse_proxy(proxy: str) -> tuple[str, str, int] | None:
    candidate = proxy if "://" in proxy else f"{DEFAULT_PROXY_SCHEME}://{proxy}"
    parsed = urlparse(candidate)
    scheme = parsed.scheme.lower()
    if scheme not in SUPPORTED_PROXY_SCHEMES or not parsed.hostname or parsed.port is None:
        return None
    try:
        ipaddress.ip_address(parsed.hostname)
    except ValueError:
        return None
    if not 1 <= parsed.port <= 65535:
        return None
    return scheme, parsed.hostname, parsed.port


def proxy_scheme(proxy: str) -> str:
    parsed = parse_proxy(proxy)
    return parsed[0] if parsed else "invalid"


def proxy_filename(scheme: str) -> str:
    return f"{scheme.lower()}.txt"


def safe_country_dir(country: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._ -]+", "_", country).strip(" ._")
    return value or "Unknown"


def read_json_file(path: Path) -> dict[str, dict[str, str]]:
    try:
        data = path.read_text(encoding="utf-8")
        loaded = json.loads(data)
        return loaded if isinstance(loaded, dict) else {}
    except (OSError, ValueError):
        return {}


def write_json_file(path: Path, data: dict[str, dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
    path.write_text(text + "\n", encoding="utf-8")


def ipinfo_lookup(ip: str, timeout: float) -> dict[str, str]:
    try:
        response = requests.get(f"https://ipinfo.io/{ip}/json", timeout=timeout)
        response.raise_for_status()
        data = response.json()
        country_code = str(data.get("country") or "XX").upper()
        country_name = str(data.get("country_name") or COUNTRY_NAMES.get(country_code) or data.get("country") or "Unknown")
        return {"country_code": country_code, "country": country_name}
    except Exception:
        return {"country_code": "XX", "country": "Unknown"}


def infer_source_scheme(source: str, url: str) -> str:
    parsed = urlparse(url)
    marker = f"{parsed.path}?{parsed.query}".lower()
    if "socks5h" in marker:
        return "socks5h"
    if "socks5" in marker:
        return "socks5"
    if "socks4a" in marker:
        return "socks4a"
    if "socks4" in marker:
        return "socks4"
    if "protocol=https" in marker or "type=https" in marker or "https_raw" in marker:
        return "https"
    if source == "sslproxies":
        return "https"
    return DEFAULT_PROXY_SCHEME


def extract_proxies(content: str, default_scheme: str = DEFAULT_PROXY_SCHEME) -> Set[str]:
    proxies: Set[str] = set()
    for match in PROXY_PATTERN.finditer(content):
        proxy = normalize_proxy(
            match.group("host"),
            match.group("port"),
            match.group("scheme") or default_scheme,
        )
        if proxy:
            proxies.add(proxy)
    return proxies


def socket_open(proxy: str, timeout: float) -> bool:
    parsed = parse_proxy(proxy)
    if parsed is None:
        return False
    _, host, port = parsed
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def validate_proxy(proxy: str, timeout: float, socket_timeout: float, test_url: str) -> bool:
    if not socket_open(proxy, socket_timeout):
        return False

    session = get_validation_session()
    proxy_url = proxy if "://" in proxy else f"{DEFAULT_PROXY_SCHEME}://{proxy}"
    try:
        response = session.get(
            test_url,
            proxies={"http": proxy_url, "https": proxy_url},
            timeout=timeout,
            allow_redirects=False,
            stream=True,
        )
        response.close()
        return 200 <= response.status_code < 400
    except requests.RequestException:
        return False


def validate_chunk(
    proxies: Sequence[str],
    timeout: float,
    socket_timeout: float,
    test_url: str,
    threads: int,
    batch_size: int,
) -> List[str]:
    valid: List[str] = []
    if not proxies:
        return valid

    workers = max(1, min(threads, len(proxies)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for start in range(0, len(proxies), batch_size):
            batch = proxies[start : start + batch_size]
            futures = {
                executor.submit(validate_proxy, proxy, timeout, socket_timeout, test_url): proxy
                for proxy in batch
            }
            for future in as_completed(futures):
                proxy = futures[future]
                try:
                    if future.result():
                        valid.append(proxy)
                except Exception:
                    continue
    return valid


class ProxyScraper:
    def __init__(self, config: Config):
        self.config = config
        self.scraping_session = create_session(retries=0, timeout_pool=config.scrape_workers)
        self.proxies: Set[str] = set()
        self.valid_proxies: Set[str] = set()

    def load_source_urls(self) -> list[tuple[str, str]]:
        urls: list[tuple[str, str]] = []
        for source, source_urls in SCRAPE_URLS.items():
            urls.extend((source, url) for url in source_urls)

        if self.config.github_sources:
            urls.extend(("github_raw", url) for url in GITHUB_PROXY_URLS)

        try:
            custom_urls = [
                line.strip()
                for line in self.config.proxy_sources_file.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.lstrip().startswith("#")
            ]
        except FileNotFoundError:
            LOGGER.warning("Archivo de fuentes no encontrado: %s", self.config.proxy_sources_file)
            custom_urls = []

        urls.extend(("custom_urls", url) for url in custom_urls)
        return list(dict.fromkeys(urls))

    def scrape_url(self, source: str, url: str) -> tuple[str, str, Set[str]]:
        try:
            response = self.scraping_session.get(url, timeout=self.config.timeout, stream=True)
            try:
                response.raise_for_status()
                content = bytearray()
                for chunk in response.iter_content(chunk_size=65536):
                    if not chunk:
                        continue
                    content.extend(chunk)
                    if (
                        self.config.max_response_bytes > 0
                        and len(content) >= self.config.max_response_bytes
                    ):
                        LOGGER.debug(
                            "Cortando %s (%s) al llegar a %s bytes",
                            url,
                            source,
                            self.config.max_response_bytes,
                        )
                        break
                text = content.decode(response.encoding or "utf-8", errors="ignore")
                return source, url, extract_proxies(text, infer_source_scheme(source, url))
            finally:
                response.close()
        except requests.RequestException as exc:
            LOGGER.debug("Error scraping %s (%s): %s", url, source, exc)
            return source, url, set()

    def scrape_all(self) -> None:
        urls = self.load_source_urls()
        if not urls:
            LOGGER.warning("No hay URLs para scrapear")
            return

        LOGGER.info("Scraping %s URLs con %s hilos", len(urls), self.config.scrape_workers)
        per_source: dict[str, int] = {}
        workers = max(1, min(self.config.scrape_workers, len(urls)))

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(self.scrape_url, source, url): (source, url)
                for source, url in urls
            }
            for future in as_completed(futures):
                source, _, proxies = future.result()
                self.proxies.update(proxies)
                per_source[source] = per_source.get(source, 0) + len(proxies)

        for source, count in sorted(per_source.items()):
            LOGGER.info("%s: %s proxies encontrados", source, count)
        LOGGER.info("Total unico de proxies encontrados: %s", len(self.proxies))
        if self.proxies:
            by_scheme: dict[str, int] = {}
            for proxy in self.proxies:
                scheme = proxy_scheme(proxy)
                by_scheme[scheme] = by_scheme.get(scheme, 0) + 1
            LOGGER.info(
                "Proxies por protocolo: %s",
                ", ".join(f"{scheme}={count}" for scheme, count in sorted(by_scheme.items())),
            )

    @staticmethod
    def chunks(items: Sequence[str], chunk_count: int) -> Iterable[list[str]]:
        chunk_count = max(1, min(chunk_count, len(items)))
        for index in range(chunk_count):
            yield list(items[index::chunk_count])

    def validate_all(self) -> None:
        proxy_list = list(self.proxies)
        random.shuffle(proxy_list)
        if not proxy_list:
            LOGGER.warning("No hay proxies para validar")
            return

        if self.config.max_validation_proxies > 0 and len(proxy_list) > self.config.max_validation_proxies:
            LOGGER.info(
                "Validacion por lotes de %s proxies hasta completar %s encontrados "
                "(usa --max-proxies 0 para un unico lote completo)",
                self.config.max_validation_proxies,
                len(proxy_list),
            )

        batch_limit = self.config.max_validation_proxies if self.config.max_validation_proxies > 0 else len(proxy_list)
        validation_batches = [
            proxy_list[index : index + batch_limit]
            for index in range(0, len(proxy_list), batch_limit)
        ]

        total_validated = 0
        for batch_index, batch in enumerate(validation_batches, start=1):
            processes = max(1, min(self.config.validation_processes, len(batch)))
            LOGGER.info(
                "Validando lote %s/%s: %s proxies con %s procesos hijo x %s hilos",
                batch_index,
                len(validation_batches),
                len(batch),
                processes,
                self.config.validation_threads,
            )

            completed_children = 0
            with ProcessPoolExecutor(max_workers=processes) as executor:
                futures = [
                    executor.submit(
                        validate_chunk,
                        chunk,
                        self.config.timeout,
                        self.config.socket_timeout,
                        self.config.test_url,
                        self.config.validation_threads,
                        self.config.batch_size,
                    )
                    for chunk in self.chunks(batch, processes)
                ]
                for future in as_completed(futures):
                    valid_chunk = future.result()
                    self.valid_proxies.update(valid_chunk)
                    completed_children += 1
                    LOGGER.info(
                        "Lote %s/%s hijo completado %s/%s - validos acumulados: %s",
                        batch_index,
                        len(validation_batches),
                        completed_children,
                        processes,
                        len(self.valid_proxies),
                    )
            total_validated += len(batch)
            LOGGER.info(
                "Lote %s/%s terminado - proxies procesados: %s/%s - validos acumulados: %s",
                batch_index,
                len(validation_batches),
                total_validated,
                len(proxy_list),
                len(self.valid_proxies),
            )
            if self.config.batch_pause > 0 and batch_index < len(validation_batches):
                LOGGER.info("Pausa de %.1f segundos antes del siguiente lote", self.config.batch_pause)
                time.sleep(self.config.batch_pause)

    def save_proxies(self) -> None:
        raw_list = sorted(self.proxies)
        valid_list = list(self.valid_proxies)
        random.shuffle(valid_list)

        self.config.raw_proxies_file.write_text("\n".join(raw_list) + "\n", encoding="utf-8")
        self.config.valid_proxies_file.write_text("\n".join(valid_list) + "\n", encoding="utf-8")
        self.save_proxy_lists(valid_list)
        valid_by_scheme: dict[str, int] = {}
        for proxy in valid_list:
            scheme = proxy_scheme(proxy)
            valid_by_scheme[scheme] = valid_by_scheme.get(scheme, 0) + 1
        LOGGER.info(
            "Proxies guardados: %s brutos en %s, %s validos en %s",
            len(raw_list),
            self.config.raw_proxies_file,
            len(valid_list),
            self.config.valid_proxies_file,
        )
        if valid_by_scheme:
            LOGGER.info(
                "Validos por protocolo: %s",
                ", ".join(f"{scheme}={count}" for scheme, count in sorted(valid_by_scheme.items())),
            )

    def save_proxy_lists(self, valid_list: Sequence[str]) -> None:
        root = self.config.proxy_list_dir
        root.mkdir(parents=True, exist_ok=True)

        by_scheme: dict[str, list[str]] = {}
        for proxy in valid_list:
            scheme = proxy_scheme(proxy)
            by_scheme.setdefault(scheme, []).append(proxy)

        for scheme in sorted(SUPPORTED_PROXY_SCHEMES | set(by_scheme)):
            proxies = sorted(by_scheme.get(scheme, []))
            (root / proxy_filename(scheme)).write_text(
                "\n".join(proxies) + ("\n" if proxies else ""),
                encoding="utf-8",
            )

        if not self.config.geo_enabled or not valid_list:
            return

        cache_path = root / "ipinfo_cache.json"
        cache = read_json_file(cache_path)
        ip_to_proxies: dict[str, list[str]] = {}
        for proxy in valid_list:
            parsed = parse_proxy(proxy)
            if parsed:
                _, host, _ = parsed
                ip_to_proxies.setdefault(host, []).append(proxy)

        missing = [ip for ip in ip_to_proxies if ip not in cache]
        if missing:
            LOGGER.info("Geolocalizando %s IPs con ipinfo", len(missing))
            workers = max(1, min(self.config.geo_workers, len(missing)))
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {executor.submit(ipinfo_lookup, ip, self.config.geo_timeout): ip for ip in missing}
                for future in as_completed(futures):
                    cache[futures[future]] = future.result()
            write_json_file(cache_path, cache)

        global_root = root / "Global"
        grouped: dict[str, dict[str, list[str]]] = {}
        for proxy in valid_list:
            parsed = parse_proxy(proxy)
            if not parsed:
                continue
            scheme, host, _ = parsed
            info = cache.get(host, {"country": "Unknown", "country_code": "XX"})
            country = safe_country_dir(info.get("country") or info.get("country_code") or "Unknown")
            grouped.setdefault(country, {}).setdefault(scheme, []).append(proxy)

        for country, schemes in grouped.items():
            country_dir = global_root / country
            country_dir.mkdir(parents=True, exist_ok=True)
            for scheme in sorted(SUPPORTED_PROXY_SCHEMES | set(schemes)):
                proxies = sorted(schemes.get(scheme, []))
                (country_dir / proxy_filename(scheme)).write_text(
                    "\n".join(proxies) + ("\n" if proxies else ""),
                    encoding="utf-8",
                )
        LOGGER.info("Listas por protocolo y pais guardadas en %s", root)

    def git_operations(self) -> None:
        files = [
            str(self.config.raw_proxies_file),
            str(self.config.valid_proxies_file),
            str(self.config.proxy_list_dir),
            str(Path(__file__).name),
        ]
        message = f"Actualizacion automatica proxies: {datetime.now().isoformat(timespec='seconds')}"
        commands = [
            ["git", "add", *files],
            ["git", "commit", "-m", message],
            ["git", "push"],
        ]
        for command in commands:
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            if result.stdout.strip():
                LOGGER.info(result.stdout.strip())
            if result.stderr.strip():
                LOGGER.info(result.stderr.strip())
        LOGGER.info("Cambios subidos a Git")

    def run(self) -> None:
        if self.config.low_priority:
            set_low_process_priority()
        LOGGER.info("Iniciando scraper multi proceso/multi hilo")
        self.scrape_all()
        self.validate_all()
        self.save_proxies()

        if self.config.git_enabled and self.valid_proxies:
            try:
                self.git_operations()
            except subprocess.CalledProcessError as exc:
                LOGGER.error("Error en Git: %s", exc)
        elif self.config.git_enabled:
            LOGGER.warning("No hay proxies validos para subir a Git")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scraper de proxies multi proceso y multi hilo basado en ultimater.py"
    )
    parser.add_argument("--sources", default="urls.txt", help="Archivo con URLs extra")
    parser.add_argument("--raw-out", default="proxies.txt", help="Archivo de proxies brutos")
    parser.add_argument("--valid-out", default="http.txt", help="Archivo de proxies validos")
    parser.add_argument("--proxy-list-dir", default="proxieslist", help="Carpeta para listas por protocolo y pais")
    parser.add_argument("--log-file", default="proxy_scraper.log", help="Archivo de log")
    parser.add_argument("--timeout", type=float, default=2.0, help="Timeout HTTP por request")
    parser.add_argument("--socket-timeout", type=float, default=1.0, help="Timeout del probe TCP")
    parser.add_argument("--scrape-workers", type=int, default=128, help="Hilos para scraping")
    parser.add_argument("--threads", type=int, default=128, help="Hilos por proceso hijo")
    parser.add_argument(
        "--processes",
        type=int,
        default=max(1, min(os.cpu_count() or 1, 4)),
        help="Procesos hijo para validacion",
    )
    parser.add_argument("--test-url", default="http://httpbin.org/ip", help="URL usada para validar")
    parser.add_argument(
        "--max-proxies",
        type=int,
        default=30_000,
        help="Tamano de lote de proxies a validar; 0 valida todos en un unico lote",
    )
    parser.add_argument(
        "--max-response-bytes",
        type=int,
        default=5_000_000,
        help="Maximo de bytes leidos por fuente; 0 no limita",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5_000,
        help="Tareas de validacion enviadas por lote dentro de cada hijo",
    )
    parser.add_argument(
        "--batch-pause",
        type=float,
        default=0.0,
        help="Segundos de pausa entre lotes de --max-proxies",
    )
    parser.add_argument(
        "--low-priority",
        action="store_true",
        help="Reduce la prioridad del proceso para afectar menos al sistema",
    )
    parser.add_argument("--no-geo", action="store_true", help="No geolocaliza proxies con ipinfo")
    parser.add_argument("--geo-workers", type=int, default=12, help="Hilos para ipinfo/geolocalizacion")
    parser.add_argument("--geo-timeout", type=float, default=3.0, help="Timeout por consulta ipinfo")
    parser.add_argument(
        "--no-github",
        action="store_true",
        help="Desactiva fuentes publicas de GitHub/raw sin API ni login",
    )
    parser.add_argument("--git", action="store_true", help="Hace git add/commit/push al terminar")
    return parser.parse_args()


def build_config(args: argparse.Namespace) -> Config:
    return Config(
        proxy_sources_file=Path(args.sources),
        raw_proxies_file=Path(args.raw_out),
        valid_proxies_file=Path(args.valid_out),
        proxy_list_dir=Path(args.proxy_list_dir),
        log_file=Path(args.log_file),
        timeout=args.timeout,
        socket_timeout=args.socket_timeout,
        scrape_workers=args.scrape_workers,
        validation_threads=args.threads,
        validation_processes=args.processes,
        max_validation_proxies=args.max_proxies,
        max_response_bytes=args.max_response_bytes,
        test_url=args.test_url,
        batch_size=args.batch_size,
        batch_pause=args.batch_pause,
        low_priority=args.low_priority,
        geo_enabled=not args.no_geo,
        geo_workers=args.geo_workers,
        geo_timeout=args.geo_timeout,
        github_sources=not args.no_github,
        git_enabled=args.git,
    )


if __name__ == "__main__":
    multiprocessing.freeze_support()
    cli_args = parse_args()
    cfg = build_config(cli_args)
    configure_logging(cfg.log_file)
    ProxyScraper(cfg).run()
