const fileInput = document.querySelector("#upload-files");
const fileList = document.querySelector("#selected-files");
const dropzone = document.querySelector("#upload-dropzone");
const filePickerButton = document.querySelector("#file-picker-button");

if (fileInput && fileList) {
  const renderSelectedFiles = () => {
    fileList.replaceChildren();
    for (const file of fileInput.files) {
      const item = document.createElement("li");
      item.textContent = file.name;
      fileList.appendChild(item);
    }
  };

  fileInput.addEventListener("change", renderSelectedFiles);
}

if (fileInput && filePickerButton) {
  filePickerButton.addEventListener("click", () => {
    fileInput.click();
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

const detail = document.querySelector("[data-task-id]");

if (detail) {
  const taskId = detail.getAttribute("data-task-id");
  const status = document.querySelector("#task-status");

  const poll = async () => {
    const response = await fetch(`/tasks/${taskId}/status`);
    if (!response.ok) {
      return;
    }
    const data = await response.json();
    if (status) {
      status.textContent = data.status;
      status.className = `status status-${data.status}`;
    }
    if (data.status === "queued" || data.status === "running") {
      window.setTimeout(poll, 2500);
      return;
    }
    window.location.reload();
  };

  if (status && (status.textContent === "queued" || status.textContent === "running")) {
    window.setTimeout(poll, 2500);
  }
}

const taskList = document.querySelector("[data-task-list='running']");

if (taskList && Number(taskList.getAttribute("data-task-count") || "0") > 0) {
  window.setTimeout(() => {
    window.location.reload();
  }, 5000);
}

const specSearch = document.querySelector("[data-spec-search]");

if (specSearch) {
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
}
