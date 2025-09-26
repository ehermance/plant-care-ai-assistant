(function () {
  const form = document.getElementById('qa-form');
  if (!form) return;

  const srStatus = document.getElementById('sr-status');
  const submitBtn = document.getElementById('submitBtn');

  // Loader/lock UX
  function setSubmitting(isSubmitting) {
    form.classList.toggle('is-submitting', isSubmitting);
    form.setAttribute('aria-busy', isSubmitting ? 'true' : 'false');

    // Disable only the submit button
    if (submitBtn) {
      submitBtn.disabled = isSubmitting;
      submitBtn.setAttribute('aria-disabled', isSubmitting ? 'true' : 'false');
    }

    // Make fields read-only (remain in POST payload)
    form.querySelectorAll('input, textarea').forEach(el => {
      if ('readOnly' in el) el.readOnly = isSubmitting;
    });

    if (isSubmitting && srStatus) srStatus.textContent = 'Submitting, please wait…';
    if (!isSubmitting && srStatus) srStatus.textContent = '';
  }

  form.addEventListener('submit', function () { setSubmitting(true); });
  window.addEventListener('pageshow', e => { if (e.persisted) setSubmitting(false); });

  // ---------- Presets panel ----------
  const presetsContainer = document.getElementById('presets-container');
  const presetsList = document.getElementById('presets-list');

  if (presetsContainer && presetsList) {
    // Try geolocation first (user consent); fallback to city input; else default
    const cityInput = document.getElementById('city');

    function renderPresets(region, items) {
      presetsContainer.hidden = false;
      document.getElementById('presets-region').textContent = region;

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
            // Seed a useful default question
            questionField.value = `Care essentials for ${item.plant}?`;
            questionField.focus();
          }
        });
        presetsList.appendChild(li);
      });
    }

    function fetchPresets(params) {
      const url = new URL('/presets', window.location.origin);
      Object.entries(params || {}).forEach(([k, v]) => { if (v != null && v !== '') url.searchParams.set(k, v); });
      fetch(url.toString(), { method: 'GET', credentials: 'same-origin' })
        .then(r => r.json())
        .then(data => renderPresets(data.region, data.items))
        .catch(() => { /* fail silent; panel stays hidden */ });
    }

    // Attempt geolocation (high accuracy not needed)
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
        // On error/denied, fallback
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
