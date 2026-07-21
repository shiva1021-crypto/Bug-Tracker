/* ==========================================================================
   Bug Tracker - shared script
   Plain JavaScript, no framework. Added to in later stages.
   ========================================================================== */

(function () {
  "use strict";

  /* ---------------------------------------------------- user menu dropdown */

  function initUserMenu() {
    var menu = document.querySelector("[data-user-menu]");
    if (!menu) return;

    var trigger = menu.querySelector("[data-user-menu-trigger]");
    var dropdown = menu.querySelector("[data-user-menu-dropdown]");
    if (!trigger || !dropdown) return;

    function close() {
      dropdown.hidden = true;
      trigger.setAttribute("aria-expanded", "false");
    }

    function open() {
      dropdown.hidden = false;
      trigger.setAttribute("aria-expanded", "true");
    }

    trigger.addEventListener("click", function (event) {
      event.stopPropagation();
      if (dropdown.hidden) { open(); } else { close(); }
    });

    // Click anywhere else, or press Escape, to dismiss.
    document.addEventListener("click", function (event) {
      if (!menu.contains(event.target)) close();
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") close();
    });
  }

  /* ------------------------------------------------------ sidebar toggle */

  function initSidebarToggle() {
    var toggle = document.querySelector("[data-sidebar-toggle]");
    var shell = document.querySelector("[data-app-shell]");
    if (!toggle || !shell) return;

    toggle.addEventListener("click", function () {
      var collapsed = shell.classList.toggle("sidebar-collapsed");
      toggle.setAttribute("aria-expanded", String(!collapsed));
    });
  }

  /* -------------------------------------------------- new project toggle */

  function initNewProjectToggle() {
    var toggle = document.querySelector("[data-new-project-toggle]");
    var form = document.querySelector("[data-new-project-form]");
    if (!toggle || !form) return;

    toggle.addEventListener("click", function () {
      form.hidden = !form.hidden;
      if (!form.hidden) {
        var firstField = form.querySelector("input, textarea");
        if (firstField) firstField.focus();
      }
    });
  }

  /* ------------------------------------------ register password matching */
  /* Convenience only - services/auth_service.py re-validates on the server. */

  function initRegisterForm() {
    var form = document.querySelector("[data-register-form]");
    if (!form) return;

    var password = form.querySelector("[data-password]");
    var confirm = form.querySelector("[data-confirm-password]");
    var error = form.querySelector("[data-password-error]");
    if (!password || !confirm || !error) return;

    function mismatched() {
      return confirm.value.length > 0 && password.value !== confirm.value;
    }

    function refresh() {
      var bad = mismatched();
      error.hidden = !bad;
      confirm.classList.toggle("input-invalid", bad);
    }

    password.addEventListener("input", refresh);
    confirm.addEventListener("input", refresh);

    form.addEventListener("submit", function (event) {
      if (password.value !== confirm.value) {
        event.preventDefault();
        error.hidden = false;
        confirm.classList.add("input-invalid");
        confirm.focus();
      }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initUserMenu();
    initSidebarToggle();
    initNewProjectToggle();
    initRegisterForm();
  });
})();
