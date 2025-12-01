/**
 * Dashboard Quick Complete Functionality
 * Handles AJAX completion of reminders from the dashboard view
 */

(function() {
  'use strict';

  document.addEventListener('DOMContentLoaded', function() {
    
    function updateGreeting() {
        // Get the current local hour using the client's system clock
        const now = new Date();
        const hour = now.getHours(); // getHours() returns 0-23
        let greetingMessage;

        // Determine the appropriate greeting based on the hour
        if (hour < 12) {
            greetingMessage = "Good morning";
        } else if (hour < 18) {
            greetingMessage = "Good afternoon";
        } else {
            greetingMessage = "Good evening";
        }

        const greetingElement = document.getElementById('greeting-display'); 
        if (greetingElement) {
            greetingElement.textContent = greetingMessage + "!";
        } else {
            console.error("Error: Could not find element with ID 'greeting-display'.");
        }
    }

    // Call the greeting function immediately when the DOM is ready
    updateGreeting();

    // Plant carousel scroll functionality with gradient indicators
    const scrollContainer = document.getElementById('dashboard-plants-scroll-container');
    const scrollLeftBtn = document.getElementById('dashboard-scroll-left-btn');
    const scrollRightBtn = document.getElementById('dashboard-scroll-right-btn');
    const gradientLeft = document.getElementById('dashboard-gradient-left');
    const gradientRight = document.getElementById('dashboard-gradient-right');

    if (scrollContainer && scrollLeftBtn && scrollRightBtn) {
      // Scroll distance (approximately 3 plant cards)
      const scrollDistance = 300;

      // Update button states and gradient visibility based on scroll position
      function updateScrollState() {
        const { scrollLeft, scrollWidth, clientWidth } = scrollContainer;
        const maxScroll = scrollWidth - clientWidth;

        // Update button states
        scrollLeftBtn.disabled = scrollLeft <= 1;
        scrollRightBtn.disabled = scrollLeft >= maxScroll - 1;

        // Update gradient indicators
        if (gradientLeft) {
          gradientLeft.style.opacity = scrollLeft > 10 ? '1' : '0';
        }
        if (gradientRight) {
          gradientRight.style.opacity = scrollLeft < maxScroll - 10 ? '1' : '0';
        }
      }

      // Scroll left
      scrollLeftBtn.addEventListener('click', () => {
        scrollContainer.scrollBy({ left: -scrollDistance, behavior: 'smooth' });
      });

      // Scroll right
      scrollRightBtn.addEventListener('click', () => {
        scrollContainer.scrollBy({ left: scrollDistance, behavior: 'smooth' });
      });

      // Update states on scroll
      scrollContainer.addEventListener('scroll', updateScrollState);

      // Initial state
      updateScrollState();

      // Re-check after images load (they might affect scrollWidth)
      window.addEventListener('load', () => {
        setTimeout(updateScrollState, 100);
      });
    }

    // Get CSRF token securely from data attribute
    const csrfTokenEl = document.getElementById('csrf-token');
    if (!csrfTokenEl) return; // No CSRF token, no reminders to complete

    const csrfToken = csrfTokenEl.dataset.csrf;
    const completeButtons = document.querySelectorAll('.quick-complete-btn');

    completeButtons.forEach(button => {
      button.addEventListener('click', async function(e) {
        e.preventDefault();

        const reminderId = this.dataset.reminderId;
        const reminderTitle = this.dataset.reminderTitle;
        const reminderItem = this.closest('[data-reminder-id]');

        // Disable button and show loading state
        this.disabled = true;
        this.innerHTML = '⏳ Completing...';

        try {
          const response = await fetch(`/reminders/api/${reminderId}/complete`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': csrfToken
            }
          });

          const data = await response.json();

          if (data.success) {
            // Check if user prefers reduced motion
            const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

            if (prefersReducedMotion) {
              // Instant removal for reduced motion preference
              reminderItem.remove();
              handlePostRemoval();
            } else {
              // Fade out and remove the reminder item
              reminderItem.style.opacity = '0';
              reminderItem.style.transition = 'opacity 0.3s ease';

              setTimeout(() => {
                reminderItem.remove();
                handlePostRemoval();
              }, 300);
            }

            function handlePostRemoval() {
              // Check if Today's Focus or Reminders list is empty
              const focusList = document.getElementById('todays-focus-list');
              const remindersList = document.getElementById('dashboard-reminders-list');

              const focusEmpty = focusList && focusList.children.length === 0;
              const remindersEmpty = remindersList && remindersList.children.length === 0;

              // Reload page if either list becomes empty to show proper empty state
              if (focusEmpty || remindersEmpty) {
                window.location.reload();
              } else {
                // Show success message
                if (window.showToast) {
                  window.showToast(`✓ ${reminderTitle} marked complete!`, 'success');
                }

                // Update the "Due Today" badge count
                const badge = document.querySelector('#reminders-title .badge-amber');
                if (badge) {
                  const currentCount = parseInt(badge.textContent) || 0;
                  const newCount = currentCount - 1;
                  if (newCount > 0) {
                    badge.textContent = newCount;
                  } else {
                    badge.remove();
                  }
                }
              }
            }

          } else {
            // Show error
            this.disabled = false;
            this.innerHTML = '✓ Done';
            if (window.showToast) {
              window.showToast(data.error || 'Failed to complete reminder', 'error');
            } else {
              alert(data.error || 'Failed to complete reminder');
            }
          }
        } catch (error) {
          // Network or other error
          this.disabled = false;
          this.innerHTML = '✓ Done';
          if (window.showToast) {
            window.showToast('Network error. Please try again.', 'error');
          } else {
            alert('Network error. Please try again.');
          }
        }
      });
    });

    // ========================================================================
    // WEATHER SUGGESTION HANDLERS
    // ========================================================================

    // Handle weather suggestion accept buttons
    const acceptButtons = document.querySelectorAll('.weather-accept-btn');
    acceptButtons.forEach(button => {
      button.addEventListener('click', async function(e) {
        e.preventDefault();

        const reminderId = this.dataset.reminderId;
        const days = parseInt(this.dataset.days || 0);
        const suggestionCard = this.closest('[data-reminder-id]') || this.closest('.flex');

        // Disable button and show loading state
        this.disabled = true;
        const originalText = this.innerHTML;
        this.innerHTML = '⏳ Applying...';

        try {
          // Call API to adjust reminder
          const response = await fetch(`/reminders/api/${reminderId}/adjust`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({ days: days })
          });

          const data = await response.json();

          if (data.success) {
            // Fade out and remove suggestion
            if (suggestionCard) {
              suggestionCard.style.opacity = '0';
              suggestionCard.style.transition = 'opacity 0.3s ease';

              setTimeout(() => {
                suggestionCard.remove();

                // Check if suggestions section is empty
                const suggestionsSection = document.querySelector('[aria-labelledby="suggestions-title"]');
                if (suggestionsSection) {
                  const remainingSuggestions = suggestionsSection.querySelectorAll('.flex.flex-col');
                  if (remainingSuggestions.length === 0) {
                    suggestionsSection.remove();
                  }
                }

                // Show success toast
                if (window.showToast) {
                  window.showToast('✓ Reminder adjusted based on weather', 'success');
                }

                // Reload to show updated reminder
                setTimeout(() => window.location.reload(), 500);
              }, 300);
            }
          } else {
            // Show error
            this.disabled = false;
            this.innerHTML = originalText;
            if (window.showToast) {
              window.showToast(data.error || 'Failed to adjust reminder', 'error');
            }
          }
        } catch (error) {
          // Network error
          this.disabled = false;
          this.innerHTML = originalText;
          if (window.showToast) {
            window.showToast('Network error. Please try again.', 'error');
          }
        }
      });
    });

    // Handle weather suggestion dismiss buttons
    const dismissButtons = document.querySelectorAll('.weather-dismiss-btn');
    dismissButtons.forEach(button => {
      button.addEventListener('click', function(e) {
        e.preventDefault();

        const suggestionCard = this.closest('[data-reminder-id]') || this.closest('.flex');

        if (suggestionCard) {
          // Fade out and remove suggestion
          suggestionCard.style.opacity = '0';
          suggestionCard.style.transition = 'opacity 0.3s ease';

          setTimeout(() => {
            suggestionCard.remove();

            // Check if suggestions section is empty
            const suggestionsSection = document.querySelector('[aria-labelledby="suggestions-title"]');
            if (suggestionsSection) {
              const remainingSuggestions = suggestionsSection.querySelectorAll('.flex.flex-col');
              if (remainingSuggestions.length === 0) {
                suggestionsSection.remove();
              }
            }

            if (window.showToast) {
              window.showToast('Suggestion dismissed', 'info');
            }
          }, 300);
        }
      });
    });

    // ========================================================================
    // "WHY?" EXPLANATION MODAL
    // ========================================================================

    // Show adjustment details modal
    window.showAdjustmentDetails = function(adjustment) {
      const modal = document.createElement('div');
      modal.className = 'fixed inset-0 bg-slate-900/50 dark:bg-slate-950/70 flex items-center justify-center z-50 p-4';
      modal.setAttribute('role', 'dialog');
      modal.setAttribute('aria-labelledby', 'modal-title');
      modal.setAttribute('aria-modal', 'true');

      const details = adjustment.details || {};

      // Build details HTML
      let detailsHTML = '<dl class="space-y-3 mt-4">';

      if (details.weather_condition) {
        detailsHTML += `
          <div>
            <dt class="text-sm font-semibold text-slate-700 dark:text-slate-300">Condition</dt>
            <dd class="text-sm text-slate-600 dark:text-slate-400 capitalize">${details.weather_condition.replace(/_/g, ' ')}</dd>
          </div>
        `;
      }

      if (details.precipitation_inches !== undefined) {
        detailsHTML += `
          <div>
            <dt class="text-sm font-semibold text-slate-700 dark:text-slate-300">Precipitation</dt>
            <dd class="text-sm text-slate-600 dark:text-slate-400">${details.precipitation_inches}" expected</dd>
          </div>
        `;
      }

      if (details.temp_min_f !== undefined) {
        detailsHTML += `
          <div>
            <dt class="text-sm font-semibold text-slate-700 dark:text-slate-300">Temperature Range</dt>
            <dd class="text-sm text-slate-600 dark:text-slate-400">${details.temp_min_f}°F - ${details.temp_max_f || 'N/A'}°F</dd>
          </div>
        `;
      }

      if (details.freeze_risk !== undefined) {
        detailsHTML += `
          <div>
            <dt class="text-sm font-semibold text-slate-700 dark:text-slate-300">Freeze Risk</dt>
            <dd class="text-sm text-slate-600 dark:text-slate-400">${details.freeze_risk ? 'Yes' : 'No'}</dd>
          </div>
        `;
      }

      if (details.light_factor !== undefined) {
        detailsHTML += `
          <div>
            <dt class="text-sm font-semibold text-slate-700 dark:text-slate-300">Light Adjustment</dt>
            <dd class="text-sm text-slate-600 dark:text-slate-400">${((details.light_factor - 1) * 100).toFixed(0)}% ${details.light_factor > 1 ? 'more' : 'less'} water needed</dd>
          </div>
        `;
      }

      detailsHTML += '</dl>';

      modal.innerHTML = `
        <div class="bg-white dark:bg-slate-800 rounded-xl shadow-2xl max-w-md w-full p-6 max-h-[90vh] overflow-y-auto">
          <div class="flex items-start justify-between mb-4">
            <div>
              <h3 id="modal-title" class="text-xl font-bold text-slate-900 dark:text-slate-100">
                Adjustment Details
              </h3>
              <p class="text-sm text-slate-600 dark:text-slate-400 mt-1">
                Why this reminder was adjusted
              </p>
            </div>
            <button
              onclick="this.closest('[role=dialog]').remove()"
              class="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors"
              aria-label="Close modal"
            >
              <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
              </svg>
            </button>
          </div>

          <div class="p-4 bg-cyan-50 dark:bg-cyan-900/20 border-l-4 border-cyan-400 dark:border-cyan-500 rounded-r mb-4">
            <p class="text-sm font-medium text-slate-700 dark:text-slate-300">
              ${adjustment.reason}
            </p>
          </div>

          ${detailsHTML}

          <div class="mt-6 flex justify-end gap-3">
            <button
              onclick="this.closest('[role=dialog]').remove()"
              class="btn btn-secondary"
            >
              Close
            </button>
          </div>
        </div>
      `;

      // Close on background click
      modal.addEventListener('click', function(e) {
        if (e.target === modal) {
          modal.remove();
        }
      });

      // Close on Escape key
      document.addEventListener('keydown', function escHandler(e) {
        if (e.key === 'Escape') {
          modal.remove();
          document.removeEventListener('keydown', escHandler);
        }
      });

      document.body.appendChild(modal);
    };
  });
})();
