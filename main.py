"""
Netroscape 0.3B "Cookie" - IE8-style Chromium browser

Same CSS-injection engine as before, now wrapped in an XP Luna /
Internet Explorer 8 style shell: custom blue-gradient title bar,
classic menu bar (File/Edit/View/Favorites/Tools/Help), an IE8-style
toolbar with an address bar, curved multi-tab browsing, and a sunken
status bar.

Run it with:
    python main.py
"""

import logging
import os
import platform
import shutil
import sys
import http.server
import socketserver

from PySide6.QtCore import QProcess, QUrl, Qt, qVersion
from PySide6.QtGui import QAction, QColor, QDesktopServices, QIcon, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QToolButton,
    QToolBar,
    QTabWidget,
    QTabBar,
    QStatusBar,
    QLabel,
    QMenuBar,
    QMessageBox,
    QInputDialog,
    QFileDialog,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QStyle,
)
from PySide6.QtWebEngineCore import (
    QWebEngineDownloadRequest,
    QWebEnginePage,
    QWebEngineProfile,
    QWebEngineUrlRequestInterceptor,
    QWebEngineScript,
)
from PySide6.QtWebEngineWidgets import QWebEngineView

from theme_loader import get_injection_script_for_url
from extensions import EXTENSIONS_DIR, Extension, ExtensionManager
from server import HOST as LOCAL_SERVER_HOST, PORT as LOCAL_SERVER_PORT, start_server
from title_bar import TitleBar
from xp_theme import (
    ADDRESS_BAR_WIDTH,
    GO_BUTTON_WIDTH,
    TAB_CLOSE_SIZE,
    TOOLBAR_BUTTON_HEIGHT,
    TOOLBAR_BUTTON_WIDTH,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
    STYLESHEET,
    icon_path,
)

HOME_URL = f"http://{LOCAL_SERVER_HOST}:{LOCAL_SERVER_PORT}/google/"
DISPLAY_URL = "https://google.com"
WINDOW_TITLE = "Netroscape 0.4 - Cookie"
VERSION = "0.4"
VERSION_NAME = "Cookie"
AUTHOR = "BCAS-Team"

LOG = logging.getLogger("netroscape")


class BuiltInAdBlocker(QWebEngineUrlRequestInterceptor):
    """Small native blocker for common advertising and tracking requests."""

    _blocked_hosts = frozenset(
        {
            "doubleclick.net",
            "googlesyndication.com",
            "googleadservices.com",
            "adservice.google.com",
            "adnxs.com",
            "adsrvr.org",
            "advertising.com",
            "taboola.com",
            "outbrain.com",
        }
    )
    _blocked_url_parts = ("/pagead/", "/ads/", "/adserver/", "doubleclick", "googlesyndication")

    def interceptRequest(self, info):
        url = info.requestUrl()
        host = url.host().lower().rstrip(".")
        is_blocked_host = any(host == blocked or host.endswith("." + blocked) for blocked in self._blocked_hosts)
        if is_blocked_host or any(part in url.toString().lower() for part in self._blocked_url_parts):
            info.block(True)

def build_spacehey_geolocation_script():
    script = QWebEngineScript()
    script.setName("netroscape-built-in::spacehey-uk-geolocation")
    script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
    script.setWorldId(QWebEngineScript.MainWorld)
    script.setSourceCode(
        """
(function () {
    const host = location.hostname.toLowerCase();
    if (host !== "spacehey.com" && !host.endsWith(".spacehey.com")) return;

    const position = {
        coords: {
            latitude: 51.5074,
            longitude: -0.1278,
            accuracy: 100,
            altitude: null,
            altitudeAccuracy: null,
            heading: null,
            speed: null
        },
        timestamp: Date.now()
    };
    const geolocation = {
        getCurrentPosition: (success) => {
            if (typeof success === "function") success(position);
        },
        watchPosition: (success) => {
            if (typeof success === "function") success(position);
            return 1;
        },
        clearWatch: () => {}
    };
    Object.defineProperty(Navigator.prototype, "geolocation", {
        configurable: true,
        get: () => geolocation
    });
    if (navigator.permissions && navigator.permissions.query) {
        const originalQuery = navigator.permissions.query.bind(navigator.permissions);
        navigator.permissions.query = (parameters) => {
            if (parameters && parameters.name === "geolocation") {
                return Promise.resolve({ state: "granted", onchange: null });
            }
            return originalQuery(parameters);
        };
    }
})();
"""
    )
    return script


def build_light_mode_script():
    script = QWebEngineScript()
    script.setName("netroscape-built-in::light-mode")
    script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
    script.setWorldId(QWebEngineScript.MainWorld)
    script.setSourceCode(
        """
(function () {
    const originalMatchMedia = window.matchMedia.bind(window);
    window.matchMedia = (query) => {
        if (query.includes('prefers-color-scheme')) {
            const prefersLight = query.includes('light');
            return {
                matches: prefersLight,
                media: query,
                onchange: null,
                addListener: () => {},
                removeListener: () => {},
                addEventListener: () => {},
                removeEventListener: () => {},
                dispatchEvent: () => false
            };
        }
        return originalMatchMedia(query);
    };
    const meta = document.createElement('meta');
    meta.name = 'color-scheme';
    meta.content = 'light';
    (document.head || document.documentElement).appendChild(meta);
    document.documentElement.style.colorScheme = 'light';
})();
"""
    )
    return script


def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )


def find_mozilla_vpn():
    candidates = [
        shutil.which("mozillavpn"),
        shutil.which("mozillavpn.exe"),
        os.path.join(os.environ.get("ProgramFiles", ""), "Mozilla VPN", "mozillavpn.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Mozilla VPN", "mozillavpn.exe"),
    ]
    return next((path for path in candidates if path and os.path.isfile(path)), None)


class BrowserPage(QWebEnginePage):
    """Web page that keeps useful console diagnostics without Chromium noise."""

    def __init__(self, view, browser):
        super().__init__(view)
        self.browser = browser
        self.featurePermissionRequested.connect(self._request_feature_permission)

    def _request_feature_permission(self, origin, feature):
        if self.browser is not None:
            self.browser.handle_feature_permission(self, origin, feature)

    def createWindow(self, window_type):
        """Open web popups as regular Netroscape tabs with the same chrome."""
        if self.browser is None:
            return None
        popup_tab = self.browser.add_tab("about:blank")
        return popup_tab.page()

    _ignored_console_messages = (
        "Unrecognized feature: 'web-share'",
        "Failed to create WebGPU Context Provider",
        "was preloaded using link preload but not used within a few seconds",
        "Access to XMLHttpRequest at 'https://ad.doubleclick.net/",
        "Autofocus processing was blocked because a document already has a focused element",
    )

    def javaScriptConsoleMessage(self, level, message, line_number, source_id):
        if any(text in message for text in self._ignored_console_messages):
            LOG.debug("Ignored page console noise: %s", message)
            return

        level_name = {
            QWebEnginePage.JavaScriptConsoleMessageLevel.InfoMessageLevel: "INFO",
            QWebEnginePage.JavaScriptConsoleMessageLevel.WarningMessageLevel: "WARN",
            QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel: "ERROR",
        }.get(level, "LOG")
        log_method = {
            "INFO": LOG.info,
            "WARN": LOG.warning,
            "ERROR": LOG.error,
        }.get(level_name, LOG.debug)
        log_method(
            "JavaScript %s | line %s | %s | %s",
            level_name,
            line_number,
            source_id or "inline script",
            message,
        )

class ExtensionPopup(QDialog):
    """Small extension-owned window for manifest action popups."""

    def __init__(self, browser, extension: Extension, popup_path: str):
        super().__init__(browser)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setFixedSize(420, 640)

        root = QVBoxLayout(self)
        root.setContentsMargins(1, 1, 1, 1)
        root.setSpacing(0)
        title_bar = TitleBar(extension.name)
        title_bar.close_clicked.connect(self.close)
        root.addWidget(title_bar)

        self.view = QWebEngineView()
        self.view.setPage(BrowserPage(self.view, browser))
        extension_root = QUrl.fromLocalFile(str(extension.path) + os.sep).toString()
        self.view.page().scripts().insert(browser.extension_manager.build_popup_script(extension, extension_root))
        root.addWidget(self.view, stretch=1)
        self.view.setUrl(QUrl.fromLocalFile(str(extension.path / popup_path)))


class PermissionDialog(QDialog):
    """Themed permission prompt matching the browser's custom dialogs."""

    def __init__(self, parent, origin, feature_name):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setFixedSize(440, 190)
        self.setObjectName("PermissionDialog")

        root = QVBoxLayout(self)
        root.setContentsMargins(1, 1, 1, 1)
        root.setSpacing(0)

        title_bar = TitleBar("Permission request")
        title_bar.close_clicked.connect(self.reject)
        root.addWidget(title_bar)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(14, 12, 14, 12)
        content_layout.setSpacing(10)

        message = QLabel(f"Allow {origin.host()} to use {feature_name}?")
        message.setObjectName("DialogDetails")
        message.setWordWrap(True)
        content_layout.addWidget(message)
        content_layout.addStretch(1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        deny = QPushButton("Deny")
        deny.clicked.connect(self.reject)
        allow = QPushButton("Allow")
        allow.setDefault(True)
        allow.clicked.connect(self.accept)
        buttons.addWidget(deny)
        buttons.addWidget(allow)
        content_layout.addLayout(buttons)
        root.addWidget(content, stretch=1)


def format_size(size):
    return f"{size.width()}x{size.height()}"


class DownloadsDialog(QDialog):
    """Persistent IE-style download history for the current browser session."""

    def __init__(self, browser):
        super().__init__(browser)
        self.browser = browser
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setFixedSize(760, 460)
        self.setObjectName("DownloadsDialog")

        root = QVBoxLayout(self)
        root.setContentsMargins(1, 1, 1, 1)
        root.setSpacing(0)

        title_bar = TitleBar("Downloads - Netroscape")
        title_bar.close_clicked.connect(self.hide)
        root.addWidget(title_bar)

        toolbar = QWidget()
        toolbar.setObjectName("DialogToolbar")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(6, 4, 6, 4)
        toolbar_layout.setSpacing(4)
        open_folder = QPushButton("Open Downloads Folder")
        open_folder.clicked.connect(browser.open_downloads_folder)
        clear_finished = QPushButton("Clear Finished")
        clear_finished.clicked.connect(self.clear_finished)
        toolbar_layout.addWidget(open_folder)
        toolbar_layout.addWidget(clear_finished)
        toolbar_layout.addStretch(1)
        root.addWidget(toolbar)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("DownloadsList")
        self.list_widget.setSpacing(4)
        root.addWidget(self.list_widget, stretch=1)

    def add_record(self, filename, path, url):
        item = QListWidgetItem(self.list_widget)
        row = QWidget()
        row.setObjectName("DownloadRow")
        layout = QVBoxLayout(row)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(3)

        header = QHBoxLayout()
        name_label = QLabel(filename)
        name_label.setObjectName("DownloadName")
        header.addWidget(name_label, stretch=1)
        open_button = QPushButton("Open")
        open_button.setEnabled(False)
        header.addWidget(open_button)
        cancel_button = QPushButton("Cancel")
        header.addWidget(cancel_button)
        layout.addLayout(header)

        path_label = QLabel(path)
        path_label.setObjectName("DownloadPath")
        path_label.setToolTip(url or path)
        layout.addWidget(path_label)

        progress = QProgressBar()
        progress.setRange(0, 100)
        progress.setValue(0)
        layout.addWidget(progress)

        status_label = QLabel("Waiting...")
        status_label.setObjectName("DownloadStatus")
        layout.addWidget(status_label)
        self.list_widget.setItemWidget(item, row)

        record = {
            "item": item,
            "row": row,
            "filename": filename,
            "path": path,
            "progress": progress,
            "status": status_label,
            "open": open_button,
            "cancel": cancel_button,
            "finished": False,
        }
        item.setData(Qt.UserRole, record)
        item.setSizeHint(row.sizeHint())
        open_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(path)))
        return record

    def clear_finished(self):
        for index in range(self.list_widget.count() - 1, -1, -1):
            item = self.list_widget.item(index)
            record = item.data(Qt.UserRole)
            if record and record["finished"]:
                self.list_widget.takeItem(index)


class AboutDialog(QDialog):
    """About window using the same custom title bar and IE-style controls."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setFixedSize(460, 280)
        self.setObjectName("AboutDialog")

        root = QVBoxLayout(self)
        root.setContentsMargins(1, 1, 1, 1)
        root.setSpacing(0)
        title_bar = TitleBar("About Netroscape")
        title_bar.close_clicked.connect(self.reject)
        root.addWidget(title_bar)

        content = QWidget()
        content.setObjectName("DialogContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(22, 18, 22, 14)
        content_layout.setSpacing(8)
        heading = QLabel(f"Netroscape {VERSION} \"{VERSION_NAME}\"")
        heading.setObjectName("DialogHeading")
        content_layout.addWidget(heading)
        subtitle = QLabel("Chromium browsing with an Internet Explorer 8-inspired shell")
        subtitle.setObjectName("DialogSubtitle")
        subtitle.setWordWrap(True)
        content_layout.addWidget(subtitle)
        details = QLabel(
            f"Built with PySide6 and QtWebEngine.\n\n"
            f"Copyright 2026c | Written by {AUTHOR}\n"
            "Includes themed tabs, downloads, extensions, and privacy tools."
        )
        details.setObjectName("DialogDetails")
        details.setWordWrap(True)
        content_layout.addWidget(details)
        content_layout.addStretch(1)
        button_row = QHBoxLayout()
        button_row.addStretch(1)
        close_button = QPushButton("Close")
        close_button.setDefault(True)
        close_button.clicked.connect(self.accept)
        button_row.addWidget(close_button)
        content_layout.addLayout(button_row)
        root.addWidget(content, stretch=1)


class BrowserTab(QWebEngineView):
    """A single tab's web view, with theme injection wired to page loads."""

    def __init__(self, url: str = HOME_URL, parent=None, browser=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        self.setMinimumSize(0, 0)
        self.setPage(BrowserPage(self, browser))
        self.loadFinished.connect(self._on_load_finished)
        self.loadStarted.connect(lambda: LOG.info("Loading tab URL: %s", self.url().toString()))
        self.setUrl(QUrl(url))

    def _on_load_finished(self, ok: bool):
        LOG.info("Load finished | ok=%s | url=%s", ok, self.url().toString())
        if not ok:
            return
        script = get_injection_script_for_url(self.url().toString())
        self.page().runJavaScript(script)


class NetroscapeBrowser(QMainWindow):
    def __init__(self):
        super().__init__()
        # Frameless so our custom TitleBar replaces the OS chrome.
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setFixedSize(int(WINDOW_WIDTH), int(WINDOW_HEIGHT))
        self._is_maximized = False
        self._normal_geometry = self.geometry()

        central = QWidget()
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(1, 1, 1, 1)
        root_layout.setSpacing(0)

        # --- Title bar ---
        self.title_bar = TitleBar(WINDOW_TITLE)
        self.title_bar.minimize_clicked.connect(self.showMinimized)
        self.title_bar.maximize_clicked.connect(self.toggle_maximize)
        self.title_bar.close_clicked.connect(self.close)
        root_layout.addWidget(self.title_bar)

        # --- Menu bar (IE8-style: File/Edit/View/Favorites/Tools/Help) ---
        self.menu_bar = QMenuBar()
        root_layout.addWidget(self.menu_bar)

        # --- Toolbar ---
        toolbar = QToolBar()
        toolbar.setMovable(False)

        self.back_btn = self.make_tool_button("back", QStyle.SP_ArrowBack, "Back", self.go_back)
        self.forward_btn = self.make_tool_button("forward", QStyle.SP_ArrowForward, "Forward", self.go_forward)
        stop_btn = self.make_tool_button("stop", QStyle.SP_BrowserStop, "Stop", lambda: self.current_view().stop())
        refresh_btn = self.make_tool_button("refresh", QStyle.SP_BrowserReload, "Refresh", lambda: self.current_view().reload())
        home_btn = self.make_tool_button(
            "home",
            QStyle.SP_DirHomeIcon,
            "Home",
            lambda: self.current_view().setUrl(QUrl(HOME_URL)),
        )

        self.address_bar = QLineEdit()
        self.address_bar.setObjectName("AddressBar")
        self.address_bar.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.address_bar.setFixedWidth(int(ADDRESS_BAR_WIDTH))
        self.address_bar.returnPressed.connect(self.navigate_to_address_bar)

        go_btn = self.make_tool_button(None, QStyle.SP_ArrowRight, "Go to address", self.navigate_to_address_bar)
        go_btn.setObjectName("GoButton")
        go_btn.setText("Go")
        go_btn.setIcon(QIcon())
        go_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        go_btn.setFixedWidth(int(GO_BUTTON_WIDTH))

        for w in (self.back_btn, self.forward_btn, stop_btn, refresh_btn, home_btn):
            toolbar.addWidget(w)
        toolbar.addWidget(self.address_bar)
        toolbar.addWidget(go_btn)
        root_layout.addWidget(toolbar)

        # --- Tabs ---
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.on_tab_changed)

        new_tab_btn = self.make_tool_button("new_tab", QStyle.SP_FileDialogNewFolder, "New tab", lambda: self.add_tab(HOME_URL))
        new_tab_btn.setObjectName("NewTabButton")
        self.tabs.setCornerWidget(new_tab_btn, Qt.TopRightCorner)

        root_layout.addWidget(self.tabs, stretch=1)

        # --- Status bar ---
        self.status_bar = QStatusBar()
        self.status_label = QLabel("Done")
        self.status_label.setObjectName("StatusSection")
        self.zoom_label = QLabel("100%")
        self.zoom_label.setObjectName("StatusSection")
        self.status_bar.addWidget(self.status_label, stretch=1)
        self.status_bar.addPermanentWidget(self.zoom_label)
        root_layout.addWidget(self.status_bar)

        self.setCentralWidget(central)

        self.favorites = []
        self.ad_blocker = BuiltInAdBlocker()
        profile = QWebEngineProfile.defaultProfile()
        profile.setUrlRequestInterceptor(self.ad_blocker)
        profile.scripts().insert(build_spacehey_geolocation_script())
        profile.scripts().insert(build_light_mode_script())
        profile.downloadRequested.connect(self.handle_download_requested)
        self.download_records = []
        self.downloads_dialog = DownloadsDialog(self)
        self.extension_manager = ExtensionManager()
        self.extension_manager.load()
        self.extension_popups = {}
        self.apply_extension_scripts()
        self.setup_menus()
        self.add_tab(HOME_URL)
        self.update_navigation_buttons()
        LOG.info("Browser created | initial size=%s | geometry=%s", format_size(self.size()), self.geometry())

    def make_tool_button(self, icon_name, standard_icon, tooltip, callback):
        button = QToolButton()
        button.setIcon(self.ui_icon(icon_name, standard_icon))
        button.setToolTip(tooltip)
        button.setAutoRaise(True)
        button.setFixedSize(int(TOOLBAR_BUTTON_WIDTH), int(TOOLBAR_BUTTON_HEIGHT))
        button.clicked.connect(callback)
        return button

    def setup_menus(self):
        file_menu = self.menu_bar.addMenu("File")
        new_tab_action = self.add_menu_action(
            file_menu,
            "New Tab",
            QStyle.SP_FileDialogNewFolder,
            lambda checked=False: self.add_tab(HOME_URL),
            "new_tab",
        )
        new_tab_action.setShortcut("Ctrl+T")
        close_tab_action = self.add_menu_action(file_menu, "Close Tab", QStyle.SP_DialogCloseButton, self.close_current_tab, "close_tab")
        close_tab_action.setShortcut("Ctrl+W")
        file_menu.addSeparator()
        self.add_menu_action(file_menu, "Exit", QStyle.SP_TitleBarCloseButton, self.close, "exit")

        edit_menu = self.menu_bar.addMenu("Edit")
        for label, shortcut, web_action in (
            ("Undo", "Ctrl+Z", QWebEnginePage.WebAction.Undo),
            ("Redo", "Ctrl+Y", QWebEnginePage.WebAction.Redo),
            ("Cut", "Ctrl+X", QWebEnginePage.WebAction.Cut),
            ("Copy", "Ctrl+C", QWebEnginePage.WebAction.Copy),
            ("Paste", "Ctrl+V", QWebEnginePage.WebAction.Paste),
            ("Select All", "Ctrl+A", QWebEnginePage.WebAction.SelectAll),
        ):
            action = edit_menu.addAction(label)
            action.setShortcut(shortcut)
            action.triggered.connect(lambda checked=False, web_action=web_action: self.trigger_page_action(web_action))

        view_menu = self.menu_bar.addMenu("View")
        self.add_page_menu_action(view_menu, "Back", QStyle.SP_ArrowBack, QWebEnginePage.WebAction.Back, "back")
        self.add_page_menu_action(view_menu, "Forward", QStyle.SP_ArrowForward, QWebEnginePage.WebAction.Forward, "forward")
        self.add_page_menu_action(view_menu, "Refresh", QStyle.SP_BrowserReload, QWebEnginePage.WebAction.Reload, "refresh")
        self.add_page_menu_action(view_menu, "Stop", QStyle.SP_BrowserStop, QWebEnginePage.WebAction.Stop, "stop")
        view_menu.addSeparator()
        for label, shortcut, callback in (
            ("Zoom In", "Ctrl+=", lambda: self.change_zoom(0.1)),
            ("Zoom Out", "Ctrl+-", lambda: self.change_zoom(-0.1)),
            ("Reset Zoom", "Ctrl+0", lambda: self.set_zoom(1.0)),
        ):
            action = view_menu.addAction(label)
            action.setShortcut(shortcut)
            action.triggered.connect(callback)
        view_menu.addSeparator()
        fullscreen_action = view_menu.addAction("Fullscreen")
        fullscreen_action.setShortcut("F11")
        fullscreen_action.triggered.connect(self.toggle_fullscreen)

        self.favorites_menu = self.menu_bar.addMenu("Favorites")
        self.favorites_menu.aboutToShow.connect(self.populate_favorites_menu)

        self.extensions_menu = self.menu_bar.addMenu("Extensions")
        self.extensions_menu.aboutToShow.connect(self.populate_extensions_menu)

        tools_menu = self.menu_bar.addMenu("Tools")
        clear_cache = self.add_menu_action(
            tools_menu,
            "Clear Browser Cache",
            QStyle.SP_TrashIcon,
            self.clear_browser_cache,
            "clear_cache",
        )
        reset_zoom = self.add_menu_action(
            tools_menu,
            "Reset Zoom",
            QStyle.SP_ComputerIcon,
            lambda: self.set_zoom(1.0),
            "reset_zoom",
        )
        tools_menu.addAction("Show Downloads", self.show_downloads)
        tools_menu.addAction("Open Downloads Folder", self.open_downloads_folder)
        tools_menu.addSeparator()
        vpn_menu = tools_menu.addMenu("Mozilla VPN")
        vpn_menu.addAction("Open Mozilla VPN", self.open_mozilla_vpn)
        vpn_menu.addAction("Connect to United Kingdom", self.connect_mozilla_vpn)
        vpn_menu.addAction("Disconnect", lambda: self.run_mozilla_vpn_command("deactivate"))
        vpn_menu.addAction("Show Status", lambda: self.run_mozilla_vpn_command("status"))

        help_menu = self.menu_bar.addMenu("Help")
        self.add_menu_action(
            help_menu,
            "About Netroscape",
            QStyle.SP_MessageBoxInformation,
            self.show_about,
            "about",
        )
        self.add_menu_action(
            help_menu,
            "Keyboard Shortcuts",
            QStyle.SP_FileDialogInfoView,
            self.show_shortcuts,
            "shortcuts",
        )

    def ui_icon(self, icon_name, standard_icon):
        configured = icon_path(icon_name) if icon_name else ""
        return QIcon(configured) if configured else self.style().standardIcon(standard_icon)

    def add_menu_action(self, menu, text, icon, callback, icon_name=None):
        action = menu.addAction(self.ui_icon(icon_name, icon) if icon_name else self.style().standardIcon(icon), text)
        action.triggered.connect(callback)
        return action

    def add_page_menu_action(self, menu, text, icon, web_action, icon_name=None):
        action = menu.addAction(self.ui_icon(icon_name, icon) if icon_name else self.style().standardIcon(icon), text)
        action.triggered.connect(lambda checked=False: self.trigger_page_action(web_action))
        return action

    def trigger_page_action(self, action):
        view = self.current_view()
        if view is not None:
            view.page().triggerAction(action)

    def go_back(self):
        view = self.current_view()
        if view is None:
            return
        if view.history().canGoBack():
            view.back()
        self.update_navigation_buttons()

    def go_forward(self):
        view = self.current_view()
        if view is None:
            return
        if view.history().canGoForward():
            view.forward()
        self.update_navigation_buttons()

    def update_navigation_buttons(self):
        view = self.current_view()
        can_go_back = view is not None and view.history().canGoBack()
        can_go_forward = view is not None and view.history().canGoForward()
        self.back_btn.setEnabled(can_go_back)
        self.forward_btn.setEnabled(can_go_forward)

    def close_current_tab(self):
        self.close_tab(self.tabs.currentIndex())

    def add_favorite(self):
        view = self.current_view()
        if view is None:
            return
        favorite = (view.title() or view.url().toString(), view.url().toString())
        if favorite not in self.favorites:
            self.favorites.append(favorite)
            self.status_label.setText("Favorite added")
            LOG.info("Favorite added | title=%s | url=%s", favorite[0], favorite[1])

    def populate_favorites_menu(self):
        self.favorites_menu.clear()
        add_action = self.favorites_menu.addAction("Add Current Page")
        add_action.triggered.connect(self.add_favorite)
        self.favorites_menu.addSeparator()
        if not self.favorites:
            empty_action = self.favorites_menu.addAction("No favorites yet")
            empty_action.setEnabled(False)
            return
        for title, url in self.favorites:
            action = self.favorites_menu.addAction(title)
            action.setToolTip(url)
            action.triggered.connect(lambda checked=False, url=url: self.current_view().setUrl(QUrl(url)))

    def apply_extension_scripts(self):
        collection = QWebEngineProfile.defaultProfile().scripts()
        for script in collection.toList():
            if script.name().startswith("netroscape-ext::"):
                collection.remove(script)
        for script in self.extension_manager.build_web_engine_scripts():
            collection.insert(script)

    def populate_extensions_menu(self):
        self.extensions_menu.clear()
        for extension in self.extension_manager.extensions:
            action = self.extensions_menu.addAction(f"{extension.name} ({extension.version})")
            action.setCheckable(True)
            action.setChecked(extension.enabled)
            action.triggered.connect(
                lambda checked, extension=extension: self.toggle_extension(extension, checked)
            )
            popup_path = self.extension_popup_path(extension)
            if popup_path:
                popup_action = self.extensions_menu.addAction(f"Open {extension.name} Popup")
                popup_action.setEnabled(extension.enabled)
                popup_action.triggered.connect(
                    lambda checked=False, extension=extension, popup_path=popup_path:
                    self.open_extension_popup(extension, popup_path)
                )
        if not self.extension_manager.extensions:
            empty = self.extensions_menu.addAction("No extensions installed")
            empty.setEnabled(False)
        self.extensions_menu.addSeparator()
        self.extensions_menu.addAction("Install from Chrome Web Store...", self.install_web_store_extension)
        self.extensions_menu.addAction("Reload Extensions", self.reload_extensions)
        self.extensions_menu.addAction("Open Extensions Folder", self.open_extensions_folder)

    def toggle_extension(self, extension: Extension, enabled: bool):
        self.extension_manager.set_enabled(extension, enabled)
        self.apply_extension_scripts()
        self.current_view().reload()

    @staticmethod
    def extension_popup_path(extension: Extension):
        action = extension.manifest.get("action", {})
        browser_action = extension.manifest.get("browser_action", {})
        popup_path = action.get("default_popup") or browser_action.get("default_popup")
        if not popup_path:
            return None
        path = extension.path / popup_path
        return popup_path if path.is_file() else None

    def open_extension_popup(self, extension: Extension, popup_path: str):
        popup = self.extension_popups.get(extension.path)
        if popup is None:
            popup = ExtensionPopup(self, extension, popup_path)
            self.extension_popups[extension.path] = popup
            popup.destroyed.connect(lambda: self.extension_popups.pop(extension.path, None))
        popup.show()
        popup.raise_()
        popup.activateWindow()

    def handle_feature_permission(self, page, origin, feature):
        feature_names = {
            QWebEnginePage.Feature.Geolocation: "location",
            QWebEnginePage.Feature.MediaAudioCapture: "microphone",
            QWebEnginePage.Feature.MediaVideoCapture: "camera",
            QWebEnginePage.Feature.MediaAudioVideoCapture: "camera and microphone",
            QWebEnginePage.Feature.Notifications: "notifications",
        }
        name = feature_names.get(feature)
        if name is None:
            policy = QWebEnginePage.PermissionPolicy.PermissionDeniedByUser
        else:
            answer = PermissionDialog(self, origin, name).exec()
            policy = (
                QWebEnginePage.PermissionPolicy.PermissionGrantedByUser
                if answer == QDialog.DialogCode.Accepted
                else QWebEnginePage.PermissionPolicy.PermissionDeniedByUser
            )
        page.setFeaturePermission(origin, feature, policy)

    def install_web_store_extension(self):
        value, accepted = QInputDialog.getText(
            self, "Install Chrome Extension", "Chrome Web Store URL or extension ID:"
        )
        if not accepted or not value.strip():
            return
        try:
            extension = self.extension_manager.install_chrome_web_store(value)
            self.extension_manager.reload()
            self.apply_extension_scripts()
            self.current_view().reload()
        except Exception as exc:
            QMessageBox.warning(self, "Install Chrome Extension", str(exc))
            return
        self.status_label.setText(f"Installed extension: {extension.name}")
        if extension.unsupported:
            QMessageBox.information(
                self,
                "Extension Partially Imported",
                "Unsupported parts: " + ", ".join(extension.unsupported),
            )

    def reload_extensions(self):
        self.extension_manager.reload()
        self.apply_extension_scripts()
        self.current_view().reload()

    def open_extensions_folder(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(EXTENSIONS_DIR)))

    def open_downloads_folder(self):
        downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")
        os.makedirs(downloads_path, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(downloads_path))

    def show_downloads(self):
        self.downloads_dialog.show()
        self.downloads_dialog.raise_()
        self.downloads_dialog.activateWindow()

    def handle_download_requested(self, download):
        default_name = download.downloadFileName() or "download"
        downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")
        os.makedirs(downloads_path, exist_ok=True)
        suggested_path = os.path.join(downloads_path, default_name)
        path, accepted = QFileDialog.getSaveFileName(
            self,
            "Save Download",
            suggested_path,
            "All files (*)",
        )
        if not accepted or not path:
            download.cancel()
            return

        directory, filename = os.path.split(path)
        download.setDownloadDirectory(directory)
        download.setDownloadFileName(filename)
        self.show_downloads()
        record = self.downloads_dialog.add_record(filename, path, download.url().toString())
        self.download_records.append(record)
        record["cancel"].clicked.connect(download.cancel)

        def update_progress():
            total = download.totalBytes()
            received = download.receivedBytes()
            if total > 0:
                record["progress"].setValue(int(received * 100 / total))
                record["status"].setText(f"Downloading {received} / {total} bytes")
            else:
                record["status"].setText(f"Downloading {received} bytes")

        def finish(state):
            if state == QWebEngineDownloadRequest.DownloadState.DownloadCompleted:
                record["progress"].setValue(100)
                record["status"].setText("Completed")
                record["open"].setEnabled(True)
                record["cancel"].setEnabled(False)
                self.status_label.setText(f"Download completed: {filename}")
            elif state == QWebEngineDownloadRequest.DownloadState.DownloadCancelled:
                record["status"].setText("Cancelled")
                record["cancel"].setEnabled(False)
                self.status_label.setText("Download cancelled")
            elif state == QWebEngineDownloadRequest.DownloadState.DownloadInterrupted:
                record["status"].setText("Interrupted")
                record["cancel"].setEnabled(False)
                self.status_label.setText("Download interrupted")
            if state != QWebEngineDownloadRequest.DownloadState.DownloadInProgress:
                record["finished"] = True

        download.receivedBytesChanged.connect(update_progress)
        download.totalBytesChanged.connect(update_progress)
        download.stateChanged.connect(finish)
        download.accept()

    def open_mozilla_vpn(self):
        executable = find_mozilla_vpn()
        if executable is None:
            QMessageBox.warning(self, "Mozilla VPN", "Mozilla VPN is not installed or was not found.")
            return
        if not QProcess.startDetached(executable, []):
            QMessageBox.warning(self, "Mozilla VPN", "Could not start Mozilla VPN.")

    def run_mozilla_vpn_command(self, command: str, *arguments: str):
        executable = find_mozilla_vpn()
        if executable is None:
            QMessageBox.warning(self, "Mozilla VPN", "Mozilla VPN is not installed or was not found.")
            return
        if not QProcess.startDetached(executable, [command, *arguments]):
            QMessageBox.warning(self, "Mozilla VPN", f"Could not run: mozillavpn {command}")
        else:
            self.status_label.setText(f"Mozilla VPN command sent: {command}")

    def connect_mozilla_vpn(self):
        self.run_mozilla_vpn_command("select", "United Kingdom")
        self.run_mozilla_vpn_command("activate")

    def change_zoom(self, amount):
        view = self.current_view()
        if view is not None:
            self.set_zoom(view.zoomFactor() + amount)

    def set_zoom(self, factor):
        view = self.current_view()
        if view is not None:
            factor = max(0.25, min(5.0, factor))
            view.setZoomFactor(factor)
            self.zoom_label.setText(f"{round(factor * 100)}%")

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
            self.setFixedSize(self._normal_geometry.size())
            self.setGeometry(self._normal_geometry)
        else:
            self._normal_geometry = self.geometry()
            self.showFullScreen()
        LOG.info("Fullscreen toggled | active=%s | size=%s", self.isFullScreen(), format_size(self.size()))

    def clear_browser_cache(self):
        profile = self.current_view().page().profile()
        profile.clearHttpCache()
        profile.clearAllVisitedLinks()
        self.status_label.setText("Browser cache cleared")
        LOG.info("Browser cache cleared")

    def show_about(self):
        dialog = AboutDialog(self)
        dialog.exec()

    def show_shortcuts(self):
        QMessageBox.information(
            self,
            "Keyboard Shortcuts",
            "Ctrl+L  Focus address bar\n"
            "Ctrl+T  New tab\n"
            "Ctrl+W  Close tab\n"
            "Ctrl+R  Refresh\n"
            "Ctrl+=  Zoom in\n"
            "Ctrl+-  Zoom out\n"
            "Ctrl+0  Reset zoom\n"
            "F11  Fullscreen",
        )

    def log_window_state(self, event_name: str):
        screen = self.screen() or QApplication.primaryScreen()
        screen_name = screen.name() if screen else "unknown"
        available = format_size(screen.availableGeometry().size()) if screen else "unknown"
        LOG.info(
            "%s | window=%s | geometry=%s | screen=%s | available=%s | tabs=%s | active=%s",
            event_name,
            format_size(self.size()),
            self.geometry(),
            screen_name,
            available,
            self.tabs.count(),
            self.tabs.currentIndex(),
        )

    def showEvent(self, event):
        super().showEvent(event)
        self.log_window_state("Window shown")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.log_window_state("Window resized")

    def moveEvent(self, event):
        super().moveEvent(event)
        self.log_window_state("Window moved")

    # --- tab management ---
    def add_tab(self, url: str):
        view = BrowserTab(url, browser=self)
        view.urlChanged.connect(lambda qurl, v=view: self.on_url_changed(v, qurl))
        view.titleChanged.connect(lambda text, v=view: self.on_title_changed(v, text))
        view.loadStarted.connect(lambda v=view: self.on_load_started(v))
        view.loadFinished.connect(lambda ok, v=view: self.on_load_finished_status(v, ok))

        index = self.tabs.addTab(view, "New Tab")
        close_button = QToolButton()
        close_button.setObjectName("TabCloseButton")
        close_button.setText("x")
        close_button.setToolTip("Close tab")
        close_button.setFixedSize(int(TAB_CLOSE_SIZE), int(TAB_CLOSE_SIZE))
        close_button.clicked.connect(lambda checked=False, tab=view: self.close_tab(self.tabs.indexOf(tab)))
        self.tabs.tabBar().setTabButton(index, QTabBar.RightSide, close_button)
        self.tabs.setCurrentIndex(index)
        LOG.info("Tab added | index=%s | url=%s | tab_count=%s", index, url, self.tabs.count())
        return view

    def close_tab(self, index: int):
        if self.tabs.count() <= 1:
            # Keep at least one tab open - closing the last one closes the app.
            self.close()
            return
        widget = self.tabs.widget(index)
        self.tabs.removeTab(index)
        widget.deleteLater()
        LOG.info("Tab closed | index=%s | tab_count=%s", index, self.tabs.count())

    def current_view(self) -> BrowserTab:
        return self.tabs.currentWidget()

    def on_tab_changed(self, index: int):
        view = self.tabs.widget(index)
        self.update_navigation_buttons()
        if view is not None:
            self.address_bar.setText(self.display_url(view.url()))
            LOG.info("Active tab changed | index=%s | url=%s", index, view.url().toString())

    # --- navigation ---
    def navigate_to_address_bar(self):
        text = self.address_bar.text().strip()
        if text == DISPLAY_URL and self.current_view().url().host() == LOCAL_SERVER_HOST:
            return
        if not text.startswith("http://") and not text.startswith("https://"):
            text = "https://" + text
        LOG.info("Address navigation requested | url=%s", text)
        self.current_view().setUrl(QUrl(text))

    @staticmethod
    def display_url(qurl: QUrl) -> str:
        if qurl.host() == LOCAL_SERVER_HOST and qurl.path().startswith("/google"):
            return DISPLAY_URL
        return qurl.toString()

    def on_url_changed(self, view: BrowserTab, qurl: QUrl):
        self.update_navigation_buttons()
        if view is self.current_view():
            self.address_bar.setText(self.display_url(qurl))

    def on_title_changed(self, view: BrowserTab, text: str):
        index = self.tabs.indexOf(view)
        if index != -1:
            # Keep tab labels short so they don't blow out the tab bar.
            short = text if len(text) <= 20 else text[:17] + "..."
            self.tabs.setTabText(index, short or "New Tab")
        if view is self.current_view():
            self.title_bar.set_title(f"{text} - {WINDOW_TITLE}" if text else WINDOW_TITLE)

    def on_load_started(self, view: BrowserTab):
        LOG.info("Load started | url=%s | active=%s", view.url().toString(), view is self.current_view())
        if view is self.current_view():
            self.status_label.setText("Opening page...")

    def on_load_finished_status(self, view: BrowserTab, ok: bool):
        self.update_navigation_buttons()
        LOG.info("Navigation status | ok=%s | url=%s", ok, view.url().toString())
        if view is self.current_view():
            self.status_label.setText("Done" if ok else "Navigation error")

    # --- window controls ---
    def toggle_maximize(self):
        # We deliberately avoid self.showMaximized()/showNormal() here.
        # On Windows, a frameless window (Qt.FramelessWindowHint) combined
        # with the native maximize call is a known source of bad geometry
        # calculations - especially on multi-monitor or high-res setups -
        # which can hand back a window many times wider than any real
        # screen. Computing the target geometry ourselves from the actual
        # current screen sidesteps that entirely.
        if self._is_maximized:
            self.setFixedSize(self._normal_geometry.size())
            self.setGeometry(self._normal_geometry)
        else:
            self._normal_geometry = self.geometry()
            screen = self.screen() or QApplication.primaryScreen()
            if screen is None:
                return
            available = screen.availableGeometry()
            self.setFixedSize(available.size())
            self.setGeometry(available)
        self._is_maximized = not self._is_maximized
        self.log_window_state("Window maximized" if self._is_maximized else "Window restored")


def main():
    configure_logging()
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-features=WebGPU")
    LOG.info(
        "Starting %s | author=%s | Python=%s | QtWebEngine diagnostics enabled",
        WINDOW_TITLE,
        AUTHOR,
        platform.python_version(),
    )
    app = QApplication(sys.argv)
    app.setApplicationName("Netroscape")
    app.setApplicationVersion(VERSION)
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#F2F2F2"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#16283A"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#16283A"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#16283A"))
    app.setPalette(palette)
    LOG.info("Qt application | Qt=%s | arguments=%s", qVersion(), sys.argv)
    app.setStyleSheet(STYLESHEET)
    local_server = start_server()
    global HOME_URL
    HOME_URL = f"http://{LOCAL_SERVER_HOST}:{local_server.server_port}/google/"
    app.aboutToQuit.connect(local_server.shutdown)
    LOG.info("Local pages hosted at %s", HOME_URL)
    window = NetroscapeBrowser()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()