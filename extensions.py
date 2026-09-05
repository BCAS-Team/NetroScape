"""Small Chrome Web Store importer for the scripts QtWebEngine can run."""

from dataclasses import dataclass, field
import json
import logging
import re
import shutil
import struct
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen
import zipfile

from PySide6.QtWebEngineCore import QWebEngineScript

LOG = logging.getLogger("netroscape.extensions")
EXTENSIONS_DIR = Path(__file__).resolve().parent / "extensions"
STORE_DOWNLOAD_URL = ("https://clients2.google.com/service/update2/crx?response=redirect"
                      "&prodversion=120.0&acceptformat=crx3,crx2&x=id%3D{extension_id}%26uc")


@dataclass
class Extension:
    name: str
    version: str
    path: Path
    content_scripts: list[dict] = field(default_factory=list)
    enabled: bool = True
    description: str = ""
    permissions: list[str] = field(default_factory=list)
    optional_permissions: list[str] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)
    manifest: dict = field(default_factory=dict)


def extension_id_from_text(value: str) -> str:
    value = value.strip()
    parsed = urlparse(value)
    if parsed.netloc.endswith("chrome.google.com") or parsed.netloc.endswith("chromewebstore.google.com"):
        parts = [part for part in parsed.path.split("/") if part]
        value = parts[-1] if parts else ""
    elif parsed.scheme or parsed.netloc:
        value = parse_qs(parsed.query).get("id", [""])[0] or value
    if not re.fullmatch(r"[a-p]{32}", value):
        raise ValueError("Enter a valid 32-character Chrome Web Store extension ID or URL.")
    return value


def _zip_payload(data: bytes) -> bytes:
    if data[:4] == b"PK\x03\x04":
        return data
    if data[:4] != b"Cr24" or len(data) < 12:
        raise ValueError("The Web Store response is not a CRX or ZIP extension package.")
    version = struct.unpack_from("<I", data, 4)[0]
    if version == 2:
        public_key_size, signature_size = struct.unpack_from("<II", data, 8)
        offset = 16 + public_key_size + signature_size
    elif version == 3:
        offset = 12 + struct.unpack_from("<I", data, 8)[0]
    else:
        raise ValueError(f"Unsupported CRX version: {version}")
    if data[offset:offset + 4] != b"PK\x03\x04":
        raise ValueError("The CRX did not contain a ZIP payload.")
    return data[offset:]


class ExtensionManager:
    def __init__(self):
        self.extensions: list[Extension] = []
        EXTENSIONS_DIR.mkdir(exist_ok=True)

    def load(self):
        self.extensions = []
        for path in sorted(EXTENSIONS_DIR.iterdir()):
            if path.is_dir() and (path / "manifest.json").exists():
                try:
                    self.extensions.append(self._read_extension(path))
                except (OSError, ValueError, json.JSONDecodeError) as exc:
                    LOG.warning("Could not load extension %s: %s", path, exc)
        return self.extensions

    reload = load

    def _read_extension(self, path: Path) -> Extension:
        manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
        permissions = manifest.get("permissions", []) + manifest.get("host_permissions", [])
        optional_permissions = manifest.get("optional_permissions", [])
        unsupported = []
        if manifest.get("background") or manifest.get("background_service_worker"):
            unsupported.append("background scripts")
        return Extension(
            name=manifest.get("name", path.name),
            version=manifest.get("version", ""),
            path=path,
            content_scripts=manifest.get("content_scripts", []),
            description=manifest.get("description", ""),
            permissions=permissions,
            optional_permissions=optional_permissions,
            unsupported=unsupported,
            manifest=manifest,
        )

    def install_chrome_web_store(self, value: str) -> Extension:
        extension_id = extension_id_from_text(value)
        request = Request(STORE_DOWNLOAD_URL.format(extension_id=extension_id),
                          headers={"User-Agent": "Netroscape Extension Installer"})
        with urlopen(request, timeout=30) as response:
            payload = _zip_payload(response.read())
        target = EXTENSIONS_DIR / extension_id
        with NamedTemporaryFile(suffix=".zip", delete=False) as file:
            file.write(payload)
            temporary = Path(file.name)
        try:
            if target.exists():
                shutil.rmtree(target)
            target.mkdir()
            with zipfile.ZipFile(temporary) as archive:
                archive.extractall(target)
            extension = self._read_extension(target)
            if not extension.content_scripts:
                raise ValueError("This extension has no content scripts that Netroscape can import.")
            return extension
        except Exception:
            if target.exists():
                shutil.rmtree(target)
            raise
        finally:
            temporary.unlink(missing_ok=True)

    def set_enabled(self, extension: Extension, enabled: bool):
        extension.enabled = enabled

    def build_web_engine_scripts(self):
        scripts = []
        for extension in self.extensions:
            if not extension.enabled:
                continue
            for index, content_script in enumerate(extension.content_scripts):
                injection_point = {
                    "document_start": QWebEngineScript.InjectionPoint.DocumentCreation,
                    "document_end": QWebEngineScript.InjectionPoint.DocumentReady,
                    "document_idle": QWebEngineScript.InjectionPoint.Deferred,
                }.get(content_script.get("run_at", "document_idle"), QWebEngineScript.InjectionPoint.Deferred)
                for file_name in content_script.get("js", []):
                    script_path = extension.path / file_name
                    if not script_path.exists():
                        continue
                    script = QWebEngineScript()
                    script.setName(f"netroscape-ext::{extension.name}::{index}::{file_name}")
                    source = script_path.read_text(encoding="utf-8")
                    source = self._compatibility_shim(extension) + source
                    source = self._match_guard(content_script.get("matches", ["<all_urls>"]), source)
                    script.setSourceCode(source)
                    script.setInjectionPoint(injection_point)
                    script.setWorldId(QWebEngineScript.MainWorld)
                    script.setRunsOnSubFrames(content_script.get("all_frames", False))
                    scripts.append(script)
                for file_name in content_script.get("css", []):
                    css_path = extension.path / file_name
                    if not css_path.exists():
                        continue
                    css = json.dumps(css_path.read_text(encoding="utf-8"))
                    style_source = self._match_guard(
                        content_script.get("matches", ["<all_urls>"]),
                        f"const style = document.createElement('style'); style.textContent = {css}; document.documentElement.appendChild(style);",
                    )
                    style_script = QWebEngineScript()
                    style_script.setName(f"netroscape-ext::{extension.name}::{index}::{file_name}")
                    style_script.setSourceCode(style_source)
                    style_script.setInjectionPoint(injection_point)
                    style_script.setWorldId(QWebEngineScript.MainWorld)
                    style_script.setRunsOnSubFrames(content_script.get("all_frames", False))
                    scripts.append(style_script)
        return scripts

    def build_popup_script(self, extension: Extension, extension_root: str = "file:///") -> QWebEngineScript:
        script = QWebEngineScript()
        script.setName(f"netroscape-ext-popup::{extension.name}")
        script.setSourceCode(self._compatibility_shim(extension, extension_root))
        script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        script.setWorldId(QWebEngineScript.MainWorld)
        return script

    @staticmethod
    def _compatibility_shim(extension: Extension, extension_root: str = "") -> str:
        manifest = json.dumps(extension.manifest, separators=(",", ":"))
        permissions = json.dumps(extension.permissions, separators=(",", ":"))
        optional_permissions = json.dumps(extension.optional_permissions, separators=(",", ":"))
        extension_root = json.dumps(extension_root)
        return f"""
(function () {{
  if (!globalThis.chrome) globalThis.chrome = {{}};
  globalThis.browser = globalThis.chrome;
  if (!chrome.runtime) chrome.runtime = {{}};
    if (!chrome.runtime.getManifest) chrome.runtime.getManifest = () => ({manifest});
    if (!chrome.runtime.getURL) chrome.runtime.getURL = (path) => {extension_root} + String(path || '').replace(/^\\//, '');
  if (!chrome.runtime.onMessage) chrome.runtime.onMessage = {{ addListener: () => {{}} }};
  if (!chrome.runtime.sendMessage) chrome.runtime.sendMessage = () => Promise.resolve();
  if (!chrome.storage) chrome.storage = {{}};
  const storageKey = "netroscape-extension-{extension.name}";
  const readStorage = () => JSON.parse(localStorage.getItem(storageKey) || "{{}}");
  const sync = {{
    get: (keys, callback) => {{
      const stored = readStorage();
      const result = {{}};
      if (Array.isArray(keys)) keys.forEach((key) => {{ if (key in stored) result[key] = stored[key]; }});
      else if (typeof keys === "string") {{ if (keys in stored) result[keys] = stored[keys]; }}
      else Object.assign(result, stored, keys || {{}});
      if (typeof callback === "function") callback(result);
      return Promise.resolve(result);
    }},
    set: (values, callback) => {{
      localStorage.setItem(storageKey, JSON.stringify(Object.assign(readStorage(), values)));
      if (typeof callback === "function") callback();
      return Promise.resolve();
    }}
  }};
  if (!chrome.storage.sync) chrome.storage.sync = sync;
    const requiredPermissions = {permissions};
    const optionalPermissions = {optional_permissions};
    const permissionKey = "netroscape-extension-permissions-{extension.name}";
    const grantedPermissions = () => JSON.parse(localStorage.getItem(permissionKey) || "{{}}" );
    const permissionList = (value) => Array.isArray(value) ? value : [];
    if (!chrome.permissions) chrome.permissions = {{}};
    if (!chrome.permissions.contains) chrome.permissions.contains = (request, callback) => {{
        const granted = grantedPermissions();
        const requested = permissionList(request && request.permissions);
        const result = requested.every((permission) => requiredPermissions.includes(permission) || granted[permission] === true);
        if (typeof callback === "function") callback(result);
        return Promise.resolve(result);
    }};
    if (!chrome.permissions.request) chrome.permissions.request = (request, callback) => {{
        const requested = permissionList(request && request.permissions);
        const valid = requested.every((permission) => optionalPermissions.includes(permission) || requiredPermissions.includes(permission));
        const optionalRequested = requested.some((permission) => optionalPermissions.includes(permission));
        const allowed = valid && (!optionalRequested || window.confirm("Allow this extension to use: " + requested.join(", ") + "?"));
        if (allowed) {{
            const granted = grantedPermissions();
            requested.forEach((permission) => granted[permission] = true);
            localStorage.setItem(permissionKey, JSON.stringify(granted));
        }}
        if (typeof callback === "function") callback(allowed);
        return Promise.resolve(allowed);
    }};
    if (!chrome.permissions.remove) chrome.permissions.remove = (request, callback) => {{
        const granted = grantedPermissions();
        permissionList(request && request.permissions).forEach((permission) => delete granted[permission]);
        localStorage.setItem(permissionKey, JSON.stringify(granted));
        if (typeof callback === "function") callback(true);
        return Promise.resolve(true);
    }};
    if (!chrome.tabs) chrome.tabs = {{}};
    if (!chrome.tabs.query) chrome.tabs.query = (query, callback) => {{
        const tabs = [{{ id: 1, active: true, windowId: 1, url: location.href }}];
        if (typeof callback === "function") callback(tabs);
        return Promise.resolve(tabs);
    }};
    if (!chrome.tabs.create) chrome.tabs.create = (properties, callback) => {{
        const url = properties && properties.url;
        if (url) window.open(url, "_blank");
        const tab = {{ id: 1, active: true, windowId: 1, url: url || "about:blank" }};
        if (typeof callback === "function") callback(tab);
        return Promise.resolve(tab);
    }};
    if (!chrome.tabs.reload) chrome.tabs.reload = () => location.reload();
    if (!chrome.scripting) chrome.scripting = {{}};
    if (!chrome.scripting.executeScript) chrome.scripting.executeScript = () => Promise.resolve([]);
}})();
"""

    @staticmethod
    def _match_guard(matches: list[str], source: str) -> str:
        hosts = []
        for pattern in matches:
            if pattern == "<all_urls>":
                return source
            if "://" in pattern:
                host = pattern.split("://", 1)[1].split("/", 1)[0]
                hosts.append(host.removeprefix("*."))
        if not hosts:
            return source
        checks = " || ".join(
            f"location.hostname === {json.dumps(host)} || location.hostname.endsWith({json.dumps('.' + host)})"
            for host in hosts
        )
        return f"if ({checks}) {{\n{source}\n}}\n"
