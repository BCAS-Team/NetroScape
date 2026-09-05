/**
 * Content script — runs on Google Search result pages.
 * 1. Fallback redirect to udm=14 (covers Google's client-side
 *    SPA navigation, which background.js's webNavigation listener
 *    cannot see because the tab URL changes without a real navigation).
 * 2. Removes AI Overview and AI Mode elements as they appear, via a
 *    single shared MutationObserver.
 *
 * All selectors live in selectors.js — this file only contains the
 * generic "find and remove" logic, so new Google DOM changes only
 * ever require editing that one file.
 */
(() => {
  let settings = ClassicSearchDefaults;
  let observer = null;
  let idleTimer = null;
  const IDLE_DISCONNECT_MS = 20000;

  function redirectIfNeeded() {
    if (!settings.enabled || !settings.redirectSearches) return;

    const url = new URL(window.location.href);
    if (!url.pathname.startsWith('/search')) return;
    if (!url.searchParams.has('q')) return;
    if (url.searchParams.has('udm')) return;

    url.searchParams.set('udm', '14');
    window.location.replace(url.toString());
  }

  function removeBySelectors(selectorList) {
    let removedCount = 0;
    for (const selector of selectorList) {
      let nodes;
      try {
        nodes = document.querySelectorAll(selector);
      } catch {
        continue; // guard against a future invalid/unsupported selector
      }
      nodes.forEach((node) => {
        if (node && node.isConnected) {
          node.remove();
          removedCount += 1;
        }
      });
    }
    return removedCount;
  }

  /** Removes AI-labeled tab/button entries without touching the tab strip itself. */
  function removeAILabeledNavItems() {
    let removedCount = 0;
    for (const stripSelector of ClassicSearchSelectors.resultsTabStrip) {
      const strip = document.querySelector(stripSelector);
      if (!strip) continue;
      strip.querySelectorAll('a, div[role="link"], button').forEach((item) => {
        const text = (item.textContent || '').trim();
        if (ClassicSearchSelectors.aiLabelText.includes(text)) {
          item.remove();
          removedCount += 1;
        }
      });
    }
    return removedCount;
  }

  function sweep() {
    let removed = 0;
    if (settings.hideAIOverview) {
      removed += removeBySelectors(ClassicSearchSelectors.aiOverview);
    }
    if (settings.hideAIMode) {
      removed += removeBySelectors(ClassicSearchSelectors.aiModeNav);
      removed += removeAILabeledNavItems();
    }
    if (removed > 0) {
      log(settings, `removed ${removed} AI element(s)`);
      resetIdleTimer();
    }
  }

  function resetIdleTimer() {
    if (idleTimer) clearTimeout(idleTimer);
    idleTimer = setTimeout(() => {
      log(settings, 'no AI elements for a while, disconnecting observer');
      disconnectObserver();
    }, IDLE_DISCONNECT_MS);
  }

  function disconnectObserver() {
    if (observer) {
      observer.disconnect();
      observer = null;
    }
    if (idleTimer) {
      clearTimeout(idleTimer);
      idleTimer = null;
    }
  }

  function startObserver() {
    if (observer) return;
    if (!settings.hideAIOverview && !settings.hideAIMode) return;

    let scheduled = false;
    observer = new MutationObserver(() => {
      if (scheduled) return;
      scheduled = true;
      requestAnimationFrame(() => {
        scheduled = false;
        sweep();
      });
    });
    observer.observe(document.documentElement, { childList: true, subtree: true });
    resetIdleTimer();
  }

  function applyCustomCSS() {
    if (!settings.customCSS) return;
    const styleId = 'classic-google-search-custom-css';
    let styleTag = document.getElementById(styleId);
    if (!styleTag) {
      styleTag = document.createElement('style');
      styleTag.id = styleId;
      (document.head || document.documentElement).appendChild(styleTag);
    }
    styleTag.textContent = settings.customCSS;
  }

  function init(nextSettings) {
    settings = nextSettings;

    if (!settings.enabled) {
      disconnectObserver();
      return;
    }

    redirectIfNeeded();
    sweep();
    startObserver();
    applyCustomCSS();
  }

  // Re-check on Google's internal SPA navigations (e.g. typing a new
  // query from the results page updates history without a full load).
  window.addEventListener('popstate', () => init(settings));
  const originalPushState = history.pushState;
  history.pushState = function patchedPushState(...args) {
    originalPushState.apply(this, args);
    init(settings);
  };

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && settings.enabled) {
      startObserver();
      sweep();
    }
  });

  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== 'sync') return;
    const updated = { ...settings };
    for (const [key, { newValue }] of Object.entries(changes)) {
      updated[key] = newValue;
    }
    init(updated);
  });

  getSettings().then(init);
})();
