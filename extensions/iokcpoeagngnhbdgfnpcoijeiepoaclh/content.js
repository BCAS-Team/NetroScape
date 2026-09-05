function removeAIMode() {
  if (!window.extensionEnabled) return;
  // Remove AI Mode tab
  const aiTabs = Array.from(document.querySelectorAll('a, div, span'))
    .filter(el => el.textContent.trim() === "AI Mode");
  aiTabs.forEach(el => el.remove());

  // Remove AI Overview
  const aiOverviews = document.querySelectorAll('[data-async-context*="ai"], [data-attrid*="ai"], [data-hveid*="AI"], div:has(span:contains("AI Overview"))');
  aiOverviews.forEach(el => el.remove());
}

function setupObserver() {
  const observer = new MutationObserver(removeAIMode);
  observer.observe(document.body, { childList: true, subtree: true });
}

chrome.storage.sync.get(['enabled'], function(result) {
  window.extensionEnabled = result.enabled !== false;
  if (window.extensionEnabled) {
    removeAIMode();
    setupObserver();
  }
});

chrome.storage.onChanged.addListener(function(changes) {
  if (changes.enabled) {
    window.extensionEnabled = changes.enabled.newValue;
    if (window.extensionEnabled) {
      removeAIMode();
      setupObserver();
    }
  }
});
