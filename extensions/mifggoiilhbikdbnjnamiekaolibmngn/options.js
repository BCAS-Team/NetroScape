/**
 * Options page logic. Auto-saves on change (debounced for the
 * free-text CSS field) — no explicit "Save" button needed.
 */
let saveNoteTimer = null;

function flashSaved() {
  const note = document.getElementById('saveNote');
  note.textContent = 'Saved';
  if (saveNoteTimer) clearTimeout(saveNoteTimer);
  saveNoteTimer = setTimeout(() => {
    note.textContent = '';
  }, 1500);
}

function debounce(fn, delay) {
  let timer = null;
  return (...args) => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

async function init() {
  const settings = await getSettings();
  document.getElementById('enableLogging').checked = settings.enableLogging;
  document.getElementById('debugMode').checked = settings.debugMode;
  document.getElementById('customCSS').value = settings.customCSS;

  document.getElementById('enableLogging').addEventListener('change', (e) => {
    setSettings({ enableLogging: e.target.checked }).then(flashSaved);
  });

  document.getElementById('debugMode').addEventListener('change', (e) => {
    setSettings({ debugMode: e.target.checked }).then(flashSaved);
  });

  const saveCSS = debounce((value) => {
    setSettings({ customCSS: value }).then(flashSaved);
  }, 400);

  document.getElementById('customCSS').addEventListener('input', (e) => {
    saveCSS(e.target.value);
  });

  document.getElementById('resetBtn').addEventListener('click', async () => {
    if (!confirm('Reset Classic Google Search to default settings?')) return;
    await setSettings({ ...ClassicSearchDefaults });
    await init();
    flashSaved();
  });
}

init();
