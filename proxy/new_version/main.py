import os
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
from typing import List, Dict, Callable
import threading

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
    'RESULTS_DIR': 'results',
    'GEO_DIR': 'GeoProxy',
    'RAW_PROXIES_FILE': 'all.txt',
    'VALID_PROXIES_FILE': 'valid.txt',
    'INVALID_PROXIES_FILE': 'invalid.txt',
    'GIT_REPO': 'https://github.com/j0rd1s3rr4n0/api.git',
    'TIMEOUT': 2,
    'MAX_WORKERS': os.cpu_count() * 5,  # Ajuste automático basado en CPU
    'TEST_URL': 'http://httpbin.org/ip',
    'SOCKET_TIMEOUT': 1,
    'BATCH_SIZE': 500,
    'GEOLOCATION_API': 'http://ip-api.com/json/{}'
}

class ProxyScraper:
    def __init__(self):
        self.scraping_session = self.create_scraping_session()
        self.validation_session = self.create_validation_session()
        self.scraping_sources = self.define_scraping_sources()
        self.file_lock = threading.Lock()
        self.geo_lock = threading.Lock()
        self.init_filesystem()

    def init_filesystem(self):
        os.makedirs(CONFIG['RESULTS_DIR'], exist_ok=True)
        os.makedirs(CONFIG['GEO_DIR'], exist_ok=True)
        self.init_file(CONFIG['RAW_PROXIES_FILE'])
        self.init_file(CONFIG['VALID_PROXIES_FILE'])
        self.init_file(CONFIG['INVALID_PROXIES_FILE'])

    def init_file(self, filename):
        open(os.path.join(CONFIG['RESULTS_DIR'], filename), 'a').close()

    # ... (Mantener métodos create_scraping_session, create_validation_session, 
    # define_scraping_sources y métodos de scraping igual que antes)
    def create_validation_session(self) -> requests.Session:
        session = requests.Session()
        adapter = HTTPAdapter(max_retries=0)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session

    def define_scraping_sources(self) -> Dict[str, Callable[[], List[str]]]:
        return {
            'proxyscrape': self.scrape_proxyscrape,
            'free-proxy-list': self.scrape_free_proxy_list,
            # ... (resto de fuentes)
        }
    def process_proxies(self, proxies):
        with open(os.path.join(CONFIG['RESULTS_DIR'], CONFIG['RAW_PROXIES_FILE']), 'a') as f:
            f.write('\n'.join(proxies) + '\n')

    def validate_proxies(self):
        logger.info("Iniciando validación de proxies...")
        
        with ThreadPoolExecutor(max_workers=CONFIG['MAX_WORKERS']) as executor:
            with open(os.path.join(CONFIG['RESULTS_DIR'], CONFIG['RAW_PROXIES_FILE']), 'r') as all_file:
                batch = []
                for line in all_file:
                    proxy = line.strip()
                    if proxy:
                        batch.append(proxy)
                        if len(batch) >= CONFIG['BATCH_SIZE']:
                            self.process_batch(executor, batch)
                            batch = []
                if batch:
                    self.process_batch(executor, batch)

    def process_batch(self, executor, batch):
        futures = {executor.submit(self.validate_and_save_proxy, proxy): proxy for proxy in batch}
        for future in as_completed(futures):
            proxy = futures[future]
            try:
                future.result()
            except Exception as e:
                logger.error(f"Error validando {proxy}: {str(e)}")

    def validate_and_save_proxy(self, proxy):
        if self.validate_proxy(proxy):
            self.save_valid_proxy(proxy)
            self.save_geo_proxy(proxy)
        else:
            self.save_invalid_proxy(proxy)

    def save_valid_proxy(self, proxy):
        with self.file_lock:
            with open(os.path.join(CONFIG['RESULTS_DIR'], CONFIG['VALID_PROXIES_FILE']), 'a') as f:
                f.write(proxy + '\n')

    def save_invalid_proxy(self, proxy):
        with self.file_lock:
            with open(os.path.join(CONFIG['RESULTS_DIR'], CONFIG['INVALID_PROXIES_FILE']), 'a') as f:
                f.write(proxy + '\n')

    def save_geo_proxy(self, proxy):
        try:
            ip = proxy.split(':')[0]
            response = requests.get(CONFIG['GEOLOCATION_API'].format(ip), timeout=2)
            data = response.json()
            country = data.get('countryCode', 'unknown').lower()
            
            with self.geo_lock:
                geo_file = os.path.join(CONFIG['GEO_DIR'], f"{country}.txt")
                with open(geo_file, 'a') as f:
                    f.write(proxy + '\n')
        except Exception as e:
            logger.error(f"Error geolocalizando {proxy}: {str(e)}")

    def run(self):
        logger.info("Iniciando scraping de proxies")
        
        for name, scraper in self.scraping_sources.items():
            try:
                logger.info(f"Scrapeando {name}")
                proxies = scraper()
                self.process_proxies(proxies)
                logger.info(f"{name}: {len(proxies)} proxies encontrados")
            except Exception as e:
                logger.error(f"Error en {name}: {str(e)}")
        
        self.validate_proxies()
        
        if os.path.getsize(os.path.join(CONFIG['RESULTS_DIR'], CONFIG['VALID_PROXIES_FILE'])) > 0:
            self.git_operations()
        else:
            logger.warning("No hay proxies válidos para subir a Git")

if __name__ == '__main__':
    scraper = ProxyScraper()
    scraper.run()