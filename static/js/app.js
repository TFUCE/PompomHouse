// Click handlers for card tabs, password toggles, and confirm buttons.
document.addEventListener('click', function (event) {
  const tabButton = event.target.closest('[data-card-tab]');
  if (tabButton) {
    const targetId = tabButton.getAttribute('data-card-target');
    const wrapper = document.getElementById(targetId);
    if (!wrapper) return;

    const tabName = tabButton.getAttribute('data-card-tab');
    wrapper.querySelectorAll('[data-card-panel]').forEach(function (panel) {
      const active = panel.getAttribute('data-card-panel') === tabName;
      panel.hidden = !active;
      panel.classList.toggle('active', active);
    });

    const tabButtons = wrapper.closest('.listing-card').querySelectorAll('[data-card-tab]');
    tabButtons.forEach(function (button) {
      const active = button === tabButton;
      button.classList.toggle('active', active);
      button.setAttribute('aria-selected', String(active));
      if (active) {
        button.removeAttribute('tabindex');
      } else {
        button.setAttribute('tabindex', '-1');
      }
    });

    tabButton.focus();
    return;
  }

  const passwordToggle = event.target.closest('[data-password-toggle]');
  if (passwordToggle) {
    const input = document.getElementById(passwordToggle.getAttribute('data-password-toggle'));
    if (!input) return;

    const showing = input.type === 'text';
    input.type = showing ? 'password' : 'text';
    passwordToggle.setAttribute('aria-pressed', String(!showing));
    passwordToggle.textContent = showing ? '👁' : '🙈';
    return;
  }

  const confirmButton = event.target.closest('[data-confirm-message]');
  if (confirmButton && !window.confirm(confirmButton.getAttribute('data-confirm-message'))) {
    event.preventDefault();
  }
});

// Arrow keys switch listing tabs for keyboard users.
document.addEventListener('keydown', function (event) {
  const current = event.target.closest('[data-card-tab]');
  if (!current || !['ArrowLeft', 'ArrowRight'].includes(event.key)) return;

  const tabs = Array.from(current.closest('[role="tablist"]').querySelectorAll('[data-card-tab]'));
  const index = tabs.indexOf(current);
  if (index === -1) return;

  event.preventDefault();
  const nextIndex = event.key === 'ArrowRight' ? (index + 1) % tabs.length : (index - 1 + tabs.length) % tabs.length;
  tabs[nextIndex].click();
});

// Small setup work once the page is ready.
document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('input[type="password"]').forEach(function (input, index) {
    if (input.dataset.passwordEnhanced === '1') return;

    if (!input.id) {
      input.id = 'password-field-' + index;
    }

    const wrapper = document.createElement('div');
    wrapper.className = 'password-input-wrap';
    input.parentNode.insertBefore(wrapper, input);
    wrapper.appendChild(input);

    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'password-toggle';
    button.setAttribute('data-password-toggle', input.id);
    button.setAttribute('aria-label', 'Show or hide password');
    button.setAttribute('aria-pressed', 'false');
    button.textContent = '👁';
    wrapper.appendChild(button);

    input.dataset.passwordEnhanced = '1';
  });

  // Show the bedroom field only when the landlord is renting separate rooms.
  const listingModeField = document.getElementById('id_listing_mode');
  const bedroomsRow = document.querySelector('.room-count-row');
  if (!listingModeField || !bedroomsRow) return;

  function toggleBedroomsField() {
    const show = listingModeField.value === 'rooms';
    bedroomsRow.classList.toggle('is-hidden', !show);

    const input = bedroomsRow.querySelector('input, select, textarea');
    if (!input) return;

    input.disabled = !show;
    if (!show) {
      input.value = '';
    }
  }

  listingModeField.addEventListener('change', toggleBedroomsField);
  toggleBedroomsField();
});
