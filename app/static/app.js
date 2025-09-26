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
    form.addEventListener('submit', () => {
      // Visual lock + overlay
      form.classList.add('is-submitting');

      // Disable the submit button to prevent double submits
      if (submitBtn) submitBtn.disabled = true;

      // Set text inputs/textarea to readOnly so user cannot modify values during submit
      [plantInput, cityInput, questionInput].forEach((el) => el && (el.readOnly = true));

      // IMPORTANT: Do NOT disable the <select>. Disabled fields are not submitted.
      // We rely on CSS (.is-submitting) to block interaction with it.
      // if (contextSelect) contextSelect.disabled = true;  // intentionally NOT used
    });

    // When navigating back/forward, some browsers use the bfcache and keep the DOM alive.
    // This event lets us restore the interactive state cleanly.
    window.addEventListener('pageshow', (event) => {
      if (event.persisted) {
        form.classList.remove('is-submitting');
        if (submitBtn) submitBtn.disabled = false;
        [plantInput, cityInput, questionInput].forEach((el) => el && (el.readOnly = false));
        // contextSelect remains enabled (we never disabled it)
      }
    });
  }
})();
