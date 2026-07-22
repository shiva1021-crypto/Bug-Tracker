/*
 * Copied verbatim from project-spec/reference-ui/static/js/script.js, per the
 * project's UI Reference convention (00-README.md), with exactly one
 * adaptation: the drag-and-drop board update reads the page's hidden CSRF
 * field by name, and this app's field is named "csrf_token" (see
 * utils/security.py::CSRF_FORM_FIELD), not "_csrf_token" as in the reference
 * app. That selector below is changed to match; nothing else is touched.
 */
document.addEventListener("DOMContentLoaded", function () {
    const navToggle = document.querySelector(".nav-toggle");
    const jiraSidebar = document.getElementById("jiraSidebar");
    const sidebarCollapseBtn = document.querySelector(".sidebar-collapse-btn");
    const themeToggles = document.querySelectorAll(".theme-toggle");
    const printReport = document.querySelector(".print-report");

    // 1. Restore dark/light theme
    if (localStorage.getItem("theme") === "dark") {
        document.body.classList.add("dark-mode");
    }

    // Restore Sidebar Collapse state
    if (jiraSidebar) {
        if (localStorage.getItem("sidebarState") === "collapsed") {
            jiraSidebar.classList.add("collapsed");
        }

        if (sidebarCollapseBtn) {
            sidebarCollapseBtn.addEventListener("click", function () {
                jiraSidebar.classList.toggle("collapsed");
                const isCollapsed = jiraSidebar.classList.contains("collapsed");
                localStorage.setItem("sidebarState", isCollapsed ? "collapsed" : "expanded");
            });
        }
    }

    // Mobile Navigation Sidebar toggle
    if (navToggle && jiraSidebar) {
        navToggle.addEventListener("click", function () {
            jiraSidebar.classList.toggle("open-mobile");
        });
    }

    // Theme Toggle
    themeToggles.forEach(toggle => {
        toggle.addEventListener("click", function (e) {
            e.preventDefault();
            document.body.classList.toggle("dark-mode");
            localStorage.setItem("theme", document.body.classList.contains("dark-mode") ? "dark" : "light");
            Toast.show(`Switched to ${document.body.classList.contains("dark-mode") ? "Dark" : "Light"} mode`, "success");
        });
    });

    // Print functionality
    if (printReport) {
        printReport.addEventListener("click", function () {
            window.print();
        });
    }

    // 2. Toast Notification system
    const Toast = {
        init() {
            if (!document.querySelector(".toast-container")) {
                const container = document.createElement("div");
                container.className = "toast-container";
                document.body.appendChild(container);
            }
        },
        show(message, type = "success") {
            this.init();
            const container = document.querySelector(".toast-container");
            const toast = document.createElement("div");
            toast.className = `toast ${type}`;
            toast.innerHTML = `
                <span>${message}</span>
                <button class="toast-close" aria-label="Close toast">&times;</button>
            `;
            container.appendChild(toast);

            const closeBtn = toast.querySelector(".toast-close");
            closeBtn.addEventListener("click", () => {
                toast.style.opacity = "0";
                toast.style.transform = "translateY(10px)";
                setTimeout(() => toast.remove(), 200);
            });

            setTimeout(() => {
                if (toast.parentNode) {
                    toast.style.opacity = "0";
                    toast.style.transform = "translateY(10px)";
                    setTimeout(() => toast.remove(), 200);
                }
            }, 4000);
        }
    };
    window.Toast = Toast; // Make global

    // 3. Client-side Form Validation
    document.querySelectorAll("form:not(.ajax-comment-form):not(.ajax-watch-form):not(.ajax-assign-form)").forEach(function (form) {
        form.addEventListener("submit", function (event) {
            let valid = true;

            form.querySelectorAll("[required]").forEach(function (field) {
                if (!field.value.trim()) {
                    valid = false;
                    field.classList.add("field-error");
                } else {
                    field.classList.remove("field-error");
                }
            });

            if (!valid) {
                event.preventDefault();
                Toast.show("Please fill in all required fields.", "error");
            }
        });
    });

    // 4. Kanban Board Drag & Drop Interactivity
    const cards = document.querySelectorAll(".kanban-card");
    const columns = document.querySelectorAll(".kanban-column");

    if (cards.length > 0 && columns.length > 0) {
        let draggedCard = null;
        let sourceColumn = null;

        cards.forEach(card => {
            if (card.getAttribute("data-can-move") !== "true") return;
            card.setAttribute("draggable", "true");

            card.addEventListener("dragstart", function (e) {
                draggedCard = card;
                sourceColumn = card.closest(".kanban-column");
                card.classList.add("dragging");
                e.dataTransfer.effectAllowed = "move";
            });

            card.addEventListener("dragend", function () {
                card.classList.remove("dragging");
                draggedCard = null;
                sourceColumn = null;
                columns.forEach(col => col.classList.remove("drag-over"));
            });
        });

        columns.forEach(column => {
            column.addEventListener("dragover", function (e) {
                e.preventDefault();
                e.dataTransfer.dropEffect = "move";
                column.classList.add("drag-over");
            });

            column.addEventListener("dragleave", function () {
                column.classList.remove("drag-over");
            });

            column.addEventListener("drop", function (e) {
                e.preventDefault();
                column.classList.remove("drag-over");

                if (!draggedCard) return;

                const targetColumn = column;
                const destCardsContainer = targetColumn.querySelector(".kanban-cards");
                const newStatus = targetColumn.getAttribute("data-status");
                const originalStatus = sourceColumn.getAttribute("data-status");

                if (newStatus === originalStatus) return;

                // Move visual card element
                destCardsContainer.appendChild(draggedCard);

                // Recalculate columns counts
                updateColumnCardCounts();

                // Find CSRF token inside page
                const csrfInput = document.querySelector('input[name="csrf_token"]');
                const csrfToken = csrfInput ? csrfInput.value : "";
                const updateUrl = draggedCard.getAttribute("data-update-url");
                const issueKey = draggedCard.getAttribute("data-key");

                // Prepare FormData for the update request
                const formData = new FormData();
                formData.append("issue_id", draggedCard.getAttribute("data-id"));
                formData.append("status", newStatus);
                formData.append("csrf_token", csrfToken);
                formData.append("return_to", "board");

                // Perform live asynchronous update
                fetch(updateUrl, {
                    method: "POST",
                    body: formData,
                    headers: {
                        "X-Requested-With": "XMLHttpRequest"
                    }
                })
                .then(async response => {
                    const payload = await response.json().catch(() => ({}));
                    if (!response.ok || response.redirected || payload.ok !== true) {
                        throw new Error(payload.error || "Status update was rejected");
                    }
                    Toast.show(payload.message || `Successfully moved ${issueKey} to ${newStatus}`, "success");
                })
                .catch(error => {
                    // Revert visual elements
                    sourceColumn.querySelector(".kanban-cards").appendChild(draggedCard);
                    updateColumnCardCounts();
                    Toast.show(error.message || `Failed to move ${issueKey}.`, "error");
                });
            });
        });

        function updateColumnCardCounts() {
            columns.forEach(col => {
                const countBadge = col.querySelector(".kanban-column-count");
                const cardsCount = col.querySelectorAll(".kanban-card").length;
                if (countBadge) {
                    countBadge.textContent = cardsCount;
                }
            });
        }
    }

    // 5. Issues Directory Real-time Live Filter
    const searchInput = document.querySelector('input[type="search"][name="q"]');
    const tableBody = document.querySelector(".panel table tbody");

    if (searchInput && tableBody) {
        searchInput.addEventListener("input", function () {
            const query = searchInput.value.toLowerCase().trim();
            const rows = tableBody.querySelectorAll("tr:not(.empty)");

            let visibleCount = 0;
            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                if (text.includes(query)) {
                    row.style.display = "";
                    visibleCount++;
                } else {
                    row.style.display = "none";
                }
            });

            // Handle empty state row
            let emptyRow = tableBody.querySelector(".empty-filter-row");
            if (visibleCount === 0 && rows.length > 0) {
                if (!emptyRow) {
                    emptyRow = document.createElement("tr");
                    emptyRow.className = "empty-filter-row";
                    emptyRow.innerHTML = `<td colspan="8" class="empty">No matching issues found.</td>`;
                    tableBody.appendChild(emptyRow);
                }
            } else if (emptyRow) {
                emptyRow.remove();
            }
        });
    }

    // 5b. Kanban Board Real-time Live Search Filter
    const boardSearchInput = document.querySelector(".board-search-input");
    if (boardSearchInput) {
        boardSearchInput.addEventListener("input", function () {
            const query = boardSearchInput.value.toLowerCase().trim();
            const cards = document.querySelectorAll(".kanban-card");

            cards.forEach(card => {
                const title = card.querySelector(".kanban-card-title") ? card.querySelector(".kanban-card-title").textContent.toLowerCase() : "";
                const key = card.querySelector(".kanban-issue-key") ? card.querySelector(".kanban-issue-key").textContent.toLowerCase() : "";
                const labels = Array.from(card.querySelectorAll(".issue-label")).map(el => el.textContent.toLowerCase()).join(" ");

                if (title.includes(query) || key.includes(query) || labels.includes(query)) {
                    card.style.display = "";
                } else {
                    card.style.display = "none";
                }
            });
        });
    }

    const boardProjectFilter = document.querySelector(".board-filter-select");
    if (boardProjectFilter) {
        boardProjectFilter.addEventListener("change", function () {
            boardProjectFilter.form.requestSubmit();
        });
    }

    // 6. AJAX details view interactions (Comments, Watchers, Assignment)
    const commentForm = document.querySelector(".ajax-comment-form");
    const watcherForm = document.querySelector(".ajax-watch-form");
    const assigneeSelect = document.querySelector(".ajax-assign-form select");

    // Hijack Comment Form
    if (commentForm) {
        commentForm.addEventListener("submit", function (e) {
            e.preventDefault();
            const textarea = commentForm.querySelector("textarea[name='comment']");
            const commentVal = textarea.value.trim();
            if (!commentVal) return;

            const url = commentForm.getAttribute("action");
            const formData = new FormData(commentForm);

            fetch(url, {
                method: "POST",
                body: formData,
                headers: { "X-Requested-With": "XMLHttpRequest" }
            })
            .then(async res => {
                const payload = await res.json().catch(() => ({}));
                if (res.ok && !res.redirected && payload.ok === true) {
                    // Prepend new comment element to feed
                    const commentFeed = document.querySelector(".comment-box") ? document.querySelector(".comment-box").parentNode : null;
                    if (commentFeed) {
                        const newComment = document.createElement("div");
                        newComment.className = "comment-box";
                        newComment.style.opacity = "0";
                        newComment.style.transform = "translateY(-10px)";
                        newComment.style.transition = "all 0.3s ease";

                        const initials = document.querySelector(".user-avatar-initial") ? document.querySelector(".user-avatar-initial").textContent.trim() : "U";
                        const userName = document.querySelector(".user-profile-link") ? document.querySelector(".user-profile-link").textContent.trim() : "You";

                        newComment.innerHTML = `
                            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
                                <div style="display: flex; align-items: center; gap: 8px;">
                                    <span class="user-avatar-initial" style="width: 24px; height: 24px; font-size: 10px; background: var(--primary-subtle); color: var(--primary);">
                                        ${initials}
                                    </span>
                                    <strong>${userName}</strong>
                                </div>
                                <small>Just now</small>
                            </div>
                            <p>${escapeHTML(commentVal)}</p>
                        `;

                        // Remove empty paragraph if present
                        const emptyMsg = commentFeed.querySelector(".empty");
                        if (emptyMsg) emptyMsg.remove();

                        commentFeed.insertBefore(newComment, commentFeed.querySelector("form").nextSibling);

                        // Force reflow and animate
                        setTimeout(() => {
                            newComment.style.opacity = "1";
                            newComment.style.transform = "translateY(0)";
                        }, 50);
                    }

                    textarea.value = "";
                    Toast.show(payload.message || "Comment posted successfully.", "success");
                } else {
                    throw new Error(payload.error || "Comment was rejected");
                }
            })
            .catch(error => {
                Toast.show(error.message || "Failed to post comment. Please try again.", "error");
            });
        });
    }

    // Hijack Watcher Toggle Form
    if (watcherForm) {
        watcherForm.addEventListener("submit", function (e) {
            e.preventDefault();
            const action = watcherForm.getAttribute("action");
            const formData = new FormData(watcherForm);
            const actionInput = watcherForm.querySelector("input[name='action']");
            const submitBtn = watcherForm.querySelector("button");
            const countText = watcherForm.querySelector(".muted");

            const isUnwatching = actionInput.value === "unwatch";

            fetch(action, {
                method: "POST",
                body: formData,
                headers: { "X-Requested-With": "XMLHttpRequest" }
            })
            .then(async res => {
                const payload = await res.json().catch(() => ({}));
                if (res.ok && !res.redirected && payload.ok === true) {
                    if (isUnwatching) {
                        actionInput.value = "watch";
                        submitBtn.className = "button";
                        submitBtn.textContent = "Watch Issue";
                        Toast.show("You stopped watching this issue.", "success");
                    } else {
                        actionInput.value = "unwatch";
                        submitBtn.className = "button-secondary";
                        submitBtn.textContent = "Stop Watching";
                        Toast.show("You are now watching this issue.", "success");
                    }

                    // Increment/decrement watcher counts
                    if (countText) {
                        const match = countText.textContent.match(/\d+/);
                        if (match) {
                            let count = parseInt(match[0]);
                            count = isUnwatching ? Math.max(0, count - 1) : count + 1;
                            countText.innerHTML = `<strong>${count}</strong> people watching this issue`;
                        }
                    }
                } else {
                    throw new Error(payload.error || "Watcher update was rejected");
                }
            })
            .catch(error => {
                Toast.show(error.message || "Failed to update watching status.", "error");
            });
        });
    }

    // Hijack Assignee select changes
    if (assigneeSelect) {
        const assignForm = assigneeSelect.closest(".ajax-assign-form");
        if (assignForm) {
            assignForm.addEventListener("submit", function (e) {
                e.preventDefault();
                submitAssignment(assignForm);
            });

            assigneeSelect.addEventListener("change", function () {
                submitAssignment(assignForm);
            });
        }

        function submitAssignment(form) {
            const url = form.getAttribute("action");
            const formData = new FormData(form);
            const selectedText = assigneeSelect.options[assigneeSelect.selectedIndex].text;
            const selectedVal = assigneeSelect.value;

            fetch(url, {
                method: "POST",
                body: formData,
                headers: { "X-Requested-With": "XMLHttpRequest" }
            })
            .then(async res => {
                const payload = await res.json().catch(() => ({}));
                if (res.ok && !res.redirected && payload.ok === true) {
                    // Update assignee detail bubble in sidebar
                    const detailAssigneeSpan = document.querySelector(".detail-stat-item .detail-stat-value");
                    if (detailAssigneeSpan) {
                        if (selectedVal === "") {
                            detailAssigneeSpan.innerHTML = `<span style="color: var(--text-muted); font-style: italic;">Unassigned</span>`;
                        } else {
                            const initials = selectedText.split(" ").map(n => n[0]).join("").toUpperCase().substring(0, 2);
                            detailAssigneeSpan.innerHTML = `
                                <div style="display: flex; align-items: center; gap: 6px;">
                                    <span class="user-avatar-initial" style="width: 20px; height: 20px; font-size: 9px; background: var(--primary-subtle); color: var(--primary);">
                                        ${initials}
                                    </span>
                                    ${escapeHTML(selectedText)}
                                </div>
                            `;
                        }
                    }
                    Toast.show(`Assignment updated to ${selectedVal ? selectedText : "Unassigned"}`, "success");
                } else {
                    throw new Error(payload.error || "Assignment was rejected");
                }
            })
            .catch(error => {
                Toast.show(error.message || "Failed to update assignment.", "error");
            });
        }
    }

    function escapeHTML(str) {
        return str.replace(/[&<>'"]/g,
            tag => ({
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                "'": '&#39;',
                '"': '&quot;'
            }[tag] || tag)
        );
    }

    // Utility placeholder buttons
    document.querySelectorAll(".placeholder-action-btn").forEach(btn => {
        btn.addEventListener("click", function(e) {
            e.preventDefault();
            const actionName = this.getAttribute("data-action-name") || "Action";
            Toast.show(`${actionName} is coming soon!`, "info");
        });
    });

    // Filter button toggle
    const filterBtn = document.getElementById("boardFilterBtn");
    const filterForm = document.querySelector(".board-filter-form");
    if (filterBtn && filterForm) {
        filterBtn.addEventListener("click", function(e) {
            e.preventDefault();
            if (filterForm.style.display === "none" || getComputedStyle(filterForm).display === "none") {
                filterForm.style.display = "inline-flex";
            } else {
                filterForm.style.display = "none";
            }
        });
    }

    // Client-side Group By sorting
    const boardGroupBy = document.getElementById("boardGroupBy");
    if (boardGroupBy) {
        boardGroupBy.addEventListener("change", function() {
            const grouping = this.value;
            const columns = document.querySelectorAll(".kanban-column");

            columns.forEach(col => {
                const cardsContainer = col.querySelector(".kanban-cards");
                if (!cardsContainer) return;

                const cards = Array.from(cardsContainer.querySelectorAll(".kanban-card"));

                // Store original loaded index if not already present
                cards.forEach((card, idx) => {
                    if (!card.hasAttribute("data-original-index")) {
                        card.setAttribute("data-original-index", idx);
                    }
                });

                if (grouping === "none") {
                    cards.sort((a, b) => {
                        return parseInt(a.getAttribute("data-original-index")) - parseInt(b.getAttribute("data-original-index"));
                    });
                } else if (grouping === "assignee") {
                    cards.sort((a, b) => {
                        const nameA = a.getAttribute("data-assignee-name") || "zzzzzzz";
                        const nameB = b.getAttribute("data-assignee-name") || "zzzzzzz";
                        return nameA.localeCompare(nameB);
                    });
                } else if (grouping === "priority") {
                    const priorityMap = { "Urgent": 1, "High": 2, "Medium": 3, "Low": 4 };
                    cards.sort((a, b) => {
                        const pA = priorityMap[a.getAttribute("data-priority")] || 9;
                        const pB = priorityMap[b.getAttribute("data-priority")] || 9;
                        return pA - pB;
                    });
                }

                // Re-append sorted cards
                cards.forEach(card => cardsContainer.appendChild(card));
            });

            Toast.show(`Grouped board by: ${grouping.charAt(0).toUpperCase() + grouping.slice(1)}`, "success");
        });
    }
});
