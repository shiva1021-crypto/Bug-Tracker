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

  /* ------------------------------------------------- issue parent filter */
  /* Mirrors services/issue_service.py::VALID_PARENT_TYPES_FOR_CHILD -- keep
     the two in sync if the hierarchy rule ever changes. Convenience only:
     the server re-validates the chosen parent (type, project, cycles)
     regardless of what this filter allowed onto the page. */

  function initParentFilter() {
    var dataEl = document.getElementById("parent-candidates-data");
    var projectSelect = document.querySelector("[data-project-select]");
    var typeSelect = document.querySelector("[data-issue-type-select]");
    var parentSelect = document.querySelector("[data-parent-select]");
    if (!dataEl || !parentSelect) return;

    var candidates;
    try {
      candidates = JSON.parse(dataEl.textContent);
    } catch (e) {
      candidates = [];
    }

    var validParentTypes = {
      Epic: [],
      Bug: [],
      Story: ["Epic"],
      Task: ["Epic"],
      Subtask: ["Story"]
    };

    var preselected = parentSelect.getAttribute("data-selected") || "";

    function refresh() {
      var projectId = projectSelect ? projectSelect.value : "";
      var issueType = typeSelect ? typeSelect.value : "";
      var allowedParentTypes = validParentTypes[issueType] || [];

      parentSelect.innerHTML = "";
      var noneOption = document.createElement("option");
      noneOption.value = "";
      noneOption.textContent = "No parent";
      parentSelect.appendChild(noneOption);

      if (!projectId || allowedParentTypes.length === 0) return;

      candidates
        .filter(function (c) {
          return String(c.project_id) === String(projectId) &&
                 allowedParentTypes.indexOf(c.issue_type) !== -1;
        })
        .forEach(function (c) {
          var option = document.createElement("option");
          option.value = c.id;
          option.textContent = c.issue_key + " — " + c.title;
          if (String(c.id) === String(preselected)) option.selected = true;
          parentSelect.appendChild(option);
        });
    }

    if (projectSelect) projectSelect.addEventListener("change", refresh);
    if (typeSelect) typeSelect.addEventListener("change", refresh);
    refresh();
  }

  /* ---------------------------------------------------- screenshot preview */

  function initScreenshotPreview() {
    var input = document.querySelector("[data-screenshot-input]");
    var preview = document.querySelector("[data-screenshot-preview]");
    if (!input || !preview) return;

    input.addEventListener("change", function () {
      var file = input.files && input.files[0];
      if (!file) {
        preview.hidden = true;
        preview.removeAttribute("src");
        return;
      }
      preview.src = URL.createObjectURL(file);
      preview.hidden = false;
    });
  }

  /* -------------------------------------------------------- history panel */

  function initHistoryToggle() {
    var toggle = document.querySelector("[data-history-toggle]");
    var list = document.querySelector("[data-history-list]");
    if (!toggle || !list) return;

    toggle.addEventListener("click", function () {
      list.hidden = !list.hidden;
    });
  }

  /* ------------------------------------------------------------ board (Stage 7) */

  function boardShowToast(message) {
    var toast = document.querySelector("[data-board-toast]");
    if (!toast) return;
    toast.textContent = message;
    toast.hidden = false;
    window.clearTimeout(toast._hideTimer);
    toast._hideTimer = window.setTimeout(function () {
      toast.hidden = true;
    }, 4000);
  }

  function boardUpdateColumnCounts() {
    document.querySelectorAll("[data-board-column-list]").forEach(function (list) {
      var cards = list.querySelectorAll(".board-card");
      var column = list.closest(".board-column");
      var countEl = column && column.querySelector("[data-column-count]");
      if (countEl) countEl.textContent = String(cards.length);

      var placeholder = list.querySelector("[data-empty-placeholder]");
      if (cards.length === 0 && !placeholder) {
        var li = document.createElement("li");
        li.className = "board-empty-placeholder";
        li.setAttribute("data-empty-placeholder", "");
        li.textContent = "No issues";
        list.appendChild(li);
      } else if (cards.length > 0 && placeholder) {
        placeholder.remove();
      }
    });
  }

  function boardPostMove(issueId, status) {
    var container = document.querySelector("[data-board-columns]");
    var url = container.getAttribute("data-move-url");
    var csrfToken = container.getAttribute("data-csrf-token");

    var formData = new FormData();
    formData.append("issue_id", issueId);
    formData.append("status", status);
    formData.append("csrf_token", csrfToken);

    return fetch(url, { method: "POST", body: formData, credentials: "same-origin" })
      .then(function (response) { return response.json(); })
      .catch(function () { return { ok: false, error: "Network error -- could not reach the server." }; });
  }

  function initBoardDragAndDrop() {
    var container = document.querySelector("[data-board-columns]");
    if (!container) return;

    var draggedCard = null;

    container.addEventListener("dragstart", function (event) {
      var card = event.target.closest(".board-card");
      if (!card) return;
      draggedCard = card;
      card.classList.add("board-card-dragging");
      event.dataTransfer.effectAllowed = "move";
      // Firefox requires setData to be called for drag to start at all.
      event.dataTransfer.setData("text/plain", card.getAttribute("data-issue-id") || "");
    });

    container.addEventListener("dragend", function (event) {
      var card = event.target.closest(".board-card");
      if (card) card.classList.remove("board-card-dragging");
      draggedCard = null;
      document.querySelectorAll(".board-column-list-hover").forEach(function (list) {
        list.classList.remove("board-column-list-hover");
      });
    });

    container.querySelectorAll("[data-board-column-list]").forEach(function (list) {
      list.addEventListener("dragover", function (event) {
        event.preventDefault();
        event.dataTransfer.dropEffect = "move";
        list.classList.add("board-column-list-hover");
      });

      list.addEventListener("dragleave", function (event) {
        if (event.target === list) list.classList.remove("board-column-list-hover");
      });

      list.addEventListener("drop", function (event) {
        event.preventDefault();
        list.classList.remove("board-column-list-hover");
        if (!draggedCard) return;

        var sourceList = draggedCard.parentElement;
        var newStatus = list.getAttribute("data-status");
        var oldStatus = sourceList.getAttribute("data-status");
        if (sourceList === list || newStatus === oldStatus) return;

        var issueId = draggedCard.getAttribute("data-issue-id");

        // Optimistic move -- the server is still the authority; this just
        // avoids a round-trip before the card visibly moves.
        list.appendChild(draggedCard);
        boardUpdateColumnCounts();

        boardPostMove(issueId, newStatus).then(function (result) {
          if (!result.ok) {
            // Not authorized (or some other server-side rejection): snap
            // the card back to its original column exactly as the spec
            // describes, and surface the server's error message.
            sourceList.appendChild(draggedCard);
            draggedCard.classList.add("board-card-returning");
            window.setTimeout(function () {
              draggedCard.classList.remove("board-card-returning");
            }, 250);
            boardUpdateColumnCounts();
            boardShowToast(result.error || "You do not have permission to make that change.");
          }
        });
      });
    });
  }

  function initBoardLoadMore() {
    document.querySelectorAll("[data-load-more]").forEach(function (button) {
      button.addEventListener("click", function () {
        var column = button.closest(".board-column");
        if (!column) return;
        column.querySelectorAll(".board-card[hidden]").forEach(function (card) {
          card.hidden = false;
        });
        button.remove();
      });
    });
  }

  function initBoardAssigneeFilter() {
    var row = document.querySelector("[data-assignee-filter-row]");
    if (!row) return;

    row.querySelectorAll("[data-assignee-filter-trigger]").forEach(function (button) {
      button.addEventListener("click", function () {
        var alreadyActive = button.classList.contains("board-assignee-avatar-active");
        var assigneeId = button.getAttribute("data-assignee-id");

        row.querySelectorAll("[data-assignee-filter-trigger]").forEach(function (b) {
          b.classList.remove("board-assignee-avatar-active");
        });
        document.querySelectorAll(".board-card").forEach(function (card) {
          card.classList.remove("board-card-filtered-out");
        });

        if (!alreadyActive) {
          button.classList.add("board-assignee-avatar-active");
          document.querySelectorAll(".board-card").forEach(function (card) {
            if (card.getAttribute("data-assignee-id") !== assigneeId) {
              card.classList.add("board-card-filtered-out");
            }
          });
        }
      });
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
    initParentFilter();
    initScreenshotPreview();
    initHistoryToggle();
    initBoardDragAndDrop();
    initBoardLoadMore();
    initBoardAssigneeFilter();
    initRegisterForm();
  });
})();
