import csv
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import proxy_atlas as proxy


class ProxyTests(unittest.TestCase):
    def test_go_response_must_cover_whole_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scraper = proxy.ProxyAtlas(proxy.Config(proxy_list_dir=root, valid_proxies_file=root/'valid.txt'))
            candidates = ['http://1.2.3.4:80', 'socks5://2.3.4.5:1080']
            output = '\n'.join(json.dumps({'proxy': p, 'valid': i == 0}) for i, p in enumerate(candidates))
            with patch.object(proxy.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, output, '')):
                self.assertEqual(scraper.validate_go(candidates), {candidates[0]})
            with patch.object(proxy.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, output.splitlines()[0], '')):
                with self.assertRaises(ValueError):
                    scraper.validate_go(candidates)

    def test_history_selection_is_bounded_and_rotates(self):
        with tempfile.TemporaryDirectory() as tmp:
            history = proxy.ProxyHistory(Path(tmp))
            candidates = [f'http://1.2.3.{i}:80' for i in range(1, 6)]
            history.observe(candidates)
            first = history.pending(2)
            self.assertEqual(len(first), 2)
            history.checked(first, [])
            second = history.pending(2)
            self.assertEqual(len(second), 2)
            self.assertTrue(first.isdisjoint(second))
            self.assertEqual(history.pending(0), set())
            self.assertEqual(history.pending(-1), set(candidates))

    def test_history_retains_dates_and_failed_proxies(self):
        with tempfile.TemporaryDirectory() as tmp:
            history = proxy.ProxyHistory(Path(tmp))
            endpoint = 'http://1.2.3.4:80'
            with patch.object(history, 'now', return_value='2026-10-01T00:00:00+00:00'):
                history.observe([endpoint])
                history.checked([endpoint], [endpoint])
            with patch.object(history, 'now', return_value='2026-10-02T00:00:00+00:00'):
                history.observe([endpoint])
                history.checked([endpoint], [])
            history = proxy.ProxyHistory(Path(tmp))
            history.export()
            with (Path(tmp)/'pool.csv').open(encoding='utf-8-sig', newline='') as stream:
                record = list(csv.DictReader(stream))[0]
            self.assertEqual(record['first_seen'], '2026-10-01T00:00:00+00:00')
            self.assertEqual(record['last_seen'], '2026-10-02T00:00:00+00:00')
            self.assertEqual(record['last_valid'], record['first_seen'])
            self.assertEqual(record['last_checked'], record['last_seen'])
            self.assertEqual(record['status'], 'invalid')
            self.assertEqual(record['checks'], '2')
            self.assertEqual(history.all_proxies(), {endpoint})

    def test_normalization(self):
        self.assertEqual(proxy.extract_proxies('1.2.3.4:8 1.2.3.4:8 socks5://2.3.4.5:1080'),
                         {'http://1.2.3.4:8', 'socks5://2.3.4.5:1080'})
        self.assertEqual(proxy.extract_proxies('999.2.3.4:80 1.2.3.4:999999'), set())
        self.assertIsNone(proxy.parse_proxy('http://1.2.3.4:99999'))
        self.assertIsNone(proxy.parse_proxy('http://1.2.3.4:abc'))
        self.assertEqual(proxy.infer_source_scheme('', 'https://example.com/socks5.txt'), 'socks5')

    def test_reports_and_stale_categories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scraper = proxy.ProxyAtlas(proxy.Config(proxy_list_dir=root, valid_proxies_file=root/'valid.txt'))
            info = {'country_code': 'ES', 'country': 'ES', 'city': 'Madrid',
                    'provider': 'Example Provider', 'asn': 'AS123', 'checked_at': proxy.time.time()}
            with patch.object(proxy, 'ipinfo_lookup', return_value=info) as lookup:
                scraper.save_proxy_lists(['http://1.2.3.4:80', 'socks5://1.2.3.4:1080'])
                self.assertEqual(lookup.call_count, 1)
            data = json.loads((root/'proxies.json').read_text())
            self.assertEqual(data[0]['provider'], 'Example Provider')
            self.assertEqual(data[0]['city'], 'Madrid')
            self.assertEqual(data[0]['country'], 'Spain')
            with (root/'proxies.csv').open(encoding='utf-8-sig', newline='') as stream:
                self.assertEqual(len(list(csv.DictReader(stream))), 2)
            self.assertTrue((root/'providers/AS123/http.txt').read_text())
            scraper.save_proxy_lists([])
            self.assertEqual((root/'countries/ES/http.txt').read_text(), '')
            self.assertEqual((root/'providers/AS123/http.txt').read_text(), '')
            self.assertEqual(json.loads((root/'proxies.json').read_text()), [])

    def test_cli_revalidates_previous_and_rejects_html(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"origin":"203.0.113.1"}' if self.server.valid else b'<html>Login</html>')
            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.valid = True
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                endpoint = f'http://127.0.0.1:{server.server_port}'
                (root/'input.txt').write_text(endpoint)
                command = [sys.executable, str(Path(proxy.__file__).resolve()), '--input', str(root/'input.txt'),
                           '--raw-out', str(root/'raw.txt'), '--valid-out', str(root/'valid.txt'),
                           '--proxy-list-dir', str(root/'lists'), '--log-file', str(root/'run.log'),
                           '--lock-file', str(root/'run.lock'), '--no-geo', '--processes', '1', '--threads', '1',
                           '--test-url', 'http://test.invalid/ip']
                command += ['--engine', os.environ.get('PROXY_ATLAS_TEST_ENGINE', 'python')]
                result = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual((root/'valid.txt').read_text().strip(), endpoint)
                server.valid = False
                result = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual((root/'valid.txt').read_text().strip(), '')
                self.assertFalse((root/'run.lock').exists())
                with (root/'history/pool.csv').open(encoding='utf-8-sig', newline='') as stream:
                    record = list(csv.DictReader(stream))[0]
                self.assertEqual(record['status'], 'invalid')
                self.assertTrue(record['last_valid'])
                self.assertEqual(record['checks'], '2')
                # A proxy absent from today's source and valid list remains in the
                # pool and is checked again, allowing it to recover.
                (root/'input.txt').write_text('')
                server.valid = True
                result = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual((root/'valid.txt').read_text().strip(), endpoint)
                with (root/'history/pool.csv').open(encoding='utf-8-sig', newline='') as stream:
                    recovered = list(csv.DictReader(stream))[0]
                self.assertEqual(recovered['first_seen'], record['first_seen'])
                self.assertEqual(recovered['last_seen'], record['last_seen'])
                self.assertEqual(recovered['status'], 'valid')
                self.assertEqual(recovered['checks'], '3')
        finally:
            server.shutdown()
            server.server_close()
            worker.join()


if __name__ == '__main__':
    unittest.main()
