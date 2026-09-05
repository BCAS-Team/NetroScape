const toggleBtn = document.getElementById('toggle');

chrome.storage.sync.get(['enabled'], function(result) {
  const enabled = result.enabled !== false;
  toggleBtn.textContent = enabled ? 'Turn Off' : 'Turn On';
  toggleBtn.classList.toggle('off', !enabled);
});

toggleBtn.addEventListener('click', () => {
  chrome.storage.sync.get(['enabled'], function(result) {
    const newState = !(result.enabled !== false);
    chrome.storage.sync.set({ enabled: newState });
    toggleBtn.textContent = newState ? 'Turn Off' : 'Turn On';
    toggleBtn.classList.toggle('off', !newState);
  });
});
