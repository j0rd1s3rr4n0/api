import csv
import html
import queue
import re
import threading
import time
import tkinter as tk
import webbrowser
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, urlparse
from urllib.request import Request, urlopen


APP_DIR = Path(__file__).resolve().parent
SEED_DORKS = APP_DIR / "dorks_seed.txt"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GoogleDorkAuditor/1.0"


TAG_RULES: list[tuple[str, list[str]]] = [
    (
        "directory_listing",
        [
            "index of",
            "parent directory",
            "?c=n;o=d",
            "?c=m;o=d",
            "directory listing",
            "directory: /",
            "name last modified size",
            "folder listing",
        ],
    ),
    ("opendir", ["open directory", "directory listing", "parent directory", "last modified", "size description"]),
    ("webdav", ["webdav", "dav:", "propfind", "mkcol", "lock", "unlock", "ms-author-via"]),
    ("admin_login", ["admin", "administrator", "login", "signin", "wp-login", "cpanel", "webmail"]),
    ("database_dump", [".sql", "mysql-dump", "dumping data", "insert into", "create table"]),
    ("config_secret", [".env", "db_password", "password=", "app_key", "wp-config", "web.config", ".ini", ".conf"]),
    ("logs", [".log", "access.log", "error.log", "debug.log", "trace"]),
    ("backup_archive", [".bak", ".old", ".backup", ".zip", ".tar", ".gz", ".7z", ".rar"]),
    ("source_control", ["/.git/", ".git/config", ".git/head", "/.svn/", "/.hg/"]),
    ("phpinfo", ["phpinfo", "php version", "zend scripting language"]),
    ("error_leak", ["fatal error", "warning:", "sql syntax", "odbc drivers error", "stack trace"]),
    ("document", [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".csv"]),
    ("cloud_bucket", ["amazonaws.com", "storage.googleapis.com", "blob.core.windows.net", "digitaloceanspaces.com"]),
    ("iot_camera", ["axis", "viewerframe", "view.shtml", "webcam", "ip camera", "live view"]),
    ("robots_sitemap", ["robots.txt", "sitemap.xml", "disallow:"]),
    ("api_surface", ["/api", "/graphql", "swagger", "openapi", "api-docs", "redoc", "postman"]),
    ("ci_cd", [".github", ".gitlab-ci", "jenkins", "circleci", "travis.yml", "azure-pipelines"]),
    ("package_manifest", ["package.json", "composer.json", "requirements.txt", "pom.xml", "gemfile", "go.mod"]),
    ("source_map", [".map", "sourceMappingURL", "webpack", "main.js.map"]),
    ("status_metrics", ["status", "metrics", "prometheus", "grafana", "kibana", "actuator", "health"]),
    ("cms_fingerprint", ["wordpress", "joomla", "drupal", "magento", "prestashop", "laravel", "symfony"]),
]


@dataclass
class Finding:
    source: str
    url: str
    title: str
    tags: str
    status: str = ""
    content_type: str = ""
    size: str = ""
    notes: str = ""


def normalize_quotes(text: str) -> str:
    replacements = {
        "«": '"',
        "»": '"',
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "–": "-",
        "—": "-",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text.strip()


def load_dorks(path: Path = SEED_DORKS) -> list[str]:
    if not path.exists():
        return []
    dorks = []
    seen = set()
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = normalize_quotes(line)
        if not line or line.startswith("#"):
            continue
        if line.lower() in seen:
            continue
        seen.add(line.lower())
        dorks.append(line)
    return dorks


def domain_from_input(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        raise ValueError("Indica un dominio objetivo autorizado.")
    if "://" in raw:
        parsed = urlparse(raw)
        raw = parsed.netloc
    raw = raw.strip().strip("/")
    if not re.match(r"^[A-Za-z0-9.-]+(:\d+)?$", raw):
        raise ValueError("Dominio invalido.")
    return raw


def google_url(query: str) -> str:
    return "https://www.google.com/search?q=" + quote_plus(query)


def build_query(dork: str, domain: str) -> str:
    dork = normalize_quotes(dork)
    if "site:" in dork.lower():
        return dork
    return f"site:{domain} {dork}"


def extract_urls(text: str) -> list[str]:
    pattern = re.compile(r"https?://[^\s<>'\"()]+", re.IGNORECASE)
    urls = []
    seen = set()
    for match in pattern.findall(text):
        url = match.rstrip(".,;]")
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def extract_title(body: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", body, re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    title = re.sub(r"\s+", " ", match.group(1))
    return html.unescape(title).strip()[:220]


def classify_text(*parts: str) -> str:
    haystack = " ".join(part or "" for part in parts).lower()
    tags = []
    for tag, needles in TAG_RULES:
        if any(needle.lower() in haystack for needle in needles):
            tags.append(tag)
    return ",".join(tags or ["unknown"])


def allowed_url_for_domain(url: str, domain: str) -> bool:
    parsed = urlparse(url)
    host = parsed.netloc.lower().split("@")[-1].split(":")[0]
    domain = domain.lower().split(":")[0]
    return host == domain or host.endswith("." + domain)


def fetch_finding(url: str, domain: str, timeout: float) -> Finding:
    if not allowed_url_for_domain(url, domain):
        return Finding("import", url, "", "out_of_scope", notes="Fuera del dominio objetivo")
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=timeout) as response:
            status = str(getattr(response, "status", ""))
            content_type = response.headers.get("Content-Type", "")
            size = response.headers.get("Content-Length", "")
            headers_text = "\n".join(f"{key}: {value}" for key, value in response.headers.items())
            body_bytes = response.read(300_000)
        body = body_bytes.decode("utf-8", errors="ignore")
        title = extract_title(body)
        dav_notes = probe_webdav(url, timeout)
        tags = classify_text(url, title, body[:50_000], content_type, headers_text, dav_notes)
        notes = dav_notes
        return Finding("fetch", url, title, tags, status, content_type, size, notes)
    except HTTPError as exc:
        return Finding("fetch", url, "", classify_text(url, str(exc)), str(exc.code), notes=str(exc))
    except (URLError, TimeoutError, OSError) as exc:
        return Finding("fetch", url, "", classify_text(url, str(exc)), notes=str(exc))


def method_request(url: str, method: str) -> Request:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    request.get_method = lambda: method
    return request


def probe_webdav(url: str, timeout: float) -> str:
    notes: list[str] = []
    try:
        with urlopen(method_request(url, "OPTIONS"), timeout=timeout) as response:
            allow = response.headers.get("Allow", "")
            dav = response.headers.get("DAV", "")
            ms_author = response.headers.get("MS-Author-Via", "")
            if dav:
                notes.append(f"DAV={dav}")
            if allow:
                notes.append(f"Allow={allow}")
            if ms_author:
                notes.append(f"MS-Author-Via={ms_author}")
            if any(method in allow.upper() for method in ["PROPFIND", "MKCOL", "LOCK", "UNLOCK", "PUT"]):
                notes.append("webdav_methods_visible")
    except Exception:
        pass

    try:
        with urlopen(method_request(url, "PROPFIND"), timeout=timeout) as response:
            status = getattr(response, "status", "")
            body = response.read(4096).decode("utf-8", errors="ignore")
            if status in {207, 200, 401, 403} or "multistatus" in body.lower():
                notes.append(f"PROPFIND={status}")
    except HTTPError as exc:
        if exc.code in {207, 401, 403, 405}:
            notes.append(f"PROPFIND={exc.code}")
    except Exception:
        pass

    return "; ".join(dict.fromkeys(notes))


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Google Dork Auditor")
        self.geometry("1240x760")
        self.minsize(980, 620)
        self.events: queue.Queue = queue.Queue()
        self.findings: list[Finding] = []
        self.dorks = load_dorks()

        self.domain_var = tk.StringVar()
        self.search_filter_var = tk.StringVar()
        self.tag_filter_var = tk.StringVar()
        self.timeout_var = tk.DoubleVar(value=10.0)
        self.threads_var = tk.IntVar(value=40)
        self.status_var = tk.StringVar(value="Listo")

        self.build_ui()
        self.load_dorks_into_list()
        self.after(150, self.poll_events)

    def build_ui(self) -> None:
        top = ttk.Frame(self, padding=10)
        top.pack(fill=tk.X)
        top.columnconfigure(1, weight=1)
        top.columnconfigure(4, weight=1)

        ttk.Label(top, text="Dominio autorizado").grid(row=0, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.domain_var).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(top, text="Abrir Google", command=self.open_selected_google).grid(row=0, column=2, padx=4)
        ttk.Button(top, text="Abrir lote", command=self.open_batch_google).grid(row=0, column=3, padx=4)
        ttk.Label(top, text="Buscar dork").grid(row=0, column=4, sticky="e")
        ttk.Entry(top, textvariable=self.search_filter_var).grid(row=0, column=5, sticky="ew", padx=6)
        ttk.Button(top, text="Filtrar", command=self.filter_dorks).grid(row=0, column=6, padx=4)

        pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        left = ttk.Frame(pane)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)
        dork_buttons = ttk.Frame(left)
        dork_buttons.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        ttk.Button(dork_buttons, text="Importar TXT", command=self.import_dorks).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(dork_buttons, text="Añadir pegado", command=self.add_pasted_dorks).pack(side=tk.LEFT, padx=4)
        ttk.Button(dork_buttons, text="Guardar lista", command=self.save_dorks).pack(side=tk.LEFT, padx=4)

        self.dork_list = tk.Listbox(left, selectmode=tk.EXTENDED)
        dork_scroll = ttk.Scrollbar(left, orient=tk.VERTICAL, command=self.dork_list.yview)
        self.dork_list.configure(yscrollcommand=dork_scroll.set)
        self.dork_list.grid(row=1, column=0, sticky="nsew")
        dork_scroll.grid(row=1, column=1, sticky="ns")
        pane.add(left, weight=1)

        right = ttk.Frame(pane)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(2, weight=1)

        paste_frame = ttk.LabelFrame(right, text="Resultados/URLs pegadas")
        paste_frame.columnconfigure(0, weight=1)
        paste_frame.rowconfigure(0, weight=1)
        paste_frame.grid(row=0, column=0, sticky="ew")
        self.paste_text = tk.Text(paste_frame, height=6, wrap="word")
        self.paste_text.grid(row=0, column=0, sticky="ew")

        actions = ttk.Frame(right)
        actions.grid(row=1, column=0, sticky="ew", pady=8)
        ttk.Button(actions, text="Categorizar pegado", command=self.classify_pasted).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(actions, text="Comprobar URLs", command=self.fetch_pasted_urls).pack(side=tk.LEFT, padx=4)
        ttk.Button(actions, text="Exportar CSV", command=self.export_csv).pack(side=tk.LEFT, padx=4)
        ttk.Button(actions, text="Limpiar resultados", command=self.clear_findings).pack(side=tk.LEFT, padx=4)
        ttk.Label(actions, text="Tag").pack(side=tk.LEFT, padx=(18, 4))
        ttk.Entry(actions, textvariable=self.tag_filter_var, width=18).pack(side=tk.LEFT)
        ttk.Button(actions, text="Filtrar tag", command=self.render_findings).pack(side=tk.LEFT, padx=4)
        ttk.Label(actions, text="Hilos").pack(side=tk.LEFT, padx=(18, 4))
        ttk.Spinbox(actions, textvariable=self.threads_var, from_=1, to=300, width=6).pack(side=tk.LEFT)
        ttk.Label(actions, text="Timeout").pack(side=tk.LEFT, padx=(10, 4))
        ttk.Spinbox(actions, textvariable=self.timeout_var, from_=1, to=60, width=6).pack(side=tk.LEFT)

        self.result_tree = ttk.Treeview(
            right,
            columns=("tags", "status", "type", "size", "title", "url", "notes"),
            show="headings",
        )
        for col, label, width in [
            ("tags", "Tags", 170),
            ("status", "HTTP", 60),
            ("type", "Content-Type", 160),
            ("size", "Size", 80),
            ("title", "Titulo", 260),
            ("url", "URL", 440),
            ("notes", "Notas", 220),
        ]:
            self.result_tree.heading(col, text=label)
            self.result_tree.column(col, width=width, stretch=(col in {"title", "url", "notes"}))
        result_scroll = ttk.Scrollbar(right, orient=tk.VERTICAL, command=self.result_tree.yview)
        self.result_tree.configure(yscrollcommand=result_scroll.set)
        self.result_tree.grid(row=2, column=0, sticky="nsew")
        result_scroll.grid(row=2, column=1, sticky="ns")
        self.result_tree.bind("<Double-1>", self.open_selected_result)
        pane.add(right, weight=3)

        ttk.Label(self, textvariable=self.status_var, anchor="w").pack(fill=tk.X, padx=10, pady=(0, 8))

    def load_dorks_into_list(self, items: list[str] | None = None) -> None:
        self.dork_list.delete(0, tk.END)
        for dork in items if items is not None else self.dorks:
            self.dork_list.insert(tk.END, dork)
        self.status_var.set(f"Dorks cargados: {self.dork_list.size()}")

    def selected_dorks(self) -> list[str]:
        indexes = self.dork_list.curselection()
        if indexes:
            return [self.dork_list.get(index) for index in indexes]
        item = self.dork_list.get(tk.ACTIVE)
        return [item] if item else []

    def get_domain(self) -> str | None:
        try:
            return domain_from_input(self.domain_var.get())
        except ValueError as exc:
            messagebox.showerror("Dominio requerido", str(exc))
            return None

    def open_selected_google(self) -> None:
        domain = self.get_domain()
        if not domain:
            return
        for dork in self.selected_dorks()[:1]:
            webbrowser.open_new_tab(google_url(build_query(dork, domain)))

    def open_batch_google(self) -> None:
        domain = self.get_domain()
        if not domain:
            return
        dorks = self.selected_dorks()
        if not dorks:
            messagebox.showinfo("Seleccion vacia", "Selecciona uno o varios dorks.")
            return
        if len(dorks) > 20 and not messagebox.askyesno("Abrir lote", f"Vas a abrir {len(dorks)} pestañas. Continuar?"):
            return
        for dork in dorks:
            webbrowser.open_new_tab(google_url(build_query(dork, domain)))
            time.sleep(0.1)

    def filter_dorks(self) -> None:
        needle = self.search_filter_var.get().strip().lower()
        if not needle:
            self.load_dorks_into_list()
            return
        self.load_dorks_into_list([dork for dork in self.dorks if needle in dork.lower()])

    def import_dorks(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if not path:
            return
        imported = load_dorks(Path(path))
        self.merge_dorks(imported)

    def add_pasted_dorks(self) -> None:
        raw = self.paste_text.get("1.0", tk.END)
        imported = [normalize_quotes(line) for line in raw.splitlines() if normalize_quotes(line)]
        self.merge_dorks(imported)

    def merge_dorks(self, imported: list[str]) -> None:
        seen = {dork.lower() for dork in self.dorks}
        added = 0
        for dork in imported:
            if dork.startswith("#") or dork.lower() in seen:
                continue
            self.dorks.append(dork)
            seen.add(dork.lower())
            added += 1
        self.load_dorks_into_list()
        self.status_var.set(f"Añadidos {added} dorks. Total: {len(self.dorks)}")

    def save_dorks(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            initialfile="dorks_custom.txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        Path(path).write_text("\n".join(self.dorks) + "\n", encoding="utf-8")
        self.status_var.set(f"Dorks guardados: {path}")

    def classify_pasted(self) -> None:
        raw = self.paste_text.get("1.0", tk.END)
        urls = extract_urls(raw)
        if urls:
            for url in urls:
                self.findings.append(Finding("paste", url, "", classify_text(url, raw)))
        else:
            for line in raw.splitlines():
                line = line.strip()
                if not line:
                    continue
                self.findings.append(Finding("paste", "", line[:220], classify_text(line), notes=line))
        self.render_findings()

    def fetch_pasted_urls(self) -> None:
        domain = self.get_domain()
        if not domain:
            return
        urls = extract_urls(self.paste_text.get("1.0", tk.END))
        if not urls:
            messagebox.showinfo("Sin URLs", "Pega URLs o resultados con URLs antes de comprobar.")
            return
        self.status_var.set(f"Comprobando {len(urls)} URLs...")
        thread = threading.Thread(target=self.fetch_worker, args=(urls, domain), daemon=True)
        thread.start()

    def fetch_worker(self, urls: list[str], domain: str) -> None:
        findings = []
        with ThreadPoolExecutor(max_workers=max(1, self.threads_var.get())) as executor:
            futures = [executor.submit(fetch_finding, url, domain, self.timeout_var.get()) for url in urls]
            for future in as_completed(futures):
                findings.append(future.result())
                self.events.put(("progress", len(findings), len(urls)))
        self.events.put(("fetched", findings))

    def clear_findings(self) -> None:
        self.findings.clear()
        self.render_findings()

    def render_findings(self) -> None:
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)
        tag_filter = self.tag_filter_var.get().strip().lower()
        visible = 0
        for finding in self.findings:
            if tag_filter and tag_filter not in finding.tags.lower():
                continue
            self.result_tree.insert(
                "",
                tk.END,
                values=(
                    finding.tags,
                    finding.status,
                    finding.content_type,
                    finding.size,
                    finding.title,
                    finding.url,
                    finding.notes,
                ),
            )
            visible += 1
        self.status_var.set(f"Resultados: {visible}/{len(self.findings)}")

    def export_csv(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialfile="dork_findings.csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        with Path(path).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["source", "url", "title", "tags", "status", "content_type", "size", "notes"],
            )
            writer.writeheader()
            for finding in self.findings:
                writer.writerow(finding.__dict__)
        self.status_var.set(f"CSV exportado: {path}")

    def open_selected_result(self, _event=None) -> None:
        item = self.result_tree.focus()
        if not item:
            return
        values = self.result_tree.item(item, "values")
        url = values[5] if len(values) > 5 else ""
        if url:
            webbrowser.open_new_tab(url)

    def poll_events(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == "progress":
                    self.status_var.set(f"Comprobadas {event[1]}/{event[2]} URLs")
                elif event[0] == "fetched":
                    self.findings.extend(event[1])
                    self.render_findings()
        except queue.Empty:
            pass
        self.after(150, self.poll_events)


if __name__ == "__main__":
    App().mainloop()
