(function () {
  const form = document.getElementById('qa-form');
  if (!form) return;
  const srStatus = document.getElementById('sr-status');
  const submitBtn = document.getElementById('submitBtn');

  function setSubmitting(isSubmitting) {
    form.classList.toggle('is-submitting', isSubmitting);
    form.setAttribute('aria-busy', isSubmitting ? 'true' : 'false');

    // Disable only the submit button
    if (submitBtn) {
      submitBtn.disabled = isSubmitting;
      submitBtn.setAttribute('aria-disabled', isSubmitting ? 'true' : 'false');
    }

    // DO NOT disable fields; disabled fields are excluded from form POST.
    // Make text inputs/textarea read-only instead (they remain in payload).
    form.querySelectorAll('input, textarea').forEach(el => {
      if ('readOnly' in el) el.readOnly = isSubmitting;
    });

    if (isSubmitting && srStatus) srStatus.textContent = 'Submitting, please wait…';
    if (!isSubmitting && srStatus) srStatus.textContent = '';
  }

  form.addEventListener('submit', function () {
    // Let the browser submit normally; just show the loader + lock UX
    setSubmitting(true);
  });

  // If page is restored from bfcache, clear the lock
  window.addEventListener('pageshow', function (e) {
    if (e.persisted) setSubmitting(false);
  });
})();
