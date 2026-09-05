"""
xp_theme.py

A QSS (Qt Style Sheet) approximating the Windows XP "Luna" look as
used by Internet Explorer 8: navy-to-blue gradient title bar, lavender
toolbar/menu chrome, curved IE8-style tabs, and a sunken status bar.

This is a visual approximation, not a pixel-perfect recreation -
QSS can't do everything real Win32 theming (uxtheme.dll) could, but
it gets close enough to feel right.

All colors and a few layout values are read from theme_config.ini in
this same directory, so you can retheme the app by editing that file
instead of this one. If the config file is missing, or a key in it is
missing/misspelled, this module quietly falls back to the built-in
DEFAULTS below rather than crashing - so deleting the ini file just
restores the original look.

Note on text color: every rule below sets an explicit `color`, even
where it looks redundant. Without that, some Windows setups (dark
mode in particular) fall back to a white default text color, which
becomes invisible against these light chrome backgrounds. Don't
remove a `color` line to "clean up" the CSS - it's load-bearing.
"""

import configparser
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "theme_config.ini")

# Built-in fallback values. Used whenever theme_config.ini is missing,
# unreadable, or missing a specific key - so a typo'd or half-deleted
# config degrades gracefully instead of crashing the app.
DEFAULTS = {
    "colors": {
        "title_bar_gradient_start": "#0B2D5C",
        "title_bar_gradient_mid": "#1E5FA3",
        "title_bar_gradient_end": "#0B2D5C",
        "title_button_text": "#FFFFFF",
        "title_button_hover_bg": "rgba(255, 255, 255, 110)",
        "title_button_hover_text": "#0B2D5C",
        "title_button_pressed_bg": "rgba(255, 255, 255, 160)",
        "close_button_hover": "#E81123",
        "close_button_pressed": "#A80F1C",
        "chrome_background": "#FFFFFF",
        "chrome_border": "#7A9AB8",
        "text": "#16283A",
        "button_face": "#FFFFFF",
        "button_hover": "#C7DDF2",
        "button_hover_border": "#4C7FA8",
        "button_pressed": "#A8C7E2",
        "button_pressed_border": "#315F89",
        "tab_active_background": "#FFFFFF",
        "tab_inactive_background": "#F2F2F2",
        "tab_border": "#6689A8",
        "address_selection_bg": "#9B6FD1",
        "address_selection_text": "#FFFFFF",
        "go_button_face": "#174A8C",
        "go_button_hover": "#245F9F",
        "go_button_pressed": "#0B2D5C",
        "go_button_text": "#FFFFFF",
    },
    "layout": {
        "title_bar_corner_radius": "0",
        "title_bar_height": "28",
        "window_width": "1200",
        "window_height": "800",
        "toolbar_button_width": "34",
        "toolbar_button_height": "28",
        "address_bar_width": "650",
        "go_button_width": "52",
        "tab_close_size": "18",
        "title_button_width": "28",
        "title_button_height": "20",
        "font_family": "Times New Roman",
        "menu_font_size": "12",
        "toolbar_font_size": "11",
        "tab_font_size": "11",
        "status_font_size": "11",
    },
    "icons": {
        "minimize": "",
        "maximize": "",
        "close": "",
        "back": "",
        "forward": "",
        "stop": "",
        "refresh": "",
        "home": "",
        "new_tab": "",
        "close_tab": "",
        "clear_cache": "",
        "reset_zoom": "",
        "about": "",
        "shortcuts": "",
        "exit": "",
    },
}


def _load_config() -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    if os.path.exists(CONFIG_PATH):
        try:
            config.read(CONFIG_PATH, encoding="utf-8")
        except configparser.Error:
            # Malformed ini (e.g. a stray unmatched bracket) - fall back
            # to an empty config so every lookup below hits DEFAULTS.
            config = configparser.ConfigParser()
    return config


def _get(config: configparser.ConfigParser, section: str, key: str) -> str:
    return config.get(section, key, fallback=DEFAULTS[section][key])


_config = _load_config()


def _c(key: str) -> str:
    """Fetch a [colors] value, falling back to the built-in default."""
    return _get(_config, "colors", key)


def _l(key: str) -> str:
    """Fetch a [layout] value, falling back to the built-in default."""
    return _get(_config, "layout", key)


def icon_path(key: str) -> str:
    """Return a configured icon path, resolving relative paths beside the ini."""
    configured = _get(_config, "icons", key).strip()
    if not configured:
        return ""
    if not os.path.isabs(configured):
        configured = os.path.join(os.path.dirname(CONFIG_PATH), configured)
    return configured if os.path.isfile(configured) else ""


# ---- colors ----
TITLE_GRAD_START = _c("title_bar_gradient_start")
TITLE_GRAD_MID = _c("title_bar_gradient_mid")
TITLE_GRAD_END = _c("title_bar_gradient_end")
TITLE_BUTTON_TEXT = _c("title_button_text")
TITLE_BUTTON_HOVER_BG = _c("title_button_hover_bg")
TITLE_BUTTON_HOVER_TEXT = _c("title_button_hover_text")
TITLE_BUTTON_PRESSED_BG = _c("title_button_pressed_bg")
CLOSE_BUTTON_HOVER = _c("close_button_hover")
CLOSE_BUTTON_PRESSED = _c("close_button_pressed")

LUNA_CHROME_BG = _c("chrome_background")
LUNA_CHROME_BORDER = _c("chrome_border")
LUNA_TEXT = _c("text")
LUNA_BUTTON_FACE = _c("button_face")
LUNA_BUTTON_HOVER = _c("button_hover")
LUNA_BUTTON_HOVER_BORDER = _c("button_hover_border")
LUNA_BUTTON_PRESSED = _c("button_pressed")
LUNA_BUTTON_PRESSED_BORDER = _c("button_pressed_border")

TAB_ACTIVE_BG = _c("tab_active_background")
TAB_INACTIVE_BG = _c("tab_inactive_background")
TAB_BORDER = _c("tab_border")

ADDRESS_SELECTION_BG = _c("address_selection_bg")
ADDRESS_SELECTION_TEXT = _c("address_selection_text")
GO_BUTTON_FACE = _c("go_button_face")
GO_BUTTON_HOVER = _c("go_button_hover")
GO_BUTTON_PRESSED = _c("go_button_pressed")
GO_BUTTON_TEXT = _c("go_button_text")

# ---- layout ----
# Radius defaults to 0: any value above 0 leaves a light-colored notch in
# the top corners, since the frameless window underneath the title bar
# is still perfectly square and isn't masked to match a rounded shape.
TITLE_BAR_RADIUS = _l("title_bar_corner_radius")
TITLE_BAR_HEIGHT = _l("title_bar_height")
WINDOW_WIDTH = _l("window_width")
WINDOW_HEIGHT = _l("window_height")
TOOLBAR_BUTTON_WIDTH = _l("toolbar_button_width")
TOOLBAR_BUTTON_HEIGHT = _l("toolbar_button_height")
ADDRESS_BAR_WIDTH = _l("address_bar_width")
GO_BUTTON_WIDTH = _l("go_button_width")
TAB_CLOSE_SIZE = _l("tab_close_size")
TITLE_BUTTON_WIDTH = _l("title_button_width")
TITLE_BUTTON_HEIGHT = _l("title_button_height")
FONT_FAMILY = _l("font_family")
MENU_FONT_SIZE = _l("menu_font_size")
TOOLBAR_FONT_SIZE = _l("toolbar_font_size")
TAB_FONT_SIZE = _l("tab_font_size")
STATUS_FONT_SIZE = _l("status_font_size")


STYLESHEET = f"""
QMainWindow {{
    background-color: {LUNA_CHROME_BG};
}}

/* ---------- Custom Title Bar ---------- */
#TitleBar {{
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 {TITLE_GRAD_START},
        stop:0.5 {TITLE_GRAD_MID},
        stop:1 {TITLE_GRAD_END}
    );
    border-top-left-radius: {TITLE_BAR_RADIUS}px;
    border-top-right-radius: {TITLE_BAR_RADIUS}px;
}}

#TitleBar QLabel {{
    color: {TITLE_BUTTON_TEXT};
    font-weight: bold;
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {MENU_FONT_SIZE}px;
    padding-left: 6px;
    background: transparent;
}}

#TitleBarButton {{
    background-color: transparent;
    border: none;
    color: {TITLE_BUTTON_TEXT};
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {MENU_FONT_SIZE}px;
    font-weight: bold;
    min-width: 28px;
    min-height: 20px;
}}

#TitleBarButton:hover {{
    background-color: {TITLE_BUTTON_HOVER_BG};
    color: {TITLE_BUTTON_HOVER_TEXT};
}}

#TitleBarButton:pressed {{
    background-color: {TITLE_BUTTON_PRESSED_BG};
    color: {TITLE_BUTTON_HOVER_TEXT};
}}

#CloseButton:hover {{
    background-color: {CLOSE_BUTTON_HOVER};
    color: {TITLE_BUTTON_TEXT};
}}

#CloseButton:pressed {{
    background-color: {CLOSE_BUTTON_PRESSED};
    color: {TITLE_BUTTON_TEXT};
}}

/* ---------- Menu Bar ---------- */
QMenuBar {{
    background-color: {LUNA_CHROME_BG};
    border-bottom: 1px solid {LUNA_CHROME_BORDER};
    color: {LUNA_TEXT};
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {MENU_FONT_SIZE}px;
    padding: 1px;
}}

QMenuBar::item {{
    background: transparent;
    color: {LUNA_TEXT};
    padding: 3px 8px;
}}

QMenuBar::item:selected {{
    background-color: {LUNA_BUTTON_HOVER};
    color: {LUNA_TEXT};
    border: 1px solid {LUNA_BUTTON_HOVER_BORDER};
    border-radius: 2px;
}}

QMenu {{
    background-color: #FFFFFF;
    color: {LUNA_TEXT};
    border: 1px solid {LUNA_CHROME_BORDER};
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {MENU_FONT_SIZE}px;
}}

QMenu::item {{
    color: {LUNA_TEXT};
    padding: 4px 20px;
}}

QMenu::item:selected {{
    background-color: {LUNA_BUTTON_HOVER};
    color: {LUNA_TEXT};
}}

/* ---------- Toolbar ---------- */
QToolBar {{
    background-color: {LUNA_CHROME_BG};
    border-bottom: 1px solid {LUNA_CHROME_BORDER};
    spacing: 2px;
    padding: 3px;
}}

/* Nav buttons (Back/Forward/Stop/Refresh/Home) are plain QPushButtons
   dropped into the toolbar, not QToolButtons - both selectors are
   listed here so both widget types get the same bevel styling. */
QToolButton, QToolBar QPushButton {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 3px;
    padding: 3px 8px;
    color: {LUNA_TEXT};
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {TOOLBAR_FONT_SIZE}px;
}}

QToolButton {{
    icon-size: 18px;
}}

QToolButton:hover, QToolBar QPushButton:hover {{
    background-color: {LUNA_BUTTON_HOVER};
    border: 1px solid {LUNA_BUTTON_HOVER_BORDER};
}}

QToolButton:pressed, QToolBar QPushButton:pressed {{
    background-color: {LUNA_BUTTON_PRESSED};
    border: 1px solid {LUNA_BUTTON_PRESSED_BORDER};
}}

QLineEdit#AddressBar {{
    background-color: white;
    color: {LUNA_TEXT};
    border: 1px solid {LUNA_BUTTON_HOVER_BORDER};
    border-radius: 2px;
    padding: 3px 6px;
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {MENU_FONT_SIZE}px;
    selection-background-color: {ADDRESS_SELECTION_BG};
    selection-color: {ADDRESS_SELECTION_TEXT};
}}

QToolButton#GoButton {{
    background-color: {GO_BUTTON_FACE};
    color: {GO_BUTTON_TEXT};
    border: 1px solid {LUNA_BUTTON_HOVER_BORDER};
    border-radius: 2px;
    padding: 3px;
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {TOOLBAR_FONT_SIZE}px;
}}

QToolButton#GoButton:hover {{
    background-color: {GO_BUTTON_HOVER};
    color: {GO_BUTTON_TEXT};
}}

QToolButton#GoButton:pressed {{
    background-color: {GO_BUTTON_PRESSED};
    color: {GO_BUTTON_TEXT};
}}

/* ---------- Tabs (IE8 style) ---------- */
QTabWidget::pane {{
    border: 1px solid {TAB_BORDER};
    top: -1px;
    background-color: {TAB_ACTIVE_BG};
}}

QTabBar {{
    background-color: {LUNA_CHROME_BG};
    color: {LUNA_TEXT};
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {TAB_FONT_SIZE}px;
}}

QTabBar::tab {{
    background-color: {TAB_INACTIVE_BG};
    color: {LUNA_TEXT};
    border: 1px solid {TAB_BORDER};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 5px 14px;
    margin-right: 1px;
    min-width: 100px;
}}

QTabBar::tab:selected {{
    background-color: {TAB_ACTIVE_BG};
    color: {LUNA_TEXT};
    font-weight: bold;
}}

QTabBar::tab:!selected {{
    margin-top: 2px;
}}

QToolButton#TabCloseButton {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 2px;
    color: {LUNA_TEXT};
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: 13px;
    font-weight: bold;
    padding: 0;
}}

QToolButton#TabCloseButton:hover {{
    background-color: {CLOSE_BUTTON_HOVER};
    border: 1px solid {CLOSE_BUTTON_PRESSED};
    color: #FFFFFF;
}}

QToolButton#TabCloseButton:pressed {{
    background-color: {CLOSE_BUTTON_PRESSED};
    color: #FFFFFF;
}}

/* The "+" new-tab button is a QPushButton set as the tab bar's
   corner widget - style it distinctly from the toolbar's nav buttons. */
QToolButton#NewTabButton {{
    background-color: {LUNA_CHROME_BG};
    color: {LUNA_TEXT};
    border: 1px solid {TAB_BORDER};
    border-radius: 3px;
    padding: 2px;
    margin: 2px 4px 0 0;
}}

QToolButton#NewTabButton:hover {{
    background-color: {LUNA_BUTTON_HOVER};
}}

/* ---------- Status Bar ---------- */
QStatusBar {{
    background-color: {LUNA_CHROME_BG};
    color: {LUNA_TEXT};
    border-top: 1px solid {LUNA_CHROME_BORDER};
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {STATUS_FONT_SIZE}px;
}}

QStatusBar::item {{
    border: none;
}}

QLabel#StatusSection {{
    color: {LUNA_TEXT};
    border-left: 1px solid {LUNA_CHROME_BORDER};
    border-top: 1px solid {LUNA_CHROME_BORDER};
    padding: 1px 8px;
    background-color: {LUNA_CHROME_BG};
}}

/* ---------- IE8-style utility windows ---------- */
QDialog#DownloadsDialog, QDialog#AboutDialog {{
    background-color: {LUNA_CHROME_BG};
    border: 1px solid {LUNA_CHROME_BORDER};
    color: {LUNA_TEXT};
}}

QWidget#DialogToolbar, QWidget#DialogContent {{
    background-color: {LUNA_CHROME_BG};
    color: {LUNA_TEXT};
}}

QPushButton {{
    background-color: {LUNA_BUTTON_FACE};
    border: 1px solid {LUNA_CHROME_BORDER};
    border-radius: 2px;
    color: {LUNA_TEXT};
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {TOOLBAR_FONT_SIZE}px;
    padding: 3px 10px;
}}

QPushButton:hover {{
    background-color: {LUNA_BUTTON_HOVER};
    border: 1px solid {LUNA_BUTTON_HOVER_BORDER};
}}

QPushButton:pressed {{
    background-color: {LUNA_BUTTON_PRESSED};
    border: 1px solid {LUNA_BUTTON_PRESSED_BORDER};
}}

QPushButton:disabled {{
    color: #7A8A99;
    background-color: #D6E0EA;
}}

QListWidget#DownloadsList {{
    background-color: #FFFFFF;
    border: 1px solid {LUNA_CHROME_BORDER};
    color: {LUNA_TEXT};
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {TOOLBAR_FONT_SIZE}px;
    padding: 3px;
}}

QListWidget#DownloadsList::item {{
    background-color: #F4F8FC;
    border: 1px solid #B2C5D8;
    color: {LUNA_TEXT};
    padding: 2px;
}}

QWidget#DownloadRow {{
    background-color: #F4F8FC;
    color: {LUNA_TEXT};
}}

QLabel#DownloadName {{
    color: {LUNA_TEXT};
    font-weight: bold;
}}

QLabel#DownloadPath, QLabel#DownloadStatus {{
    color: #4B6073;
    font-size: {STATUS_FONT_SIZE}px;
}}

QProgressBar {{
    background-color: #FFFFFF;
    border: 1px solid {LUNA_CHROME_BORDER};
    color: {LUNA_TEXT};
    text-align: center;
}}

QProgressBar::chunk {{
    background-color: {GO_BUTTON_FACE};
}}

QLabel#DialogHeading {{
    color: {TITLE_GRAD_START};
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: 18px;
    font-weight: bold;
}}

QLabel#DialogSubtitle {{
    color: {LUNA_TEXT};
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {MENU_FONT_SIZE}px;
    font-weight: bold;
}}

QLabel#DialogDetails {{
    color: {LUNA_TEXT};
    font-family: "{FONT_FAMILY}", sans-serif;
    font-size: {TOOLBAR_FONT_SIZE}px;
}}

#PermissionDialog {{
    background-color: {LUNA_CHROME_BG};
}}
"""