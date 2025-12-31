/**
 * Plant Onboarding Wizard
 * Multi-step wizard for adding a new plant with reminders.
 */

(function() {
  'use strict';

  let currentStep = 1;
  const totalSteps = 3;
  let plantId = null; // Will be set after step 2 submission

  function updateProgress() {
    const stepEl = document.getElementById('current-step');
    const progressBar = document.getElementById('progress-bar');
    if (stepEl) stepEl.textContent = currentStep;
    if (progressBar) progressBar.style.width = `${(currentStep / totalSteps) * 100}%`;
  }

  function showStep(step) {
    // Hide all steps
    document.querySelectorAll('.step-content').forEach(el => {
      el.classList.add('hidden');
    });

    // Show current step
    const stepEl = document.getElementById(`step-${step}`);
    if (stepEl) stepEl.classList.remove('hidden');

    // Update progress
    updateProgress();

    // Scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function nextStep() {
    if (currentStep < totalSteps) {
      // If moving from step 1 to step 2, copy marketing opt-in preference
      if (currentStep === 1) {
        const marketingCheckbox = document.getElementById('onboarding_marketing_opt_in');
        const marketingHidden = document.getElementById('marketing_opt_in_hidden');
        if (marketingCheckbox && marketingHidden) {
          marketingHidden.value = marketingCheckbox.checked ? 'on' : '';
        }
      }

      currentStep++;
      showStep(currentStep);
    }
  }

  function prevStep() {
    if (currentStep > 1) {
      currentStep--;
      showStep(currentStep);
    }
  }

  function submitAndContinue() {
    const form = document.getElementById('onboarding-form');
    if (!form) return;

    const formData = new FormData(form);

    // Validate required fields
    const nameInput = document.getElementById('name');
    if (nameInput && !nameInput.value.trim()) {
      nameInput.focus();
      nameInput.reportValidity();
      return;
    }

    // Submit form via fetch to avoid page reload
    fetch(form.action, {
      method: 'POST',
      body: formData
    })
    .then(response => response.json())
    .then(data => {
      if (data.success) {
        // Store plant ID for step 3
        plantId = data.plant_id;

        // Move to step 3
        nextStep();
      } else {
        alert(data.message || 'Error creating plant. Please try again.');
      }
    })
    .catch(error => {
      console.error('Error:', error);
      alert('Error creating plant. Please try again.');
    });
  }

  function toggleReminderFields(skipChecked) {
    const frequencySelect = document.getElementById('watering_frequency');
    if (frequencySelect) {
      if (skipChecked) {
        frequencySelect.removeAttribute('required');
        frequencySelect.disabled = true;
      } else {
        frequencySelect.setAttribute('required', 'required');
        frequencySelect.disabled = false;
      }
    }
  }

  // Initialize when DOM is ready
  document.addEventListener('DOMContentLoaded', function() {
    // Only run on onboarding page
    if (!document.getElementById('step-1')) return;

    // Initialize first step
    showStep(1);

    // Event delegation for step navigation buttons
    document.addEventListener('click', function(e) {
      const btn = e.target.closest('[data-action]');
      if (!btn) return;

      const action = btn.dataset.action;
      switch (action) {
        case 'next-step':
          nextStep();
          break;
        case 'prev-step':
          prevStep();
          break;
        case 'submit-continue':
          submitAndContinue();
          break;
      }
    });

    // Handle skip reminder checkbox
    const skipReminderCheckbox = document.getElementById('skip_reminder');
    if (skipReminderCheckbox) {
      skipReminderCheckbox.addEventListener('change', function() {
        toggleReminderFields(this.checked);
      });
    }
  });
})();
