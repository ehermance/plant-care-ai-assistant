(function() {
  'use strict';
  /**
 * Client-side interactivity.
 *
 * - Prefill form from preset buttons (plant, question, context, optional city)
 * - One overlay for both columns; announces aria-busy/live
 * - Keeps select enabled so value posts; text inputs become readOnly while submitting
 * - After submit, focuses the Answer region and scrolls into view (reduced-motion aware)
 * - Units toggle (°F default, persisted to localStorage) controls presentation only
 * - Restores interactivity on bfcache navigation
 * - Reset button clears fields to a clean state (not just HTML “reset” to initial values)
 */

(function () {
  const form = document.getElementById('ask-form');
  const presets = document.getElementById('presets');

  const plantInput = document.getElementById('plant');
  const cityInput = document.getElementById('city');
  const contextSelect = document.getElementById('care_context');
  const questionInput = document.getElementById('question');
  const submitBtn = document.getElementById('submit-btn');
  const resetBtn = document.getElementById('reset-btn');

  const gridTwo = document.querySelector('.grid-two');
  const answerCard = document.querySelector('.answer-card');

  // --- Presets ---
  if (presets) {
    presets.addEventListener('click', (e) => {
      const btn = e.target.closest('.preset-btn');
      if (!btn) return;

      const { plant, city, question, context } = btn.dataset;

      if (typeof plant === 'string') plantInput.value = plant;
      if (typeof city === 'string' && city.trim() !== '') cityInput.value = city;
      if (typeof question === 'string') questionInput.value = question;
      if (typeof context === 'string') contextSelect.value = context;

      questionInput.focus();
    });
  }

  // --- Reset (clear) button ---
  if (resetBtn) {
    resetBtn.addEventListener('click', () => {
      // Clear all fields to blank, and reset context to the default option
      if (plantInput) plantInput.value = '';
      if (cityInput) cityInput.value = '';
      if (questionInput) questionInput.value = '';
      if (contextSelect) contextSelect.value = 'indoor_potted';

      // Put focus in the first field for quick typing
      plantInput?.focus();
    });
  }

  // --- Submit loading state ---
  function setSubmitting(on) {
    if (gridTwo) {
      gridTwo.classList.toggle('is-submitting', !!on);
      gridTwo.setAttribute('aria-busy', on ? 'true' : 'false');
    }
    if (submitBtn) submitBtn.disabled = !!on;
    ['plant','city','question'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.readOnly = !!on;
    });
  }

  function scrollIntoViewPref(el) {
    if (!el) return;
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduce) el.scrollIntoView();
    else el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  if (form) {
    form.addEventListener('submit', () => {
      try { sessionStorage.setItem('pcai-just-submitted', '1'); } catch (_) {}
      setSubmitting(true);
    });
    window.addEventListener('pageshow', (ev) => {
      if (ev.persisted) setSubmitting(false);
    });
  }

  window.addEventListener('DOMContentLoaded', () => {
    // Focus answer after successful submit
    let justSubmitted = false;
    try {
      justSubmitted = sessionStorage.getItem('pcai-just-submitted') === '1';
      sessionStorage.removeItem('pcai-just-submitted');
    } catch (_) {}
    const hasAnswer = !!document.querySelector('.answer-card .prewrap');
    if (justSubmitted && hasAnswer && answerCard) {
      try { answerCard.focus({ preventScroll: true }); } catch (_) {}
      scrollIntoViewPref(answerCard);
    }

    // Units toggle (persisted) — default °F
    const weatherSection = document.getElementById('weather-section');
    if (weatherSection) {
      const saved = (localStorage.getItem('pcai-units') || 'f').toLowerCase();
      if (saved === 'c' || saved === 'f') {
        weatherSection.setAttribute('data-units', saved);
        const radio = document.querySelector(`.units-toggle input[value="${saved}"]`);
        if (radio) radio.checked = true;
      } else {
        weatherSection.setAttribute('data-units', 'f');
        const radioF = document.querySelector('.units-toggle input[value="f"]');
        if (radioF) radioF.checked = true;
      }

      document.querySelectorAll('.units-toggle input[name="units"]').forEach((input) => {
        input.addEventListener('change', () => {
          const val = input.value === 'c' ? 'c' : 'f';
          weatherSection.setAttribute('data-units', val);
          try { localStorage.setItem('pcai-units', val); } catch (_) {}
        });
      });
    }
  });

  // Footer year
  const yearEl = document.getElementById('copyright-year');
  if (yearEl) yearEl.textContent = String(new Date().getFullYear());
})();
})();
