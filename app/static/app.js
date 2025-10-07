/**
 * Client-side interactivity.
 *
 * Responsibilities:
 * - Prefills the form from recommended preset buttons (plant, city, question, care_context)
 * - Shows a loading overlay and prevents interaction while submitting
 * - IMPORTANT: does NOT disable the <select> so its value is included in POST
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

  // Handle clicks on any .preset-btn within the presets container.
  // Uses event delegation so adding/removing buttons requires no extra JS wiring.
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

  if (form) {
    const formCard = document.querySelector('.form-card');
    const answerCard = document.querySelector('.answer-card');

    function setSubmitting(on) {
      // Toggle loading state on the cards to reveal overlays
      if (formCard) {
        formCard.classList.toggle('is-submitting', on);
        formCard.setAttribute('aria-busy', on ? 'true' : 'false');
      }
      if (answerCard) {
        answerCard.classList.toggle('is-submitting', on);
        answerCard.setAttribute('aria-busy', on ? 'true' : 'false');
      }

      // Prevent double submit
      const submitBtn = document.getElementById('submit-btn');
      if (submitBtn) submitBtn.disabled = !!on;

      // Make text fields readOnly so values still POST
      ['plant','city','question'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.readOnly = !!on;
      });
      // Don't disable the <select>; disabled fields don't submit
    }

    form.addEventListener('submit', () => setSubmitting(true));

    // Restore state if user navigates back via bfcache
    window.addEventListener('pageshow', (ev) => {
      if (ev.persisted) setSubmitting(false);
    });
  }

  // Footer year
  const yearEl = document.getElementById('copyright-year');
  if (yearEl) yearEl.textContent = String(new Date().getFullYear());
})();
