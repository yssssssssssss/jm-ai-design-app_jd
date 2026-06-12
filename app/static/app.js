const activeTaskStatuses = new Set(["queued", "running"]);

const initUploadComposer = () => {
  const fileInput = document.querySelector("#upload-files");
  const fileList = document.querySelector("#selected-files");
  const dropzone = document.querySelector("#upload-dropzone");
  const filePickerButton = document.querySelector("#file-picker-button");
  const auditComposer = document.querySelector("#audit-composer");
  const submitTaskButton = document.querySelector("#submit-task-button");
  const uploadClientError = document.querySelector("#upload-client-error");
  const auditSpecInputs = document.querySelectorAll('input[name="audit_spec_ids"]');
  const allowedFileExtensions = new Set(["png", "jpg", "jpeg", "webp"]);
  const maxUploadFiles = Number(auditComposer?.getAttribute("data-max-upload-files") || "0");
  const maxUploadBytes =
    Number(auditComposer?.getAttribute("data-max-upload-mb-per-file") || "0") * 1024 * 1024;

  const showUploadError = (message) => {
    if (!uploadClientError) {
      return;
    }
    uploadClientError.textContent = message;
    uploadClientError.hidden = false;
  };

  const clearUploadError = () => {
    if (!uploadClientError) {
      return;
    }
    uploadClientError.textContent = "";
    uploadClientError.hidden = true;
  };

  const uploadMessage = (name, fallback) =>
    uploadClientError?.getAttribute(name) || fallback;

  const formatFileSize = (bytes) => {
    if (!Number.isFinite(bytes)) {
      return "-";
    }
    if (bytes < 1024 * 1024) {
      return `${Math.max(1, Math.round(bytes / 1024))} KB`;
    }
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  };

  const uploadIssueForFile = (file) => {
    const extension = file.name.split(".").pop()?.toLowerCase();
    if (!extension || !allowedFileExtensions.has(extension)) {
      return "文件类型不支持";
    }
    if (maxUploadBytes > 0 && file.size > maxUploadBytes) {
      return "文件过大";
    }
    return "";
  };

  const hasSelectedAuditSpec = () =>
    Array.from(auditSpecInputs).some((input) => input.checked);

  const hasUnsupportedUpload = () =>
    Array.from(fileInput?.files || []).some(
      (file) => uploadIssueForFile(file) === "文件类型不支持",
    );

  const hasOversizedUpload = () =>
    Array.from(fileInput?.files || []).some(
      (file) => uploadIssueForFile(file) === "文件过大",
    );

  if (fileInput && fileList) {
    const renderSelectedFiles = () => {
      fileList.replaceChildren();
      for (const file of fileInput.files) {
        const issue = uploadIssueForFile(file);
        const item = document.createElement("li");
        item.classList.toggle("is-invalid", Boolean(issue));
        if (issue) {
          item.setAttribute("data-file-status", "invalid");
        }
        const name = document.createElement("span");
        name.className = "file-item-name";
        name.textContent = file.name;
        const meta = document.createElement("span");
        meta.className = "file-item-meta";
        meta.textContent = `${formatFileSize(file.size)} · ${issue || "可上传"}`;
        item.append(name, meta);
        fileList.appendChild(item);
      }
    };

    fileInput.addEventListener("change", () => {
      clearUploadError();
      renderSelectedFiles();
    });
  }

  for (const input of auditSpecInputs) {
    input.addEventListener("change", clearUploadError);
  }

  if (fileInput && filePickerButton) {
    filePickerButton.addEventListener("click", () => {
      fileInput.click();
    });
  }

  if (auditComposer && submitTaskButton) {
    auditComposer.addEventListener("submit", (event) => {
      if (!hasSelectedAuditSpec()) {
        event.preventDefault();
        showUploadError(
          uploadMessage("data-message-no-spec", "请选择至少一个审核规范"),
        );
        return;
      }
      if (!fileInput?.files.length) {
        event.preventDefault();
        showUploadError(uploadMessage("data-message-no-file", "请至少上传 1 张图片"));
        return;
      }
      if (maxUploadFiles > 0 && fileInput.files.length > maxUploadFiles) {
        event.preventDefault();
        showUploadError(uploadMessage("data-message-too-many-files", "上传图片数量超出限制"));
        return;
      }
      if (hasUnsupportedUpload()) {
        event.preventDefault();
        showUploadError(
          uploadMessage("data-message-bad-file", "仅支持 PNG/JPG/JPEG/WEBP 图片"),
        );
        return;
      }
      if (hasOversizedUpload()) {
        event.preventDefault();
        showUploadError(uploadMessage("data-message-too-large-file", "单张图片超出大小限制"));
        return;
      }
      if (!auditComposer.checkValidity()) {
        event.preventDefault();
        auditComposer.reportValidity();
        return;
      }
      if (auditComposer.dataset.submitting === "true") {
        event.preventDefault();
        return;
      }
      auditComposer.dataset.submitting = "true";
      submitTaskButton.disabled = true;
      submitTaskButton.textContent =
        submitTaskButton.getAttribute("data-pending-text") || "提交中...";
    });
  }

  if (fileInput && fileList && dropzone) {
    const isFileDrag = (event) =>
      Array.from(event.dataTransfer?.types || []).includes("Files");
    const setDraggedFiles = (files) => {
      const transfer = new DataTransfer();
      for (const file of files) {
        transfer.items.add(file);
      }
      fileInput.files = transfer.files;
      fileInput.dispatchEvent(new Event("change", { bubbles: true }));
    };

    for (const eventName of ["dragover", "drop"]) {
      document.addEventListener(eventName, (event) => {
        if (!isFileDrag(event)) {
          return;
        }
        event.preventDefault();
      });
    }

    for (const eventName of ["dragenter", "dragover"]) {
      dropzone.addEventListener(eventName, (event) => {
        if (!isFileDrag(event)) {
          return;
        }
        event.preventDefault();
        dropzone.classList.add("is-dragging");
      });
    }

    for (const eventName of ["dragleave", "drop"]) {
      dropzone.addEventListener(eventName, () => {
        dropzone.classList.remove("is-dragging");
      });
    }

    dropzone.addEventListener("drop", (event) => {
      event.preventDefault();
      if (!event.dataTransfer?.files.length) {
        return;
      }
      setDraggedFiles(event.dataTransfer.files);
    });
  }
};

const initTaskDetailPolling = () => {
  const detail = document.querySelector("[data-task-id]");

  if (!detail) {
    return;
  }

  const taskId = detail.getAttribute("data-task-id");
  const status = document.querySelector("#task-status");
  const backLink = document.querySelector("#task-back-link");
  const summary = document.querySelector("#task-summary");
  const error = document.querySelector("#task-error");
  const failureActions = document.querySelector("#task-failure-actions");
  const reportLinks = document.querySelector("#task-report-links");
  const visiblePollIntervalMs = 2500;
  const hiddenPollIntervalMs = 15000;
  let pollTimer = null;

  const setOptionalText = (element, value) => {
    if (!element) {
      return;
    }
    element.textContent = value || "";
    element.hidden = !value;
  };

  const updateReportLinks = (report) => {
    if (!reportLinks) {
      return;
    }
    reportLinks.hidden = !report;
    if (!report) {
      return;
    }
    const [htmlLink, pdfLink] = reportLinks.querySelectorAll("a");
    if (htmlLink) {
      htmlLink.href = report.html;
    }
    if (pdfLink) {
      pdfLink.href = report.pdf;
    }
  };

  const updateFailureActions = (actions) => {
    if (!failureActions) {
      return;
    }
    failureActions.replaceChildren();
    const availableActions = Array.isArray(actions) ? actions : [];
    failureActions.hidden = availableActions.length === 0;
    for (const action of availableActions) {
      const link = document.createElement("a");
      link.className = "task-action-link";
      link.href = action.href;
      link.textContent = action.label;
      failureActions.appendChild(link);
    }
  };

  const updateBackLink = (link) => {
    if (!backLink || !link) {
      return;
    }
    backLink.href = link.href;
    backLink.textContent = link.label;
  };

  const updateImages = (images) => {
    for (const image of images || []) {
      const row = document.querySelector(`[data-image-id="${image.id}"]`);
      if (!row) {
        continue;
      }
      const badge = row.querySelector(".status");
      if (badge) {
        badge.textContent = image.status_label || image.status;
        badge.className = `status status-${image.status}`;
      }
      const errorCell = row.querySelector("[data-image-error]");
      if (errorCell) {
        errorCell.textContent = image.error_message || "-";
      }
    }
  };

  const taskIsActive = () =>
    activeTaskStatuses.has(status?.getAttribute("data-task-status-value") || "");

  const clearPollTimer = () => {
    if (!pollTimer) {
      return;
    }
    window.clearTimeout(pollTimer);
    pollTimer = null;
  };

  const schedulePoll = () => {
    clearPollTimer();
    pollTimer = window.setTimeout(
      () => poll(),
      document.hidden ? hiddenPollIntervalMs : visiblePollIntervalMs,
    );
  };

  const poll = async ({ force = false } = {}) => {
    if (!force && !taskIsActive()) {
      return;
    }
    clearPollTimer();
    let response;
    try {
      response = await fetch(`/tasks/${taskId}/status`);
    } catch {
      if (taskIsActive()) {
        schedulePoll();
      }
      return;
    }
    if (!response.ok) {
      if (taskIsActive()) {
        schedulePoll();
      }
      return;
    }
    const data = await response.json();
    if (status) {
      status.textContent = data.status_label || data.status;
      status.className = `status status-${data.status}`;
      status.setAttribute("data-task-status-value", data.status);
    }
    updateBackLink(data.back_link);
    setOptionalText(summary, data.summary);
    setOptionalText(error, data.error_message);
    updateFailureActions(data.failure_actions);
    updateReportLinks(data.report);
    updateImages(data.images);
    if (activeTaskStatuses.has(data.status)) {
      schedulePoll();
    }
  };

  document.addEventListener("visibilitychange", () => {
    if (!taskIsActive()) {
      return;
    }
    if (document.hidden) {
      schedulePoll();
      return;
    }
    poll({ force: true });
  });

  if (taskIsActive()) {
    poll({ force: true });
  }
};

const initRunningTaskListPolling = () => {
  const taskList = document.querySelector("[data-task-list='running']");

  if (!taskList || Number(taskList.getAttribute("data-task-count") || "0") <= 0) {
    return;
  }

  const currentTaskIds = () =>
    Array.from(document.querySelectorAll("[data-task-row]:not([data-task-retired])")).map(
      (row) => Number(row.getAttribute("data-task-row")),
    );

  const nextTaskIds = (nextTasks) => (nextTasks || []).map((task) => Number(task.id));

  const hasUnexpectedRunningListChange = (nextTasks) => {
    const current = currentTaskIds();
    const next = nextTaskIds(nextTasks);
    const currentSet = new Set(current);
    if (next.some((id) => !currentSet.has(id))) {
      return true;
    }
    let nextIndex = 0;
    for (const id of current) {
      if (id === next[nextIndex]) {
        nextIndex += 1;
      }
    }
    return nextIndex !== next.length;
  };

  const updateListStatuses = (tasks) => {
    for (const task of tasks || []) {
      const badge = document.querySelector(`[data-task-status="${task.id}"]`);
      if (!badge) {
        continue;
      }
      badge.textContent = task.status_label || task.status;
      badge.className = `status status-${task.status}`;
    }
  };

  const renderEmptyRunningState = () => {
    if (taskList.querySelector("[data-task-row]")) {
      return;
    }
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "暂无正在分析的任务。";
    taskList.replaceChildren(empty);
    taskList.setAttribute("data-task-count", "0");
  };

  const retireCompletedTaskRows = (nextTasks) => {
    const activeIds = new Set(nextTaskIds(nextTasks));
    for (const row of document.querySelectorAll("[data-task-row]:not([data-task-retired])")) {
      const taskId = Number(row.getAttribute("data-task-row"));
      if (activeIds.has(taskId)) {
        continue;
      }
      row.setAttribute("data-task-retired", "true");
      row.classList.add("is-retiring");
      const action = row.querySelector(".text-action");
      if (action) {
        action.textContent = "已转入历史任务";
        action.removeAttribute("href");
      }
      window.setTimeout(() => {
        row.remove();
        renderEmptyRunningState();
      }, 1600);
    }
  };

  const pollRunningTasks = async () => {
    let response;
    try {
      response = await fetch("/tasks/running/status");
    } catch {
      window.setTimeout(pollRunningTasks, 5000);
      return;
    }
    if (!response.ok) {
      window.setTimeout(pollRunningTasks, 5000);
      return;
    }
    const data = await response.json();
    if (hasUnexpectedRunningListChange(data.tasks)) {
      window.location.reload();
      return;
    }
    retireCompletedTaskRows(data.tasks);
    updateListStatuses(data.tasks);
    window.setTimeout(pollRunningTasks, 5000);
  };

  window.setTimeout(pollRunningTasks, 5000);
};

const initSpecSearch = () => {
  const specSearch = document.querySelector("[data-spec-search]");

  if (!specSearch) {
    return;
  }

  const form = document.querySelector("#spec-search-form");
  const input = document.querySelector("#spec-search-input");
  const stream = document.querySelector("#spec-chat-stream");
  const backToTop = document.querySelector("#spec-back-to-top");
  const maxQueryLength = Number(specSearch.getAttribute("data-max-query-length") || "200");

  const scrollToLatest = () => {
    stream.scrollTop = stream.scrollHeight;
  };

  const message = (role, content) => {
    const item = document.createElement("article");
    item.className = `chat-message chat-message-${role}`;

    const avatar = document.createElement("div");
    avatar.className = "chat-avatar";
    avatar.textContent = role === "user" ? "你" : "AI";

    const bubble = document.createElement("div");
    bubble.className = "chat-bubble";
    if (typeof content === "string") {
      const paragraph = document.createElement("p");
      paragraph.textContent = content;
      bubble.appendChild(paragraph);
    } else {
      bubble.appendChild(content);
    }

    item.append(avatar, bubble);
    stream.appendChild(item);
    scrollToLatest();
    return item;
  };

  const renderAsset = (asset) => {
    const link = document.createElement("a");
    link.className = "spec-asset-card";
    link.href = asset.url;
    link.target = "_blank";
    link.rel = "noreferrer";

    const image = document.createElement("img");
    image.src = asset.url;
    image.alt = asset.label || "规范素材";
    image.loading = "lazy";

    const caption = document.createElement("span");
    caption.textContent = asset.label || asset.source || "规范素材";

    link.append(image, caption);
    return link;
  };

  const renderResult = (result) => {
    const item = document.createElement("section");
    item.className = "spec-result-item";

    const head = document.createElement("div");
    head.className = "spec-result-head";

    const title = document.createElement("h2");
    title.textContent = result.title || result.spec_label || "规范片段";

    const source = document.createElement("span");
    source.className = "spec-result-source";
    source.textContent = result.source_ref || result.spec_label || "规范来源";

    head.append(title, source);

    const excerpt = document.createElement("p");
    excerpt.className = "spec-result-excerpt";
    excerpt.textContent = result.excerpt || "";

    item.append(head, excerpt);

    const assets = Array.isArray(result.assets) ? result.assets.filter((asset) => asset.url) : [];
    if (assets.length) {
      const grid = document.createElement("div");
      grid.className = "spec-asset-grid";
      for (const asset of assets) {
        grid.appendChild(renderAsset(asset));
      }
      item.appendChild(grid);
    }

    return item;
  };

  const renderPayload = (payload) => {
    const wrapper = document.createElement("div");
    const summary = document.createElement("p");
    summary.className = "spec-result-summary";
    summary.textContent = payload.summary || "已完成检索。";
    wrapper.appendChild(summary);

    const results = Array.isArray(payload.results) ? payload.results : [];
    if (!results.length) {
      const empty = document.createElement("p");
      empty.className = "meta";
      empty.textContent = "可以换一个关键词，或尝试输入组件名、状态名、颜色/尺寸要求。";
      wrapper.appendChild(empty);
      return wrapper;
    }

    const list = document.createElement("div");
    list.className = "spec-result-list";
    for (const result of results) {
      list.appendChild(renderResult(result));
    }
    wrapper.appendChild(list);
    return wrapper;
  };

  const setBusy = (busy) => {
    const button = form.querySelector("button");
    input.disabled = busy;
    button.disabled = busy;
    button.textContent = busy ? "检索中" : "发送";
  };

  const submitSearch = async () => {
    const query = input.value.trim();
    if (!query) {
      return;
    }
    if (query.length > maxQueryLength) {
      message("assistant", `检索内容不能超过 ${maxQueryLength} 个字符。`);
      return;
    }

    message("user", query);
    input.value = "";
    input.style.height = "auto";
    setBusy(true);
    const pending = message("assistant", "正在检索规范...");

    try {
      const body = new URLSearchParams({ query });
      const response = await fetch(form.action, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body,
      });
      const payload = await response.json();
      pending.remove();
      if (!response.ok) {
        message("assistant", payload.error || "检索失败，请稍后重试。");
        return;
      }
      message("assistant", renderPayload(payload));
    } catch {
      pending.remove();
      message("assistant", "检索失败，请稍后重试。");
    } finally {
      setBusy(false);
      input.focus();
    }
  };

  input.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 160)}px`;
  });

  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    submitSearch();
  });

  if (backToTop) {
    backToTop.addEventListener("click", () => {
      stream.scrollTo({ top: 0, behavior: "smooth" });
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  }
};

initUploadComposer();
initTaskDetailPolling();
initRunningTaskListPolling();
initSpecSearch();
