/**
 * Background service worker.
 * Redirects Google Search result pages to classic Web results
 * (udm=14) before the page renders, so AI Overview never has a
 * chance to flash on screen.
 */
importScripts('storage.js');

let cachedSettings = ClassicSearchDefaults;

getSettings().then((settings) => {
  cachedSettings = settings;
});

chrome.storage.onChanged.addListener((changes, area) => {
  if (area !== 'sync') return;
  for (const [key, { newValue }] of Object.entries(changes)) {
    cachedSettings[key] = newValue;
  }
});

/** True when the URL is a Google search results page missing udm=14. */
function needsRedirect(urlString) {
  let url;
  try {
    url = new URL(urlString);
  } catch {
    return null;
  }

  if (!url.pathname.startsWith('/search')) return null;
  if (!url.searchParams.has('q')) return null;
  if (url.searchParams.has('udm')) return null;

  url.searchParams.set('udm', '14');
  return url.toString();
}

chrome.webNavigation.onBeforeNavigate.addListener(
  (details) => {
    if (details.frameId !== 0) return;
    if (!cachedSettings.enabled || !cachedSettings.redirectSearches) return;

    const redirectUrl = needsRedirect(details.url);
    if (!redirectUrl) return;

    log(cachedSettings, 'redirecting', details.url, '->', redirectUrl);
    chrome.tabs.update(details.tabId, { url: redirectUrl });
  },
  { url: [{ pathContains: '/search' }] }
);
