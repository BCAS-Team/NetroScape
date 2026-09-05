"""
theme_loader.py

Picks the right CSS theme file for whatever URL is currently loaded,
and builds the small JS snippet used to inject it into the page.
"""

import os
from urllib.parse import urlparse

THEMES_DIR = os.path.join(os.path.dirname(__file__), "themes")

# Map a domain (or partial domain match) to a theme filename.
# Add more entries here as you build out more themes.
DOMAIN_THEMES = {
    "google.": "google_ie8.css",
    "youtube.com": "youtube.css",
    "spacehey.com": "spacehey.css",
}

DEFAULT_THEME = "default.css"

# The <style> tag we inject gets this id, so we can find + replace it
# on every page load instead of stacking up duplicate tags.
STYLE_TAG_ID = "netroscape-injected-style"


def get_theme_for_url(url: str) -> str:
    """Return the filename of the theme that matches this URL's domain."""
    if not url:
        return DEFAULT_THEME

    domain = urlparse(url).netloc.lower()

    for key, filename in DOMAIN_THEMES.items():
        if key in domain:
            return filename

    return DEFAULT_THEME


def load_css(theme_filename: str) -> str:
    """Read a theme file's contents. Falls back to empty string if missing."""
    path = os.path.join(THEMES_DIR, theme_filename)
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def build_injection_script(css: str) -> str:
    """
    Build a JS snippet that inserts (or replaces) a <style> tag containing
    our CSS. Using JSON-style escaping via repr-like quoting keeps this
    simple and safe for most CSS content.
    """
    # Escape backticks and backslashes so the CSS can't break out of the
    # JS template literal we're injecting it into.
    safe_css = css.replace("\\", "\\\\").replace("`", "\\`")

    return f"""
    (function() {{
        var existing = document.getElementById('{STYLE_TAG_ID}');
        if (existing) {{
            existing.remove();
        }}
        var style = document.createElement('style');
        style.id = '{STYLE_TAG_ID}';
        style.textContent = `{safe_css}`;
        document.head.appendChild(style);
    }})();
    """


def get_injection_script_for_url(url: str) -> str:
    """Convenience: URL in, ready-to-run JS string out."""
    theme_file = get_theme_for_url(url)
    css = load_css(theme_file)
    return build_injection_script(css)