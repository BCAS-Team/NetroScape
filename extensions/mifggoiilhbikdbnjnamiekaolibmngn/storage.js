/**
 * Shared chrome.storage.sync helper.
 * Loaded in the background service worker (via importScripts),
 * content scripts, popup, and options page — same defaults everywhere.
 */
const ClassicSearchDefaults = Object.freeze({
  enabled: true,
  redirectSearches: true,
  hideAIOverview: true,
  hideAIMode: true,
  autoUpdateSelectors: true,
  enableLogging: false,
  debugMode: false,
  customCSS: ''
});

/** Resolve current settings, backfilling any missing keys with defaults. */
function getSettings() {
  return new Promise((resolve) => {
    chrome.storage.sync.get(ClassicSearchDefaults, (items) => {
      resolve(items);
    });
  });
}

/** Persist a partial settings patch. */
function setSettings(patch) {
  return new Promise((resolve) => {
    chrome.storage.sync.set(patch, resolve);
  });
}

function log(settings, ...args) {
  if (settings && settings.enableLogging) {
    // eslint-disable-next-line no-console
    console.log('[Classic Google Search]', ...args);
  }
}
