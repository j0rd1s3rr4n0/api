import argparse
import csv
from contextlib import closing
import sys
import ipaddress
from itertools import islice
import json
import logging
import multiprocessing
import os
import random
import re
import socket
import sqlite3
import subprocess
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, ThreadPoolExecutor, as_completed, wait
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Sequence, Set
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


BASE_DIR = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent

LOGGER = logging.getLogger("proxy_scraper")
PROXY_PATTERN = re.compile(
    r"(?:(?P<scheme>https?|socks(?:4a?|5h?)|quic)://)?"
    r"(?P<host>\b\d{1,3}(?:\.\d{1,3}){3}\b):(?P<port>\d{1,5})(?!\d)",
    re.IGNORECASE,
)
THREAD_LOCAL = threading.local()
DEFAULT_PROXY_SCHEME = "http"
SUPPORTED_PROXY_SCHEMES = {"http", "https", "socks4", "socks4a", "socks5", "socks5h"}
# ISO 3166-1 countries and territories, plus XK and XX.
# Source: https://github.com/pycountry/pycountry
COUNTRY_NAMES = {
    "AD": "Andorra",
    "AE": "United Arab Emirates",
    "AF": "Afghanistan",
    "AG": "Antigua and Barbuda",
    "AI": "Anguilla",
    "AL": "Albania",
    "AM": "Armenia",
    "AO": "Angola",
    "AQ": "Antarctica",
    "AR": "Argentina",
    "AS": "American Samoa",
    "AT": "Austria",
    "AU": "Australia",
    "AW": "Aruba",
    "AX": "\u00c5land Islands",
    "AZ": "Azerbaijan",
    "BA": "Bosnia and Herzegovina",
    "BB": "Barbados",
    "BD": "Bangladesh",
    "BE": "Belgium",
    "BF": "Burkina Faso",
    "BG": "Bulgaria",
    "BH": "Bahrain",
    "BI": "Burundi",
    "BJ": "Benin",
    "BL": "Saint Barth\u00e9lemy",
    "BM": "Bermuda",
    "BN": "Brunei Darussalam",
    "BO": "Bolivia",
    "BQ": "Bonaire, Sint Eustatius and Saba",
    "BR": "Brazil",
    "BS": "Bahamas",
    "BT": "Bhutan",
    "BV": "Bouvet Island",
    "BW": "Botswana",
    "BY": "Belarus",
    "BZ": "Belize",
    "CA": "Canada",
    "CC": "Cocos (Keeling) Islands",
    "CD": "Congo, The Democratic Republic of the",
    "CF": "Central African Republic",
    "CG": "Congo",
    "CH": "Switzerland",
    "CI": "C\u00f4te d'Ivoire",
    "CK": "Cook Islands",
    "CL": "Chile",
    "CM": "Cameroon",
    "CN": "China",
    "CO": "Colombia",
    "CR": "Costa Rica",
    "CU": "Cuba",
    "CV": "Cabo Verde",
    "CW": "Cura\u00e7ao",
    "CX": "Christmas Island",
    "CY": "Cyprus",
    "CZ": "Czechia",
    "DE": "Germany",
    "DJ": "Djibouti",
    "DK": "Denmark",
    "DM": "Dominica",
    "DO": "Dominican Republic",
    "DZ": "Algeria",
    "EC": "Ecuador",
    "EE": "Estonia",
    "EG": "Egypt",
    "EH": "Western Sahara",
    "ER": "Eritrea",
    "ES": "Spain",
    "ET": "Ethiopia",
    "FI": "Finland",
    "FJ": "Fiji",
    "FK": "Falkland Islands (Malvinas)",
    "FM": "Micronesia, Federated States of",
    "FO": "Faroe Islands",
    "FR": "France",
    "GA": "Gabon",
    "GB": "United Kingdom",
    "GD": "Grenada",
    "GE": "Georgia",
    "GF": "French Guiana",
    "GG": "Guernsey",
    "GH": "Ghana",
    "GI": "Gibraltar",
    "GL": "Greenland",
    "GM": "Gambia",
    "GN": "Guinea",
    "GP": "Guadeloupe",
    "GQ": "Equatorial Guinea",
    "GR": "Greece",
    "GS": "South Georgia and the South Sandwich Islands",
    "GT": "Guatemala",
    "GU": "Guam",
    "GW": "Guinea-Bissau",
    "GY": "Guyana",
    "HK": "Hong Kong",
    "HM": "Heard Island and McDonald Islands",
    "HN": "Honduras",
    "HR": "Croatia",
    "HT": "Haiti",
    "HU": "Hungary",
    "ID": "Indonesia",
    "IE": "Ireland",
    "IL": "Israel",
    "IM": "Isle of Man",
    "IN": "India",
    "IO": "British Indian Ocean Territory",
    "IQ": "Iraq",
    "IR": "Iran",
    "IS": "Iceland",
    "IT": "Italy",
    "JE": "Jersey",
    "JM": "Jamaica",
    "JO": "Jordan",
    "JP": "Japan",
    "KE": "Kenya",
    "KG": "Kyrgyzstan",
    "KH": "Cambodia",
    "KI": "Kiribati",
    "KM": "Comoros",
    "KN": "Saint Kitts and Nevis",
    "KP": "North Korea",
    "KR": "South Korea",
    "KW": "Kuwait",
    "KY": "Cayman Islands",
    "KZ": "Kazakhstan",
    "LA": "Laos",
    "LB": "Lebanon",
    "LC": "Saint Lucia",
    "LI": "Liechtenstein",
    "LK": "Sri Lanka",
    "LR": "Liberia",
    "LS": "Lesotho",
    "LT": "Lithuania",
    "LU": "Luxembourg",
    "LV": "Latvia",
    "LY": "Libya",
    "MA": "Morocco",
    "MC": "Monaco",
    "MD": "Moldova",
    "ME": "Montenegro",
    "MF": "Saint Martin (French part)",
    "MG": "Madagascar",
    "MH": "Marshall Islands",
    "MK": "North Macedonia",
    "ML": "Mali",
    "MM": "Myanmar",
    "MN": "Mongolia",
    "MO": "Macao",
    "MP": "Northern Mariana Islands",
    "MQ": "Martinique",
    "MR": "Mauritania",
    "MS": "Montserrat",
    "MT": "Malta",
    "MU": "Mauritius",
    "MV": "Maldives",
    "MW": "Malawi",
    "MX": "Mexico",
    "MY": "Malaysia",
    "MZ": "Mozambique",
    "NA": "Namibia",
    "NC": "New Caledonia",
    "NE": "Niger",
    "NF": "Norfolk Island",
    "NG": "Nigeria",
    "NI": "Nicaragua",
    "NL": "Netherlands",
    "NO": "Norway",
    "NP": "Nepal",
    "NR": "Nauru",
    "NU": "Niue",
    "NZ": "New Zealand",
    "OM": "Oman",
    "PA": "Panama",
    "PE": "Peru",
    "PF": "French Polynesia",
    "PG": "Papua New Guinea",
    "PH": "Philippines",
    "PK": "Pakistan",
    "PL": "Poland",
    "PM": "Saint Pierre and Miquelon",
    "PN": "Pitcairn",
    "PR": "Puerto Rico",
    "PS": "Palestine, State of",
    "PT": "Portugal",
    "PW": "Palau",
    "PY": "Paraguay",
    "QA": "Qatar",
    "RE": "R\u00e9union",
    "RO": "Romania",
    "RS": "Serbia",
    "RU": "Russia",
    "RW": "Rwanda",
    "SA": "Saudi Arabia",
    "SB": "Solomon Islands",
    "SC": "Seychelles",
    "SD": "Sudan",
    "SE": "Sweden",
    "SG": "Singapore",
    "SH": "Saint Helena, Ascension and Tristan da Cunha",
    "SI": "Slovenia",
    "SJ": "Svalbard and Jan Mayen",
    "SK": "Slovakia",
    "SL": "Sierra Leone",
    "SM": "San Marino",
    "SN": "Senegal",
    "SO": "Somalia",
    "SR": "Suriname",
    "SS": "South Sudan",
    "ST": "Sao Tome and Principe",
    "SV": "El Salvador",
    "SX": "Sint Maarten (Dutch part)",
    "SY": "Syria",
    "SZ": "Eswatini",
    "TC": "Turks and Caicos Islands",
    "TD": "Chad",
    "TF": "French Southern Territories",
    "TG": "Togo",
    "TH": "Thailand",
    "TJ": "Tajikistan",
    "TK": "Tokelau",
    "TL": "Timor-Leste",
    "TM": "Turkmenistan",
    "TN": "Tunisia",
    "TO": "Tonga",
    "TR": "T\u00fcrkiye",
    "TT": "Trinidad and Tobago",
    "TV": "Tuvalu",
    "TW": "Taiwan",
    "TZ": "Tanzania",
    "UA": "Ukraine",
    "UG": "Uganda",
    "UM": "United States Minor Outlying Islands",
    "US": "United States",
    "UY": "Uruguay",
    "UZ": "Uzbekistan",
    "VA": "Holy See (Vatican City State)",
    "VC": "Saint Vincent and the Grenadines",
    "VE": "Venezuela",
    "VG": "Virgin Islands, British",
    "VI": "Virgin Islands, U.S.",
    "VN": "Vietnam",
    "VU": "Vanuatu",
    "WF": "Wallis and Futuna",
    "WS": "Samoa",
    "XK": "Kosovo",
    "XX": "Unknown",
    "YE": "Yemen",
    "YT": "Mayotte",
    "ZA": "South Africa",
    "ZM": "Zambia",
    "ZW": "Zimbabwe"
}


@dataclass(frozen=True)
class Config:
    proxy_sources_file: Path = BASE_DIR / "sources.txt"
    raw_proxies_file: Path = BASE_DIR / "results/candidates.txt"
    valid_proxies_file: Path = BASE_DIR / "results/valid.txt"
    proxy_list_dir: Path = BASE_DIR / "results/classified"
    log_file: Path = BASE_DIR / "logs/proxy_atlas.log"
    lock_file: Path = BASE_DIR / "proxy_atlas.lock"
    timeout: float = 2.0
    socket_timeout: float = 1.0
    scrape_workers: int = 128
    validation_threads: int = 128
    validation_processes: int = max(1, min(os.cpu_count() or 1, 4))
    max_validation_proxies: int = 30_000
    max_response_bytes: int = 5_000_000
    test_url: str = "https://httpbin.org/ip"
    batch_size: int = 5_000
    batch_pause: float = 0.0
    child_timeout: float = 0.0
    low_priority: bool = False
    geo_enabled: bool = True
    geo_workers: int = 12
    geo_timeout: float = 3.0
    github_sources: bool = True
    git_enabled: bool = False
    input_file: Path | None = None
    history_limit: int = 30000
    full_history: bool = False
    engine: str = "python"
    go_checker: Path = BASE_DIR / "golang_checker" / ("proxy_checker.exe" if os.name == "nt" else "proxy_checker")


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
    "https://raw.githubusercontent.com/ProxyAtlas/ProxyAtlas/main/http.txt",
    "https://raw.githubusercontent.com/ProxyAtlas/ProxyAtlas/main/socks4.txt",
    "https://raw.githubusercontent.com/ProxyAtlas/ProxyAtlas/main/socks5.txt",
]


def configure_logging(log_file: Path) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
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


def process_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            STILL_ACTIVE = 259
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not handle:
                return False
            exit_code = ctypes.c_ulong()
            try:
                if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                    return False
                return exit_code.value == STILL_ACTIVE
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def acquire_single_instance_lock(path: Path) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            pid_text = path.read_text(encoding="utf-8-sig", errors="ignore").strip().splitlines()[0]
            old_pid = int(pid_text)
        except Exception:
            old_pid = 0
        if process_is_running(old_pid):
            raise SystemExit(f"Ya hay una ejecucion activa de proxy_atlas.exe (PID {old_pid}).")
        LOGGER.warning("Lock stale encontrado, se reemplaza: %s", path)
        try:
            path.unlink()
        except OSError:
            pass
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(f"{os.getpid()}\n{datetime.now().isoformat()}\n")


def release_single_instance_lock(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass


def create_session(retries: int, timeout_pool: int) -> requests.Session:
    session = requests.Session()
    session.trust_env = False
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
    try:
        parsed = urlparse(candidate)
        port = parsed.port
    except ValueError:
        return None
    scheme = parsed.scheme.lower()
    if scheme not in SUPPORTED_PROXY_SCHEMES or not parsed.hostname or port is None:
        return None
    try:
        ipaddress.ip_address(parsed.hostname)
    except ValueError:
        return None
    if not 1 <= port <= 65535:
        return None
    return scheme, parsed.hostname, port


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


def ipinfo_lookup(ip: str, timeout: float) -> dict:
    try:
        headers = {}
        if os.environ.get("IPINFO_TOKEN"):
            headers["Authorization"] = "Bearer " + os.environ["IPINFO_TOKEN"]
        with create_session(0, 1) as session:
            response = session.get(f"https://ipinfo.io/{ip}/json", timeout=timeout, headers=headers)
            response.raise_for_status()
            data = response.json()
        if not isinstance(data, dict) or data.get("error") or data.get("bogon"):
            return {}
        code = str(data.get("country") or "XX").upper()
        org = str(data.get("org") or "")
        asn, _, provider = org.partition(" ")
        details = data.get("asn") or {}
        return {"country_code": code, "country": COUNTRY_NAMES.get(code, code),
                "region": data.get("region", ""), "city": data.get("city", ""),
                "location": data.get("loc", ""),
                "asn": details.get("asn", asn), "provider": details.get("name", provider) or "Unknown",
                "checked_at": time.time()}
    except (requests.RequestException, ValueError, TypeError, AttributeError):
        return {}


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
        try:
            if response.status_code != 200:
                return False
            payload = bytearray()
            for chunk in response.iter_content(4096):
                payload.extend(chunk)
                if len(payload) > 65536:
                    return False
            data = json.loads(payload)
            origins = data.get("origin", data.get("ip", ""))
            return bool(origins) and all(ipaddress.ip_address(ip.strip()) for ip in origins.split(","))
        finally:
            response.close()
    except (requests.RequestException, ValueError, TypeError, AttributeError):
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

    socket.setdefaulttimeout(max(timeout, socket_timeout, 1.0))
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


class ProxyHistory:
    """Persistent pool; only completed checks change validation status."""

    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        self.directory = directory
        self.path = directory / "pool.sqlite3"
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS proxies (
                proxy TEXT PRIMARY KEY, first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL, date_basis TEXT NOT NULL,
                last_checked TEXT, last_valid TEXT,
                status TEXT NOT NULL DEFAULT 'unverified',
                checks INTEGER NOT NULL DEFAULT 0)""")
            db.execute("CREATE INDEX IF NOT EXISTS idx_recheck ON proxies(last_checked, proxy)")

    @staticmethod
    def now():
        return datetime.now(timezone.utc).isoformat(timespec="microseconds")

    def observe(self, proxies, imported=False):
        timestamp = self.now()
        with closing(sqlite3.connect(self.path)) as db, db:
            db.executemany("""INSERT INTO proxies(proxy, first_seen, last_seen, date_basis)
                VALUES (?, ?, ?, ?) ON CONFLICT(proxy) DO UPDATE SET
                last_seen=excluded.last_seen WHERE excluded.date_basis='observed'""",
                ((p, timestamp, timestamp, "imported" if imported else "observed") for p in proxies))

    def pending(self, limit=30000):
        """Oldest checks first, including never checked entries; bounded memory."""
        with closing(sqlite3.connect(self.path)) as db:
            cursor = db.execute("SELECT proxy FROM proxies ORDER BY last_checked, proxy LIMIT ?", (limit,))
            return {row[0] for row in cursor}

    def all_proxies(self):
        return self.pending(-1)

    def checked(self, candidates, valid):
        timestamp = self.now()
        valid = set(valid)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.executemany("""UPDATE proxies SET last_checked=?, status=?, checks=checks+1,
                last_valid=CASE WHEN ? THEN ? ELSE last_valid END WHERE proxy=?""",
                ((timestamp, "valid" if p in valid else "invalid", p in valid, timestamp, p)
                 for p in candidates))

    def export(self):
        target = self.directory / "pool.csv"
        temporary = target.with_suffix(".csv.tmp")
        with closing(sqlite3.connect(self.path)) as db, temporary.open("w", encoding="utf-8-sig", newline="") as stream:
            cursor = db.execute("SELECT * FROM proxies")
            writer = csv.writer(stream)
            writer.writerow([column[0] for column in cursor.description])
            writer.writerows(cursor)
        temporary.replace(target)


class ProxyAtlas:
    def __init__(self, config: Config):
        self.config = config
        self.scraping_session = create_session(retries=0, timeout_pool=config.scrape_workers)
        self.proxies: Set[str] = set()
        self.valid_proxies: Set[str] = set()
        self.history = None
        self.sticky_valid_proxies: Set[str] = self.load_previous_valid_proxies()

    def load_previous_valid_proxies(self) -> Set[str]:
        candidates: Set[str] = set()
        paths = [self.config.valid_proxies_file]
        if self.config.proxy_list_dir.exists():
            paths.extend(self.config.proxy_list_dir.glob("*.txt"))
        for path in paths:
            try:
                for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                    raw = line.strip()
                    if not raw or raw.startswith("#"):
                        continue
                    parsed = parse_proxy(raw)
                    if parsed is None:
                        continue
                    scheme, host, port = parsed
                    proxy = normalize_proxy(host, str(port), scheme)
                    if proxy:
                        candidates.add(proxy)
            except OSError:
                continue
        if candidates:
            LOGGER.info("Proxies validos anteriores cargados para reutilizar: %s", len(candidates))
        return candidates

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
        return list({url: (source, url) for source, url in urls}.values())

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

    def validate_go(self, batch: Sequence[str]) -> Set[str]:
        command = [str(self.config.go_checker.resolve()), "-workers", str(self.config.validation_threads),
                   "-timeout", f"{self.config.timeout}s", "-connect-timeout", f"{self.config.socket_timeout}s",
                   "-test-url", self.config.test_url]
        deadline = self.config.child_timeout or max(
            60.0, (len(batch) / max(1, self.config.validation_threads) + 1) * self.config.timeout * 3)
        completed = subprocess.run(command, input="\n".join(batch) + "\n", encoding="utf-8",
                                   capture_output=True, check=True, timeout=deadline)
        expected = set(batch)
        seen = set()
        valid = set()
        for line in completed.stdout.splitlines():
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ValueError("Respuesta Go invalida")
            endpoint = record.get("proxy")
            if endpoint not in expected or endpoint in seen or type(record.get("valid")) is not bool:
                raise ValueError("Respuesta Go incompleta o inconsistente")
            seen.add(endpoint)
            if record["valid"]:
                valid.add(endpoint)
        if seen != expected:
            raise ValueError("Go no completo todas las comprobaciones; no se modifican sus estados")
        return valid

    def validate_all(self) -> None:
        self.proxies.update(self.sticky_valid_proxies)
        self.valid_proxies.clear()
        sticky_list = list(self.sticky_valid_proxies)
        new_list = list(self.proxies - self.sticky_valid_proxies)
        random.shuffle(sticky_list)
        random.shuffle(new_list)
        proxy_list = sticky_list + new_list
        if not proxy_list:
            LOGGER.warning("No hay proxies para validar")
            return
        if self.sticky_valid_proxies:
            LOGGER.info(
                "Reutilizando %s proxies validos previos y validandolos primero",
                len(self.sticky_valid_proxies),
            )

        if self.config.max_validation_proxies > 0 and len(proxy_list) > self.config.max_validation_proxies:
            LOGGER.info(
                "Validacion por lotes de %s proxies hasta completar %s encontrados "
                "(usa --max-proxies 0 para un unico lote completo)",
                self.config.max_validation_proxies,
                len(proxy_list),
            )

        batch_limit = self.config.max_validation_proxies if self.config.max_validation_proxies > 0 else len(proxy_list)
        batch_count = (len(proxy_list) + batch_limit - 1) // batch_limit
        validation_batches = (proxy_list[index:index + batch_limit]
                              for index in range(0, len(proxy_list), batch_limit))

        total_validated = 0
        for batch_index, batch in enumerate(validation_batches, start=1):
            if self.config.engine == "go":
                valid = self.validate_go(batch)
                if self.history:
                    self.history.checked(batch, valid)
                self.valid_proxies.update(valid)
                LOGGER.info("Go: lote %s/%s, %s validos de %s", batch_index, batch_count, len(valid), len(batch))
                if self.config.batch_pause > 0 and batch_index < batch_count:
                    time.sleep(self.config.batch_pause)
                continue
            processes = max(1, min(self.config.validation_processes, len(batch)))
            LOGGER.info(
                "Validando lote %s/%s: %s proxies con %s procesos hijo x %s hilos",
                batch_index,
                batch_count,
                len(batch),
                processes,
                self.config.validation_threads,
            )

            completed_children = 0
            child_timeout = self.config.child_timeout or max(
                60.0,
                (self.config.timeout + self.config.socket_timeout + 1.0)
                * max(1, len(batch) / max(1, self.config.validation_threads * processes))
                * 3.0,
            )
            executor = ProcessPoolExecutor(max_workers=processes)
            pending: set = set()
            try:
                futures = {
                    executor.submit(
                        validate_chunk,
                        chunk,
                        self.config.timeout,
                        self.config.socket_timeout,
                        self.config.test_url,
                        self.config.validation_threads,
                        self.config.batch_size,
                    ): chunk
                    for chunk in self.chunks(batch, processes)
                }
                pending = set(futures)
                deadline = time.monotonic() + child_timeout
                while pending:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        LOGGER.error(
                            "Lote %s/%s excedio %.1fs; cancelando %s hijos pendientes",
                            batch_index,
                            batch_count,
                            child_timeout,
                            len(pending),
                        )
                        for future in pending:
                            future.cancel()
                        break
                    done, pending = wait(pending, timeout=min(10.0, remaining), return_when=FIRST_COMPLETED)
                    if not done:
                        LOGGER.info(
                            "Lote %s/%s esperando hijos: pendientes=%s validos=%s",
                            batch_index,
                            batch_count,
                            len(pending),
                            len(self.valid_proxies),
                        )
                        continue
                    for future in done:
                        try:
                            valid_chunk = future.result()
                            if self.history:
                                self.history.checked(futures[future], valid_chunk)
                        except Exception as exc:
                            LOGGER.warning("Hijo de validacion fallo: %s", exc)
                            valid_chunk = []
                        self.valid_proxies.update(valid_chunk)
                        completed_children += 1
                        LOGGER.info(
                            "Lote %s/%s hijo completado %s/%s - validos acumulados: %s",
                            batch_index,
                            batch_count,
                            completed_children,
                            processes,
                            len(self.valid_proxies),
                        )
            finally:
                terminate = getattr(executor, "terminate_workers", None)
                kill = getattr(executor, "kill_workers", None)
                try:
                    if pending and callable(terminate):
                        terminate()
                    elif pending and callable(kill):
                        kill()
                    else:
                        executor.shutdown(wait=False, cancel_futures=True)
                except Exception:
                    executor.shutdown(wait=False, cancel_futures=True)
            total_validated += len(batch)
            LOGGER.info(
                "Lote %s/%s terminado - proxies procesados: %s/%s - validos acumulados: %s",
                batch_index,
                batch_count,
                total_validated,
                len(proxy_list),
                len(self.valid_proxies),
            )
            if self.config.batch_pause > 0 and batch_index < batch_count:
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

        for scheme in sorted(SUPPORTED_PROXY_SCHEMES | set(by_scheme) | {"quic"}):
            proxies = sorted(by_scheme.get(scheme, []))
            (root / proxy_filename(scheme)).write_text(
                "\n".join(proxies) + ("\n" if proxies else ""),
                encoding="utf-8",
            )

        cache_path = root / "ipinfo_cache.json"
        cache = read_json_file(cache_path)
        hosts = {parse_proxy(p)[1] for p in valid_list}
        missing = [ip for ip in sorted(hosts) if not isinstance(cache.get(ip), dict)
                   or time.time() - float(cache[ip].get("checked_at", 0)) > 604800]
        # Bound API usage per run; failed lookups are retried on the next run.
        if self.config.geo_enabled:
            with ThreadPoolExecutor(max_workers=max(1, self.config.geo_workers)) as executor:
                futures = {executor.submit(ipinfo_lookup, ip, self.config.geo_timeout): ip for ip in missing[:1000]}
                for future in as_completed(futures):
                    info = future.result()
                    if info:
                        cache[futures[future]] = info
            write_json_file(cache_path, cache)
        records = []
        grouped = {}
        for proxy in sorted(valid_list):
            scheme, host, port = parse_proxy(proxy)
            info = cache.get(host, {}) if self.config.geo_enabled else {}
            record = {"proxy": proxy, "protocol": scheme, "ip": host, "port": port,
                      "country_code": info.get("country_code", "XX"),
                      "country": COUNTRY_NAMES.get(str(info.get("country_code", "XX")).upper(), info.get("country", "Unknown")),
                      "region": info.get("region", ""), "city": info.get("city", ""),
                      "location": info.get("location", ""), "asn": info.get("asn", ""),
                      "provider": info.get("provider", "Unknown")}
            records.append(record)
            for category, value in [("countries", record["country_code"]),
                                    ("providers", record["asn"] or "Unknown")]:
                relative = f"{category}/{safe_country_dir(value)}/{scheme}.txt"
                grouped.setdefault(relative, []).append(proxy)
        # Clear only generated category lists, including countries no longer present.
        for category in ("countries", "providers"):
            for old in (root / category).glob("*/*.txt"):
                if old.stem in SUPPORTED_PROXY_SCHEMES | {"quic"}:
                    old.write_text("", encoding="utf-8")
        for relative, proxies in grouped.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("\n".join(proxies) + "\n", encoding="utf-8")
        fields = ["proxy", "protocol", "ip", "port", "country_code", "country", "region", "city", "location", "asn", "provider"]
        with (root / "proxies.csv").open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(records)
        (root / "proxies.json").write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        LOGGER.info("Informes CSV/JSON y listas por protocolo, pais y ASN: %s", root)

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
        if self.config.engine == "go" and not self.config.go_checker.is_file():
            raise FileNotFoundError(f"Compila golang_checker primero: {self.config.go_checker}")
        if self.config.low_priority:
            set_low_process_priority()
        LOGGER.info("Iniciando scraper multi proceso/multi hilo")
        for path in (self.config.raw_proxies_file, self.config.valid_proxies_file):
            path.parent.mkdir(parents=True, exist_ok=True)
        history_dir = (BASE_DIR / "history" if self.config.raw_proxies_file.resolve() ==
                       (BASE_DIR / "results/candidates.txt").resolve()
                       else self.config.raw_proxies_file.parent / "history")
        first_import = not (history_dir / "pool.sqlite3").exists()
        self.history = ProxyHistory(history_dir)
        # Import existing candidates before the current raw snapshot is overwritten.
        if first_import and self.config.raw_proxies_file.exists():
            with self.config.raw_proxies_file.open(encoding="utf-8-sig", errors="replace") as stream:
                for lines in iter(lambda: list(islice(stream, 10000)), []):
                    self.history.observe(extract_proxies("".join(lines)), imported=True)
        self.history.observe(self.sticky_valid_proxies, imported=True)
        if self.config.input_file:
            self.proxies.update(extract_proxies(self.config.input_file.read_text(encoding="utf-8-sig")))
        else:
            self.scrape_all()
        self.history.observe(self.proxies)
        self.proxies.update(self.history.pending(-1 if self.config.full_history else self.config.history_limit))
        try:
            self.validate_all()
            self.save_proxies()
        finally:
            self.history.export()

        if self.config.git_enabled and self.valid_proxies:
            try:
                self.git_operations()
            except subprocess.CalledProcessError as exc:
                LOGGER.error("Error en Git: %s", exc)
        elif self.config.git_enabled:
            LOGGER.warning("No hay proxies validos para subir a Git")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="proxy-atlas",
        description="Proxy Atlas: pool historico, validacion y clasificacion de proxies"
    )
    parser.add_argument("--engine", choices=("python", "go"), default="python", help="Motor de validacion")
    parser.add_argument("--go-checker", type=Path, default=Config.go_checker, help="Ruta al ejecutable Go")
    parser.add_argument("--history-limit", type=int, default=30000, help="Historicos a revalidar por ejecucion, empezando por los mas antiguos")
    parser.add_argument("--full-history", action="store_true", help="Revalidar todo el pool (puede tardar horas)")
    parser.add_argument("--input", type=Path, help="Lista local; omite scraping remoto")
    parser.add_argument("--sources", default=str(BASE_DIR / "sources.txt"), help="Archivo con URLs extra")
    parser.add_argument("--raw-out", default=str(BASE_DIR / "results/candidates.txt"), help="Archivo de proxies brutos")
    parser.add_argument("--valid-out", default=str(BASE_DIR / "results/valid.txt"), help="Archivo de proxies validos")
    parser.add_argument("--proxy-list-dir", default=str(BASE_DIR / "results/classified"), help="Carpeta para listas por protocolo y pais")
    parser.add_argument("--log-file", default=str(BASE_DIR / "logs/proxy_atlas.log"), help="Archivo de log")
    parser.add_argument("--lock-file", default=str(BASE_DIR / "proxy_atlas.lock"), help="Lock para evitar ejecuciones solapadas")
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
    parser.add_argument("--test-url", default="https://httpbin.org/ip", help="URL usada para validar")
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
        "--child-timeout",
        type=float,
        default=0.0,
        help="Timeout duro por lote de procesos hijo; 0 calcula uno conservador",
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
    args = parser.parse_args()
    for name in ("timeout", "socket_timeout", "scrape_workers", "threads", "processes", "batch_size", "geo_workers", "geo_timeout"):
        if getattr(args, name) <= 0:
            parser.error(f"--{name.replace('_', '-')} debe ser mayor que cero")
    for name in ("max_proxies", "max_response_bytes", "batch_pause", "child_timeout", "history_limit"):
        if getattr(args, name) < 0:
            parser.error(f"--{name.replace('_', '-')} no puede ser negativo")
    if args.input and not args.input.is_file():
        parser.error("El archivo --input no existe")
    if args.engine == "go" and (args.threads > 4096 or not args.go_checker.is_file()):
        parser.error("Go requiere un ejecutable --go-checker existente y --threads entre 1 y 4096")
    return args


def build_config(args: argparse.Namespace) -> Config:
    return Config(
        engine=args.engine,
        go_checker=args.go_checker,
        input_file=args.input,
        history_limit=args.history_limit,
        full_history=args.full_history,
        proxy_sources_file=Path(args.sources),
        raw_proxies_file=Path(args.raw_out),
        valid_proxies_file=Path(args.valid_out),
        proxy_list_dir=Path(args.proxy_list_dir),
        log_file=Path(args.log_file),
        lock_file=Path(args.lock_file),
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
        child_timeout=args.child_timeout,
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
    acquire_single_instance_lock(cfg.lock_file)
    try:
        ProxyAtlas(cfg).run()
    finally:
        release_single_instance_lock(cfg.lock_file)
