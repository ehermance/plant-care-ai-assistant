/**
 * Client-side interactivity.
 *
 * Responsibilities:
 * - Prefills the form from recommended preset buttons (plant, city, question, care_context)
 * - Shows a single loading overlay that covers BOTH the form and answer columns
 * - Announces loading state via aria-live and toggles aria-busy for WCAG compliance
 * - Prevents interaction during submit without disabling the <select> (so its value posts)
 * - After a successful submit, focuses the Answer region and scrolls it into view (reduced-motion aware)
 * - Restores interactivity when navigating back via the browser cache (bfcache)
 */

(function () {
  const form = document.getElementById('ask-form');
  const presets = document.getElementById('presets');

  const plantInput = document.getElementById('plant');
  const cityInput = document.getElementById('city');
  const contextSelect = document.getElementById('care_context');
  const questionInput = document.getElementById('question');
  const submitBtn = document.getElementById('submit-btn');

  // The two-column container that gets the "is-submitting" class (shows overlay)
  const gridTwo = document.querySelector('.grid-two');
  const answerCard = document.querySelector('.answer-card');

  // Handle clicks on any preset button via event delegation.
  if (presets) {
    presets.addEventListener('click', (e) => {
      const btn = e.target.closest('.preset-btn');
      if (!btn) return;

      const { plant, city, question, context } = btn.dataset;

      if (typeof plant === 'string') plantInput.value = plant;
      if (typeof city === 'string' && city.trim() !== '') cityInput.value = city;
      if (typeof question === 'string') questionInput.value = question;
      if (typeof context === 'string') contextSelect.value = context;

      // Move focus where typing is most likely to continue
      questionInput.focus();
    });
  }

  function setSubmitting(on) {
    // Toggle state on the shared container to reveal the big overlay
    if (gridTwo) {
      gridTwo.classList.toggle('is-submitting', !!on);
      gridTwo.setAttribute('aria-busy', on ? 'true' : 'false');
    }

    // Prevent double submit
    if (submitBtn) submitBtn.disabled = !!on;

    // Make text areas/inputs readOnly so their values still POST
    ['plant','city','question'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.readOnly = !!on;
    });
    // Do NOT disable the <select>; disabled controls won't submit values
  }

  // Smooth scroll utility respecting prefers-reduced-motion
  function scrollIntoViewPref(el) {
    if (!el) return;
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduce) {
      el.scrollIntoView(); // no smooth to respect user's preference
    } else {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }

  if (form) {
    form.addEventListener('submit', () => {
      // Mark that this navigation resulted from a user submit so we can focus the answer on the next page
      try { sessionStorage.setItem('pcai-just-submitted', '1'); } catch (_) {}
      setSubmitting(true);
    });

    // If the page is restored from bfcache, remove the submitting state
    window.addEventListener('pageshow', (ev) => {
      if (ev.persisted) setSubmitting(false);
    });
  }

  // On load, if we just submitted and there's an answer, move focus to it and scroll it into view.
  // This helps on mobile where the answer may be off-screen.
  window.addEventListener('DOMContentLoaded', () => {
    let justSubmitted = false;
    try {
      justSubmitted = sessionStorage.getItem('pcai-just-submitted') === '1';
      // Always clear the flag so it doesn't trigger on unrelated navigations
      sessionStorage.removeItem('pcai-just-submitted');
    } catch (_) {}

    const hasAnswer = !!document.querySelector('.answer-card .prewrap');
    if (justSubmitted && hasAnswer && answerCard) {
      // Move programmatic focus (tabindex=-1 makes regions focusable)
      try { answerCard.focus({ preventScroll: true }); } catch (_) { /* older browsers */ }
      // Then scroll so it's visible
      scrollIntoViewPref(answerCard);
    }
  });

  // Footer year
  const yearEl = document.getElementById('copyright-year');
  if (yearEl) yearEl.textContent = String(new Date().getFullYear());
})();
