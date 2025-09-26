/*
Enhances the form UX: displays a loading overlay during submission, locks
fields without removing them from the POST payload, and populates a presets
panel by calling /presets using geolocation or the current city field.
*/

(function () {
  const form = document.getElementById('qa-form');
  if (!form) return;

  const srStatus = document.getElementById('sr-status');
  const submitBtn = document.getElementById('submitBtn');

  // Toggle submitting UI: overlay, aria-busy, readOnly fields.
  function setSubmitting(isSubmitting) {
    form.classList.toggle('is-submitting', isSubmitting);
    form.setAttribute('aria-busy', isSubmitting ? 'true' : 'false');

    // Avoid disabling inputs (disabled fields are dropped from POST),
    // but disabling the submit button is safe.
    if (submitBtn) {
      submitBtn.disabled = isSubmitting;
      submitBtn.setAttribute('aria-disabled', isSubmitting ? 'true' : 'false');
    }

    form.querySelectorAll('input, textarea').forEach(el => {
      if ('readOnly' in el) el.readOnly = isSubmitting;
    });

    if (isSubmitting && srStatus) srStatus.textContent = 'Submitting, please wait…';
    if (!isSubmitting && srStatus) srStatus.textContent = '';
  }

  form.addEventListener('submit', function () {
    setSubmitting(true);
  });

  // Handle bfcache restores.
  window.addEventListener('pageshow', function (e) {
    if (e.persisted) setSubmitting(false);
  });

  // ---- Presets ----
  const presetsContainer = document.getElementById('presets-container');
  const presetsList = document.getElementById('presets-list');

  if (presetsContainer && presetsList) {
    const cityInput = document.getElementById('city');

    function renderPresets(region, items) {
      presetsContainer.hidden = false;
      const regionEl = document.getElementById('presets-region');
      if (regionEl) regionEl.textContent = region;

      presetsList.innerHTML = '';
      items.forEach(item => {
        const li = document.createElement('li');
        li.className = 'preset-card';
        li.innerHTML = `
          <button type="button" class="preset-btn" aria-label="Use preset ${item.plant}">
            <div class="preset-plant">${item.plant}</div>
            <div class="preset-why">${item.why}</div>
            <div class="preset-care">${item.starter_care}</div>
          </button>
        `;
        li.querySelector('button').addEventListener('click', () => {
          const plantField = document.getElementById('plant');
          const questionField = document.getElementById('question');
          if (plantField) plantField.value = item.plant;
          if (questionField) {
            questionField.value = `Care essentials for ${item.plant}?`;
            questionField.focus();
          }
        });
        presetsList.appendChild(li);
      });
    }

    function fetchPresets(params) {
      const url = new URL('/presets', window.location.origin);
      Object.entries(params || {}).forEach(([k, v]) => {
        if (v != null && v !== '') url.searchParams.set(k, v);
      });
      fetch(url.toString(), { method: 'GET', credentials: 'same-origin' })
        .then(r => r.json())
        .then(data => renderPresets(data.region, data.items))
        .catch(() => { /* Silent failure: panel remains hidden */ });
    }

    // Prefer geolocation; fall back to the City field; else default.
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        pos => {
          const { latitude, longitude } = pos.coords || {};
          if (typeof latitude === 'number' && typeof longitude === 'number') {
            fetchPresets({ lat: latitude.toFixed(4), lon: longitude.toFixed(4) });
          } else if (cityInput && cityInput.value) {
            fetchPresets({ city: cityInput.value });
          } else {
            fetchPresets({});
          }
        },
        () => {
          if (cityInput && cityInput.value) fetchPresets({ city: cityInput.value });
          else fetchPresets({});
        },
        { timeout: 5000, maximumAge: 600000, enableHighAccuracy: false }
      );
    } else {
      if (cityInput && cityInput.value) fetchPresets({ city: cityInput.value });
      else fetchPresets({});
    }
  }
})();
