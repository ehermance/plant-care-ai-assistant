/**
 * Dashboard Quick Complete Functionality
 * Handles AJAX completion of reminders from the dashboard view
 */

(function() {
  'use strict';

  document.addEventListener('DOMContentLoaded', function() {
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
              // Check if list is empty
              const remindersList = document.getElementById('dashboard-reminders-list');
              if (remindersList && remindersList.children.length === 0) {
                // Reload page to update stats and show empty state
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
  });
})();
