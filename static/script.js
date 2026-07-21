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

  /* ------------------------------------------------- backlog (Stage 8) */

  function initNewSprintToggle() {
    var toggle = document.querySelector("[data-new-sprint-toggle]");
    var form = document.querySelector("[data-new-sprint-form]");
    if (!toggle || !form) return;

    toggle.addEventListener("click", function () {
      form.hidden = !form.hidden;
      if (!form.hidden) {
        var firstField = form.querySelector("input, textarea");
        if (firstField) firstField.focus();
        form.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
    });
  }

  /* A backlog row's "move to sprint" dropdown includes a "+ New Sprint"
     option (per the spec: "a dropdown to assign it into an existing
     sprint (or '+ New Sprint')"). Picking it should not submit the move
     form -- there is no sprint to move into yet -- it should instead
     reveal the same new-sprint form the top-of-page button does. */
  function initBacklogSprintSelects() {
    var selects = document.querySelectorAll("[data-backlog-sprint-select]");
    if (!selects.length) return;

    var newSprintForm = document.querySelector("[data-new-sprint-form]");

    selects.forEach(function (select) {
      select.addEventListener("change", function () {
        if (select.value !== "__new__") return;
        select.value = "";
        if (newSprintForm) {
          newSprintForm.hidden = false;
          newSprintForm.scrollIntoView({ behavior: "smooth", block: "nearest" });
          var firstField = newSprintForm.querySelector("input, textarea");
          if (firstField) firstField.focus();
        }
      });
    });
  }

  /* --------------------------------------------------- saved filters (Stage 8) */

  function initSaveFilterForm() {
    var form = document.querySelector("[data-save-filter-form]");
    var trigger = document.querySelector("[data-save-filter-trigger]");
    var nameField = document.querySelector("[data-save-filter-name]");
    if (!form || !trigger || !nameField) return;

    trigger.addEventListener("click", function () {
      var name = window.prompt("Name this filter:");
      if (!name) return;
      nameField.value = name;
      form.submit();
    });
  }

  /* ------------------------------------------------- Stage 9: versions page */

  function initNewVersionToggle() {
    var toggle = document.querySelector("[data-new-version-toggle]");
    var form = document.querySelector("[data-new-version-form]");
    if (!toggle || !form) return;

    toggle.addEventListener("click", function () {
      form.hidden = !form.hidden;
      if (!form.hidden) {
        var firstField = form.querySelector("input, select, textarea");
        if (firstField) firstField.focus();
      }
    });
  }

  /* ------------------------------------------------- Stage 9: fields page */

  function initNewFieldToggle() {
    var toggle = document.querySelector("[data-new-field-toggle]");
    var form = document.querySelector("[data-new-field-form]");
    if (!toggle || !form) return;

    toggle.addEventListener("click", function () {
      form.hidden = !form.hidden;
      if (!form.hidden) {
        var firstField = form.querySelector("input, select, textarea");
        if (firstField) firstField.focus();
      }
    });
  }

  function initFieldTypeOptionsToggle() {
    var typeSelect = document.querySelector("[data-field-type-select]");
    var optionsWrap = document.querySelector("[data-field-options-wrap]");
    if (!typeSelect || !optionsWrap) return;

    function refresh() {
      optionsWrap.hidden = typeSelect.value !== "dropdown";
    }

    typeSelect.addEventListener("change", refresh);
    refresh();
  }

  /* ------------------------------------------------- Stage 9: automation page */

  function initNewRuleToggle() {
    var toggle = document.querySelector("[data-new-rule-toggle]");
    var form = document.querySelector("[data-new-rule-form]");
    if (!toggle || !form) return;

    toggle.addEventListener("click", function () {
      form.hidden = !form.hidden;
      if (!form.hidden) {
        var firstField = form.querySelector("input, select, textarea");
        if (firstField) firstField.focus();
      }
    });
  }

  function initConditionRows() {
    var container = document.querySelector("[data-condition-rows]");
    var addButton = document.querySelector("[data-add-condition-row]");
    if (!container || !addButton) return;

    addButton.addEventListener("click", function () {
      var firstRow = container.querySelector("[data-condition-row]");
      if (!firstRow) return;
      var clone = firstRow.cloneNode(true);
      clone.querySelectorAll("input").forEach(function (input) { input.value = ""; });
      clone.querySelectorAll("select").forEach(function (select) { select.selectedIndex = 0; });
      container.appendChild(clone);
    });

    container.addEventListener("click", function (event) {
      if (!event.target.matches("[data-remove-condition-row]")) return;
      var rows = container.querySelectorAll("[data-condition-row]");
      if (rows.length <= 1) {
        // Keep at least one row -- just clear it, rather than removing the
        // only row a submitted rule could attach a condition to.
        var row = event.target.closest("[data-condition-row]");
        row.querySelectorAll("input").forEach(function (input) { input.value = ""; });
        row.querySelectorAll("select").forEach(function (select) { select.selectedIndex = 0; });
        return;
      }
      event.target.closest("[data-condition-row]").remove();
    });
  }

  function initActionTypeFields() {
    var select = document.querySelector("[data-action-type-select]");
    var fieldGroups = document.querySelectorAll("[data-action-field]");
    if (!select || !fieldGroups.length) return;

    function refresh() {
      fieldGroups.forEach(function (group) {
        group.hidden = group.getAttribute("data-action-field") !== select.value;
      });
    }

    select.addEventListener("change", refresh);
    refresh();
  }

  /* ------------------------------------------------- Stage 9: dynamic fields */
  /* Add-issue page only (edit page's project never changes, so its custom
     fields/fix-version options are rendered server-side once, at load
     time -- see routes/issue_routes.py::edit_issue). Reloads both the
     custom-fields list and the Fix Version dropdown via AJAX whenever the
     selected Project changes, per the spec's explicit instruction. */

  function customFieldInputHtml(field) {
    var id = "custom_field_" + field.id;
    var requiredAttr = field.required ? " required" : "";
    var label = field.name + (field.required ? " *" : "");

    if (field.field_type === "dropdown") {
      var options = "<option value=\"\">Select…</option>";
      (field.options || []).forEach(function (option) {
        options += "<option value=\"" + option + "\">" + option + "</option>";
      });
      return (
        "<div class=\"field\"><label class=\"label\" for=\"" + id + "\">" + label + "</label>" +
        "<select class=\"input\" id=\"" + id + "\" name=\"" + id + "\"" + requiredAttr + ">" + options + "</select></div>"
      );
    }
    if (field.field_type === "checkbox") {
      return (
        "<div class=\"field\"><label class=\"checkbox-line\">" +
        "<input type=\"checkbox\" id=\"" + id + "\" name=\"" + id + "\"> " + label +
        "</label></div>"
      );
    }
    var inputType = field.field_type === "number" ? "number" : (field.field_type === "date" ? "date" : "text");
    return (
      "<div class=\"field\"><label class=\"label\" for=\"" + id + "\">" + label + "</label>" +
      "<input class=\"input\" type=\"" + inputType + "\" id=\"" + id + "\" name=\"" + id + "\"" + requiredAttr + "></div>"
    );
  }

  function loadCustomFields(projectId) {
    var container = document.querySelector("[data-custom-fields-container]");
    var list = document.querySelector("[data-custom-fields-list]");
    if (!container || !list) return;

    if (!projectId) {
      container.hidden = true;
      list.innerHTML = "";
      return;
    }

    fetch("/api/fields?project_id=" + encodeURIComponent(projectId), { credentials: "same-origin" })
      .then(function (response) { return response.json(); })
      .then(function (fields) {
        list.innerHTML = fields.map(customFieldInputHtml).join("");
        container.hidden = fields.length === 0;
      })
      .catch(function () {
        container.hidden = true;
        list.innerHTML = "";
      });
  }

  function loadFixVersions(projectId) {
    var select = document.querySelector("[data-fix-version-select]");
    if (!select) return;

    var preselected = select.getAttribute("data-selected") || "";

    if (!projectId) {
      select.innerHTML = "<option value=\"\">No fix version</option>";
      return;
    }

    fetch("/api/versions?project_id=" + encodeURIComponent(projectId), { credentials: "same-origin" })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        var versions = data.versions || [];
        var html = "<option value=\"\">No fix version</option>";
        versions.forEach(function (version) {
          var selected = String(version.id) === String(preselected) ? " selected" : "";
          html += "<option value=\"" + version.id + "\"" + selected + ">" + version.name + "</option>";
        });
        select.innerHTML = html;
      })
      .catch(function () {
        select.innerHTML = "<option value=\"\">No fix version</option>";
      });
  }

  function initDynamicFieldsAndVersions() {
    var projectSelect = document.querySelector("[data-project-select]");
    var hasCustomFields = document.querySelector("[data-custom-fields-container]");
    var hasFixVersion = document.querySelector("[data-fix-version-select]");
    if (!projectSelect || (!hasCustomFields && !hasFixVersion)) return;

    function refresh() {
      var projectId = projectSelect.value;
      loadCustomFields(projectId);
      loadFixVersions(projectId);
    }

    projectSelect.addEventListener("change", refresh);
    if (projectSelect.value) refresh();
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
    initNewSprintToggle();
    initBacklogSprintSelects();
    initSaveFilterForm();
    initRegisterForm();
    initNewFieldToggle();
    initFieldTypeOptionsToggle();
    initNewVersionToggle();
    initNewRuleToggle();
    initConditionRows();
    initActionTypeFields();
    initDynamicFieldsAndVersions();
  });
})();
