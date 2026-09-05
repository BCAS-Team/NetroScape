/**
 * Centralized selector registry for Classic Google Search.
 *
 * Google changes its DOM structure often and does not expose stable
 * class names. Every selector list below is used as a "best effort"
 * match: content.js walks these lists and removes whatever matches,
 * without assuming any single selector is permanent.
 *
 * To adapt to a future Google redesign, add new selectors to the
 * relevant array below. Do not touch content.js.
 */
const ClassicSearchSelectors = {
  /**
   * AI Overview / SGE container candidates.
   * Matches both current and legacy attribute/id/class patterns Google
   * has used to mount the generative AI summary block above results.
   */
  aiOverview: [
    '#m-x-content',
    'div[data-attrid="AIOverview"]',
    'div[data-attrid*="GenerativeContent"]',
    'div[jsname="qEgvXe"]',
    'block-component',
    'div[data-async-context*="ai_overview"]',
    'div[data-async-context*="bard"]',
    '#ai-overview',
    '.EEfMYd',
    '.LT6XE',
    '.dfsMSb',
    'div[aria-label="AI Overview"]',
    'div[aria-label*="AI-generated"]'
  ],

  /**
   * "AI Mode" / "Ask AI" navigation entry points: top search tabs,
   * pill buttons, and side-panel entry points.
   */
  aiModeNav: [
    'a[href*="udm=50"]',
    'a[href*="/aimode"]',
    'div[aria-label="AI Mode"]',
    'div[data-attrid="AIMode"]',
    'a[aria-label*="AI Mode"]',
    'a[aria-label*="Ask AI"]',
    '.ZjyBRc',
    '.YmvwI'
  ],

  /**
   * The horizontal results tab strip (All / Images / News / ...).
   * Used only as a search boundary — never removed — so that AI tab
   * entries can be pruned from inside it without breaking navigation.
   */
  resultsTabStrip: [
    '#hdtb-msb',
    'div[role="navigation"] g-scrolling-carousel',
    '.crJ18e'
  ],

  /** Text labels that identify an AI-related tab/button when present. */
  aiLabelText: ['AI Mode', 'Ask AI', 'AI Overview']
};

// Expose read-only to avoid accidental mutation from content.js.
Object.freeze(ClassicSearchSelectors);
Object.keys(ClassicSearchSelectors).forEach((key) => {
  if (Array.isArray(ClassicSearchSelectors[key])) {
    Object.freeze(ClassicSearchSelectors[key]);
  }
});
