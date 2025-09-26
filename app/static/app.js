/**
 * This file handles all client-side interactivity:
 * - Listens for clicks on recommended preset buttons and pre-fills the form
 *   (plant, city, question) with their data attributes.
 * - Optionally auto-submits the form if the button includes data-autosubmit="1".
 * - Manages the "loading overlay" and disables form fields while the request is in progress.
 * - Re-enables the form if the user navigates back using the browser's back/forward cache.
 * 
 * This keeps the UI responsive, secure, and accessible, while delegating
 * all AI logic and validation to the Flask backend.
 */

(function () {
  const form = document.getElementById('ask-form');
  const plantInput = document.getElementById('plant');
  const cityInput = document.getElementById('city');
  const questionInput = document.getElementById('question');
  const submitBtn = document.getElementById('submit-btn');

  // Handle clicks on recommended preset buttons
  const presetsWrap = document.getElementById('presets');
  if (presetsWrap) {
    presetsWrap.addEventListener('click', (e) => {
      const btn = e.target.closest('.preset-btn');
      if (!btn) return;

      const { plant, city, question, autosubmit } = btn.dataset;

      // Fill form fields if provided
      if (typeof plant === 'string') {
        plantInput.value = plant;
        plantInput.dispatchEvent(new Event('input', { bubbles: true }));
      }
      if (typeof city === 'string' && city.trim() !== '') {
        cityInput.value = city;
        cityInput.dispatchEvent(new Event('input', { bubbles: true }));
      }
      if (typeof question === 'string') {
        questionInput.value = question;
        questionInput.dispatchEvent(new Event('input', { bubbles: true }));
      }

      // Focus the question field so user can tweak it if they want
      questionInput.focus();

      // If button requests auto-submit, send the form immediately
      if (autosubmit === '1' && questionInput.value.trim().length > 0) {
        form.requestSubmit();
      }
    });
  }

  // Show loading overlay & disable interactions during form submission
  if (form) {
    form.addEventListener('submit', () => {
      form.classList.add('is-submitting');
      submitBtn.disabled = true;
      plantInput.readOnly = true;
      cityInput.readOnly = true;
      questionInput.readOnly = true;
    });

    // Handle browser back/forward cache: restore form to usable state
    window.addEventListener('pageshow', (event) => {
      if (event.persisted) {
        form.classList.remove('is-submitting');
        submitBtn.disabled = false;
        plantInput.readOnly = false;
        cityInput.readOnly = false;
        questionInput.readOnly = false;
      }
    });
  }
})();
