/**
 * Guides Index Page — Search & Filter
 * Client-side filtering of guide cards by text search and category chips.
 */

(function() {
  'use strict';

  const searchInput = document.getElementById('guides-search');
  if (!searchInput) return;

  const cards = document.querySelectorAll('.guide-card');
  const chips = document.querySelectorAll('.guide-chip');
  const resultsCount = document.getElementById('guides-results-count');
  const noResults = document.getElementById('guides-no-results');
  const clearBtn = document.getElementById('guides-clear-btn');
  const clearAllBtn = document.getElementById('guides-clear-all');
  const sections = document.querySelectorAll('[data-guide-section]');
  const subgroups = document.querySelectorAll('.landing-subgroup');
  const totalCards = cards.length;

  let activeTag = 'all';
  let searchQuery = '';
  let debounceTimer = null;

  // Chip styling classes
  const activeClasses = ['bg-emerald-100', 'dark:bg-emerald-900/30', 'text-emerald-700', 'dark:text-emerald-300', 'border-emerald-300', 'dark:border-emerald-600'];
  const inactiveClasses = ['bg-slate-100', 'dark:bg-slate-800', 'text-slate-600', 'dark:text-slate-400', 'border-slate-200', 'dark:border-slate-700'];

  function applyFilters() {
    let visibleCount = 0;
    const query = searchQuery.toLowerCase().trim();

    cards.forEach(function(card) {
      const searchText = card.getAttribute('data-search') || '';
      const tagList = (card.getAttribute('data-tags') || '').split(',');
      const matchesTag = activeTag === 'all' || tagList.indexOf(activeTag) !== -1;
      const matchesSearch = !query || searchText.indexOf(query) !== -1;

      if (matchesTag && matchesSearch) {
        card.classList.remove('hidden');
        visibleCount++;
      } else {
        card.classList.add('hidden');
      }
    });

    // Update results count
    if (resultsCount) {
      resultsCount.textContent = 'Showing ' + visibleCount + ' of ' + totalCards + ' results';
    }

    // Toggle no-results message
    if (noResults) {
      noResults.classList.toggle('hidden', visibleCount > 0);
    }

    // Show/hide clear button in search input
    if (clearBtn) {
      clearBtn.classList.toggle('hidden', !searchQuery);
    }

    updateSectionVisibility();
    updateURL();
  }

  function updateSectionVisibility() {
    sections.forEach(function(section) {
      const visible = section.querySelectorAll('.guide-card:not(.hidden)');
      section.classList.toggle('hidden', visible.length === 0);
    });

    subgroups.forEach(function(group) {
      const visible = group.querySelectorAll('.guide-card:not(.hidden)');
      group.classList.toggle('hidden', visible.length === 0);
    });
  }

  function setActiveChip(tag) {
    activeTag = tag;
    chips.forEach(function(chip) {
      const isActive = chip.getAttribute('data-tag') === tag;
      chip.setAttribute('aria-pressed', isActive ? 'true' : 'false');

      if (isActive) {
        inactiveClasses.forEach(function(cls) { chip.classList.remove(cls); });
        activeClasses.forEach(function(cls) { chip.classList.add(cls); });
      } else {
        activeClasses.forEach(function(cls) { chip.classList.remove(cls); });
        inactiveClasses.forEach(function(cls) { chip.classList.add(cls); });
      }
    });
  }

  function resetAll() {
    searchInput.value = '';
    searchQuery = '';
    setActiveChip('all');
    applyFilters();
    searchInput.focus();
  }

  // Search input (debounced)
  searchInput.addEventListener('input', function() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(function() {
      searchQuery = searchInput.value;
      applyFilters();
    }, 250);
  });

  // Allow clearing with Escape key
  searchInput.addEventListener('keydown', function(e) {
    if (e.key === 'Escape' && (searchQuery || activeTag !== 'all')) {
      e.preventDefault();
      resetAll();
    }
  });

  // Chip click handlers
  chips.forEach(function(chip) {
    chip.addEventListener('click', function() {
      setActiveChip(this.getAttribute('data-tag'));
      applyFilters();
    });
  });

  // Clear buttons
  if (clearBtn) clearBtn.addEventListener('click', resetAll);
  if (clearAllBtn) clearAllBtn.addEventListener('click', resetAll);

  // URL state (shareable links)
  function updateURL() {
    const params = new URLSearchParams();
    if (searchQuery) params.set('q', searchQuery);
    if (activeTag !== 'all') params.set('tag', activeTag);
    const qs = params.toString();
    const newURL = window.location.pathname + (qs ? '?' + qs : '');
    history.replaceState(null, '', newURL);
  }

  function readURL() {
    const params = new URLSearchParams(window.location.search);
    const q = params.get('q');
    const tag = params.get('tag');
    if (q) {
      searchInput.value = q;
      searchQuery = q;
    }
    if (tag) {
      var validTags = Array.from(chips).map(function(c) { return c.getAttribute('data-tag'); });
      if (validTags.indexOf(tag) !== -1) {
        setActiveChip(tag);
      }
    }
    if (q || tag) applyFilters();
  }

  readURL();
})();
