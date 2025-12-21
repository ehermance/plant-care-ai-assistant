/**
 * Care Assistant Page Functionality
 * Handles scroll-to-answer, preset chips, plant selection, and carousel.
 */

(function() {
  'use strict';

  // Scroll to answer box when page loads with an answer
  const answerBox = document.getElementById('answer-box');
  const hasAnswer = answerBox && answerBox.querySelector('.prewrap');
  if (hasAnswer) {
    // Small delay to ensure page layout is complete
    setTimeout(function() {
      // Get the sticky header height to offset the scroll position
      const header = document.querySelector('header.sticky');
      const headerHeight = header ? header.offsetHeight : 0;
      const padding = 16; // Extra padding for visual breathing room

      // Calculate scroll position: element top minus header and padding
      const elementTop = answerBox.getBoundingClientRect().top + window.scrollY;
      const scrollTarget = elementTop - headerHeight - padding;

      window.scrollTo({
        top: scrollTarget,
        behavior: 'smooth'
      });
    }, 100);
  }

  // Helper function to scroll to form with header offset
  function scrollToForm() {
    const askForm = document.getElementById('ask-form');
    const formCard = askForm ? askForm.closest('.card') : null;
    if (formCard) {
      const header = document.querySelector('header.sticky');
      const headerHeight = header ? header.offsetHeight : 0;
      const padding = 16;
      const elementTop = formCard.getBoundingClientRect().top + window.scrollY;
      const scrollTarget = elementTop - headerHeight - padding;
      window.scrollTo({ top: scrollTarget, behavior: 'smooth' });
    }
  }

  // Preset chip click handlers (unauthenticated users only)
  document.querySelectorAll('.preset-chip').forEach(function(chip) {
    chip.addEventListener('click', function(e) {
      e.preventDefault();

      // Get data attributes
      const plant = this.dataset.plant;
      const question = this.dataset.question;
      const context = this.dataset.context;

      // Get form fields
      const plantField = document.getElementById('plant');
      const questionField = document.getElementById('question');
      const contextField = document.getElementById('care_context');

      // Always replace all fields with preset values
      if (plant && plantField) {
        plantField.value = plant;
      }

      if (question && questionField) {
        questionField.value = question;
      }

      if (context && contextField) {
        contextField.value = context;
      }

      // Scroll to form so user can see what was filled
      scrollToForm();

      // Focus the question field (most likely next action)
      if (questionField) {
        questionField.focus();
      }
    });
  });

  // Plant selection click handlers (authenticated users)
  document.querySelectorAll('.plant-select-btn').forEach(function(btn) {
    btn.addEventListener('click', function(e) {
      e.preventDefault();

      // Get data attributes
      const plantId = this.dataset.plantId;
      const plantName = this.dataset.plantName;
      const plantLocation = this.dataset.plantLocation || 'indoor_potted';

      // Get form fields
      const plantField = document.getElementById('plant');
      const contextField = document.getElementById('care_context');
      const selectedPlantIdField = document.getElementById('selected_plant_id');
      const questionField = document.getElementById('question');

      // Fill plant name (always overwrite to ensure consistency)
      if (plantName && plantField) {
        plantField.value = plantName;
      }

      // Fill care context from plant's location
      if (plantLocation && contextField) {
        contextField.value = plantLocation;
      }

      // Store selected plant ID for AI context
      if (plantId && selectedPlantIdField) {
        selectedPlantIdField.value = plantId;
      }

      // Visual feedback: highlight selected plant
      document.querySelectorAll('.plant-select-btn').forEach(function(b) {
        b.classList.remove('ring-2', 'ring-emerald-500', 'dark:ring-emerald-400');
      });
      this.classList.add('ring-2', 'ring-emerald-500', 'dark:ring-emerald-400');

      // Scroll to form so user can see what was filled
      scrollToForm();

      // Focus the question field (most likely next action)
      if (questionField) {
        questionField.focus();
      }
    });
  });

  // Plant carousel scroll functionality with gradient indicators
  (function() {
    const scrollContainer = document.getElementById('plants-scroll-container');
    const scrollLeftBtn = document.getElementById('scroll-left-btn');
    const scrollRightBtn = document.getElementById('scroll-right-btn');
    const gradientLeft = document.getElementById('gradient-left');
    const gradientRight = document.getElementById('gradient-right');

    // Only run if elements exist (user has plants)
    if (!scrollContainer || !scrollLeftBtn || !scrollRightBtn) {
      return;
    }

    /**
     * Update scroll button states and gradient visibility
     * based on current scroll position.
     */
    function updateScrollState() {
      const scrollLeft = scrollContainer.scrollLeft;
      const scrollWidth = scrollContainer.scrollWidth;
      const clientWidth = scrollContainer.clientWidth;
      const maxScroll = scrollWidth - clientWidth;

      // Update left button and gradient
      const isAtStart = scrollLeft <= 1; // 1px threshold for rounding
      scrollLeftBtn.disabled = isAtStart;
      if (gradientLeft) {
        gradientLeft.style.opacity = isAtStart ? '0' : '1';
      }

      // Update right button and gradient
      const isAtEnd = scrollLeft >= maxScroll - 1; // 1px threshold for rounding
      scrollRightBtn.disabled = isAtEnd;
      if (gradientRight) {
        gradientRight.style.opacity = isAtEnd ? '0' : '1';
      }

      // Update ARIA labels for accessibility
      scrollLeftBtn.setAttribute('aria-disabled', isAtStart ? 'true' : 'false');
      scrollRightBtn.setAttribute('aria-disabled', isAtEnd ? 'true' : 'false');
    }

    /**
     * Scroll the carousel by approximately one plant width.
     * @param {string} direction - 'left' or 'right'
     */
    function scrollCarousel(direction) {
      const plantWidth = 112 + 12; // w-28 (112px) + gap-3 (12px)
      const scrollAmount = plantWidth * 2; // Scroll 2 plants at a time
      const currentScroll = scrollContainer.scrollLeft;
      const targetScroll = direction === 'left'
        ? currentScroll - scrollAmount
        : currentScroll + scrollAmount;

      scrollContainer.scrollTo({
        left: targetScroll,
        behavior: 'smooth'
      });
    }

    // Event listeners for scroll buttons
    scrollLeftBtn.addEventListener('click', () => scrollCarousel('left'));
    scrollRightBtn.addEventListener('click', () => scrollCarousel('right'));

    // Update state on scroll
    scrollContainer.addEventListener('scroll', updateScrollState);

    // Update state on window resize
    window.addEventListener('resize', updateScrollState);

    // Initialize state on page load
    updateScrollState();

    // Re-check after images load (they might affect scrollWidth)
    window.addEventListener('load', () => {
      setTimeout(updateScrollState, 100);
    });
  })();
})();
