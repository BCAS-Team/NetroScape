/**
 * Popup UI logic. Reads/writes chrome.storage.sync via storage.js
 * and reflects state instantly — no reload required on the page,
 * since content.js listens for storage.onChanged.
 */
// TODO before publishing: replace with your real repository and
// Chrome Web Store listing URLs.
const LINKS = {
  github: 'https://github.com/elfarsaouiomar/hide-gemini',
  rate: 'https://chromewebstore.google.com/detail/classic-google-search/mifggoiilhbikdbnjnamiekaolibmngn',
  report: 'https://github.com/elfarsaouiomar/hide-gemini/issues/new'
};

const CHECKBOX_KEYS = [
  'redirectSearches',
  'hideAIOverview',
  'hideAIMode',
  'autoUpdateSelectors'
];

function reflectSettings(settings) {
  document.getElementById('enabledToggle').checked = settings.enabled;
  document.getElementById('statusText').textContent = settings.enabled
    ? 'Enabled'
    : 'Disabled';
  for (const key of CHECKBOX_KEYS) {
    document.getElementById(key).checked = settings[key];
  }
}

function bindToggle(id, key) {
  document.getElementById(id).addEventListener('change', (event) => {
    setSettings({ [key]: event.target.checked });
    if (key === 'enabled') {
      document.getElementById('statusText').textContent = event.target.checked
        ? 'Enabled'
        : 'Disabled';
    }
  });
}

function bindLink(id, url) {
  document.getElementById(id).addEventListener('click', () => {
    chrome.tabs.create({ url });
  });
}

async function init() {
  const settings = await getSettings();
  reflectSettings(settings);

  bindToggle('enabledToggle', 'enabled');
  for (const key of CHECKBOX_KEYS) {
    bindToggle(key, key);
  }

  bindLink('githubBtn', LINKS.github);
  bindLink('rateBtn', LINKS.rate);
  bindLink('reportBtn', LINKS.report);

  document.getElementById('optionsLink').addEventListener('click', (event) => {
    event.preventDefault();
    chrome.runtime.openOptionsPage();
  });
}

init();
