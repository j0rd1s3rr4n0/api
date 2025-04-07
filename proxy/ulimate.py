import requests
import re
import os
import logging
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import subprocess
import socket
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from typing import List, Set, Dict, Callable

# Configuración inicial
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('proxy_scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constantes
CONFIG = {
    'PROXY_SOURCES_FILE': 'urls.txt',
    'RAW_PROXIES_FILE': 'proxies.txt',
    'VALID_PROXIES_FILE': 'http.txt',
    'GIT_REPO': 'https://github.com/tu_usuario/tu_repo.git',
    'TIMEOUT': 10,
    'MAX_WORKERS': 50,
    'TEST_URLS': [
        'http://httpbin.org/ip',
        'http://example.com',
        'http://google.com'
    ]
}

# Tipos personalizados
ProxySource = Dict[str, Callable[[requests.Session], List[str]]]

class ProxyScraper:
    def __init__(self):
        self.session = self.create_session()
        self.proxies: Set[str] = set()
        self.valid_proxies: Set[str] = set()
        self.scraping_sources = self.define_scraping_sources()
        
    def create_session(self) -> requests.Session:
        """Crea una sesión HTTP con configuración de reintentos"""
        session = requests.Session()
        retry = Retry(
            total=5,
            backoff_factor=0.3,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=['HEAD', 'GET', 'OPTIONS']
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        return session

    def define_scraping_sources(self) -> ProxySource:
        """Define todas las fuentes de scraping de proxies"""
        return {
            'proxyscrape': self.scrape_proxyscrape,
            'free-proxy-list': self.scrape_free_proxy_list,
            'sslproxies': self.scrape_sslproxies,
            'us-proxy': self.scrape_us_proxy,
            'openproxy': self.scrape_openproxy,
            'proxy-list.download': self.scrape_proxy_list_download,
            'custom_urls': self.scrape_custom_urls
        }

    # Métodos de scraping específicos
    def scrape_proxyscrape(self, session: requests.Session) -> List[str]:
        urls = [
            "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all",
            "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=https&timeout=10000&country=all"
        ]
        return self.scrape_url_list(urls)

    def scrape_free_proxy_list(self, session: requests.Session) -> List[str]:
        return self.extract_proxies_from_url("https://free-proxy-list.net/")

    def scrape_sslproxies(self, session: requests.Session) -> List[str]:
        return self.extract_proxies_from_url("https://www.sslproxies.org/")

    def scrape_us_proxy(self, session: requests.Session) -> List[str]:
        return self.extract_proxies_from_url("https://www.us-proxy.org/")

    def scrape_openproxy(self, session: requests.Session) -> List[str]:
        urls = [
            "https://openproxy.space/list/http",
            "https://openproxy.space/list/https",
            "https://openproxy.space/list/socks4",
            "https://openproxy.space/list/socks5"
        ]
        return self.scrape_url_list(urls)

    def scrape_proxy_list_download(self, session: requests.Session) -> List[str]:
        urls = [
            "https://www.proxy-list.download/api/v1/get?type=http",
            "https://www.proxy-list.download/api/v1/get?type=https"
        ]
        return self.scrape_url_list(urls)

    def scrape_custom_urls(self, session: requests.Session) -> List[str]:
        try:
            with open(CONFIG['PROXY_SOURCES_FILE'], 'r') as f:
                urls = [line.strip() for line in f if line.strip()]
                return self.scrape_url_list(urls)
        except FileNotFoundError:
            logger.error(f"Archivo {CONFIG['PROXY_SOURCES_FILE']} no encontrado")
            return []

    # Métodos auxiliares de scraping
    def extract_proxies_from_url(self, url: str) -> List[str]:
        try:
            response = self.session.get(url, timeout=CONFIG['TIMEOUT'])
            return self.extract_proxies(response.text)
        except Exception as e:
            logger.error(f"Error scraping {url}: {str(e)}")
            return []

    def scrape_url_list(self, urls: List[str]) -> List[str]:
        proxies = []
        with ThreadPoolExecutor(max_workers=CONFIG['MAX_WORKERS']) as executor:
            futures = [executor.submit(self.extract_proxies_from_url, url) for url in urls]
            for future in as_completed(futures):
                proxies.extend(future.result())
        return proxies

    @staticmethod
    def extract_proxies(content: str) -> List[str]:
        proxies = set()
        patterns = [
            r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+\b',
            r'(?:http|https|socks4|socks5)://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+'
        ]
        for pattern in patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if '://' in match:
                    proxy = match.split('://')[1]
                else:
                    proxy = match
                proxies.add(proxy.strip())
        return list(proxies)

    # Validación de proxies
    def validate_proxy(self, proxy: str) -> bool:
        try:
            proxies = {
                'http': f'http://{proxy}',
                'https': f'http://{proxy}'
            }
            for test_url in CONFIG['TEST_URLS']:
                response = requests.get(
                    test_url,
                    proxies=proxies,
                    timeout=CONFIG['TIMEOUT']
                )
                if response.status_code != 200:
                    return False
            return True
        except Exception as e:
            logger.debug(f"Proxy fallido {proxy}: {str(e)}")
            return False

    def validate_proxies(self):
        logger.info("Iniciando validación de proxies...")
        with ThreadPoolExecutor(max_workers=CONFIG['MAX_WORKERS']) as executor:
            futures = {executor.submit(self.validate_proxy, proxy): proxy for proxy in self.proxies}
            for future in as_completed(futures):
                proxy = futures[future]
                try:
                    if future.result():
                        self.valid_proxies.add(proxy)
                except Exception as e:
                    logger.error(f"Error validando proxy: {str(e)}")

    # Manejo de archivos y Git
    def save_proxies(self):
        try:
            # Guardar proxies brutos
            with open(CONFIG['RAW_PROXIES_FILE'], 'w') as f:
                f.write('\n'.join(self.proxies))
            
            # Guardar proxies válidos mezclados
            valid_list = list(self.valid_proxies)
            random.shuffle(valid_list)
            with open(CONFIG['VALID_PROXIES_FILE'], 'w') as f:
                f.write('\n'.join(valid_list))
            
            logger.info(f"Proxies guardados: {len(self.proxies)} brutos, {len(valid_list)} válidos")
        except Exception as e:
            logger.error(f"Error guardando proxies: {str(e)}")

    def git_operations(self):
        try:
            subprocess.run(['git', 'config', '--global', 'user.email', 'proxy-updater@example.com'], check=True)
            subprocess.run(['git', 'config', '--global', 'user.name', 'Proxy Updater'], check=True)
            
            subprocess.run(['git', 'add', '.'], check=True)
            subprocess.run(['git', 'commit', '-m', f'Actualización automática: {datetime.now().isoformat()}'], check=True)
            subprocess.run(['git', 'push'], check=True)
            logger.info("Cambios subidos a Git exitosamente")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error en operaciones Git: {str(e)}")
            logger.error("Realizando limpieza...")
            subprocess.run(['git', 'reset', '--hard'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(['git', 'clean', '-fd'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Flujo principal
    def run(self):
        logger.info("Iniciando proceso de scraping de proxies")
        
        # Scraping de todas las fuentes
        for name, scraper in self.scraping_sources.items():
            try:
                logger.info(f"Scraping fuente: {name}")
                proxies = scraper(self.session)
                self.proxies.update(proxies)
                logger.info(f"Fuente {name}: {len(proxies)} proxies encontrados")
            except Exception as e:
                logger.error(f"Error en fuente {name}: {str(e)}")
        
        logger.info(f"Proxies totales encontrados: {len(self.proxies)}")
        
        # Validación
        self.validate_proxies()
        
        # Guardado
        self.save_proxies()
        
        # Operaciones Git
        if self.valid_proxies:
            self.git_operations()
        else:
            logger.warning("No se encontraron proxies válidos. Saltando Git.")

if __name__ == '__main__':
    scraper = ProxyScraper()
    scraper.run()