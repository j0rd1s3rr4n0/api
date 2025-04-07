import requests
import re
import logging
import random
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from typing import List, Set, Dict, Callable

# Configuración optimizada
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('proxy_scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

CONFIG = {
    'PROXY_SOURCES_FILE': 'urls.txt',
    'RAW_PROXIES_FILE': 'proxies.txt',
    'VALID_PROXIES_FILE': 'http.txt',
    'GIT_REPO': 'https://github.com/j0rd1s3rr4n0/api.git',
    'TIMEOUT': 2,
    'MAX_WORKERS': 100,
    'TEST_URL': 'http://httpbin.org/ip',
    'SOCKET_TIMEOUT': 1,
    'BATCH_SIZE': 500
}

class ProxyScraper:
    def __init__(self):
        self.scraping_session = self.create_scraping_session()
        self.validation_session = self.create_validation_session()
        self.proxies: Set[str] = set()
        self.valid_proxies: Set[str] = set()
        self.scraping_sources = self.define_scraping_sources()
        
    def define_scraping_sources(self) -> Dict[str, Callable[[], List[str]]]:
        return {
            'proxyscrape': self.scrape_proxyscrape,
            'free-proxy-list': self.scrape_free_proxy_list,
            'sslproxies': self.scrape_sslproxies,
            'us-proxy': self.scrape_us_proxy,
            'openproxy': self.scrape_openproxy,
            'proxy-list.download': self.scrape_proxy_list_download,
            'custom_urls': self.scrape_custom_urls
        }

    def create_scraping_session(self) -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        return session

    def create_validation_session(self) -> requests.Session:
        session = requests.Session()
        adapter = HTTPAdapter(max_retries=0)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session

    # Métodos de scraping
    def scrape_proxyscrape(self) -> List[str]:
        urls = [
            "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all",
            "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=https&timeout=10000&country=all"
        ]
        return self.scrape_url_list(urls)

    def scrape_free_proxy_list(self) -> List[str]:
        return self.extract_proxies_from_url("https://free-proxy-list.net/")

    def scrape_sslproxies(self) -> List[str]:
        return self.extract_proxies_from_url("https://www.sslproxies.org/")

    def scrape_us_proxy(self) -> List[str]:
        return self.extract_proxies_from_url("https://www.us-proxy.org/")

    def scrape_openproxy(self) -> List[str]:
        urls = [
            "https://openproxy.space/list/http",
            "https://openproxy.space/list/https",
            "https://openproxy.space/list/socks4",
            "https://openproxy.space/list/socks5"
        ]
        return self.scrape_url_list(urls)

    def scrape_proxy_list_download(self) -> List[str]:
        urls = [
            "https://www.proxy-list.download/api/v1/get?type=http",
            "https://www.proxy-list.download/api/v1/get?type=https"
        ]
        return self.scrape_url_list(urls)

    def scrape_custom_urls(self) -> List[str]:
        try:
            with open(CONFIG['PROXY_SOURCES_FILE'], 'r') as f:
                urls = [line.strip() for line in f if line.strip()]
                return self.scrape_url_list(urls)
        except FileNotFoundError:
            logger.error(f"Archivo {CONFIG['PROXY_SOURCES_FILE']} no encontrado")
            return []

    # Helpers de scraping
    def extract_proxies_from_url(self, url: str) -> List[str]:
        try:
            response = self.scraping_session.get(url, timeout=CONFIG['TIMEOUT'])
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
                proxy = match.split('://')[1] if '://' in match else match
                proxies.add(proxy.strip())
        return list(proxies)

    # Validación
    def check_proxy_port(self, proxy: str) -> bool:
        try:
            ip, port = proxy.split(':')
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(CONFIG['SOCKET_TIMEOUT'])
                s.connect((ip, int(port)))
            return True
        except Exception:
            return False

    def validate_proxy(self, proxy: str) -> bool:
        if not self.check_proxy_port(proxy):
            return False
        
        try:
            proxies = {'http': f'http://{proxy}', 'https': f'http://{proxy}'}
            response = self.validation_session.head(
                CONFIG['TEST_URL'],
                proxies=proxies,
                timeout=CONFIG['TIMEOUT'],
                allow_redirects=False
            )
            return response.status_code == 200
        except Exception:
            return False

    def validate_proxies(self):
        logger.info(f"Iniciando validación de {len(self.proxies)} proxies...")
        proxy_list = list(self.proxies)
        random.shuffle(proxy_list)
        
        for i in range(0, len(proxy_list), CONFIG['BATCH_SIZE']):
            batch = proxy_list[i:i + CONFIG['BATCH_SIZE']]
            with ThreadPoolExecutor(max_workers=CONFIG['MAX_WORKERS']) as executor:
                futures = {executor.submit(self.validate_proxy, proxy): proxy for proxy in batch}
                for future in as_completed(futures):
                    proxy = futures[future]
                    if future.result():
                        self.valid_proxies.add(proxy)
            logger.info(f"Progreso: {len(self.valid_proxies)} válidos de {i + len(batch)} procesados")

    # Manejo de archivos y Git
    def save_proxies(self):
        try:
            with open(CONFIG['RAW_PROXIES_FILE'], 'w') as f:
                f.write('\n'.join(self.proxies))
            
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
            logger.info("Cambios subidos a Git")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error en Git: {str(e)}")
            subprocess.run(['git', 'reset', '--hard'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(['git', 'clean', '-fd'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Flujo principal
    def run(self):
        logger.info("Iniciando scraping de proxies")
        
        for name, scraper in self.scraping_sources.items():
            try:
                logger.info(f"Scrapeando {name}")
                proxies = scraper()
                self.proxies.update(proxies)
                logger.info(f"{name}: {len(proxies)} proxies encontrados")
            except Exception as e:
                logger.error(f"Error en {name}: {str(e)}")
        
        logger.info(f"Total de proxies encontrados: {len(self.proxies)}")
        
        self.validate_proxies()
        self.save_proxies()
        
        if self.valid_proxies:
            self.git_operations()
        else:
            logger.warning("No hay proxies válidos para subir a Git")

if __name__ == '__main__':
    scraper = ProxyScraper()
    scraper.run()