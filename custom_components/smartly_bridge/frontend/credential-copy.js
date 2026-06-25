const COPY_ICON_PATH =
  "M19,21H8V7H19M19,5H8A2,2 0 0,0 6,7V21A2,2 0 0,0 8,23H19A2,2 0 0,0 21,21V7A2,2 0 0,0 19,5M16,1H4A2,2 0 0,0 2,3V17H4V3H16V1Z";

const CREDENTIAL_ROWS = [
  {
    labels: ["Client ID:", "Client ID："],
    ariaLabel: "Copy Client ID",
    copiedMessage: "Client ID copied to clipboard",
  },
  {
    labels: ["Client Secret:", "Client Secret："],
    ariaLabel: "Copy Client Secret",
    copiedMessage: "Client Secret copied to clipboard",
  },
];

const BUTTON_CLASS = "smartly-bridge-copy-button";
const STYLE_ID = "smartly-bridge-copy-button-style";
const BUTTON_STYLES = `
  .${BUTTON_CLASS} {
    align-items: center;
    appearance: none;
    background: transparent;
    border: 0;
    border-radius: 50%;
    box-shadow: none;
    box-sizing: border-box;
    color: var(--secondary-text-color);
    cursor: pointer;
    display: inline-flex;
    height: 32px;
    justify-content: center;
    line-height: 0;
    margin: 0 0 0 6px;
    min-height: 32px;
    min-width: 32px;
    outline: none;
    padding: 6px;
    position: relative;
    -webkit-tap-highlight-color: transparent;
    vertical-align: middle;
    width: 32px;
  }

  .${BUTTON_CLASS}:hover {
    background: var(--secondary-background-color);
    color: var(--primary-text-color);
  }

  .${BUTTON_CLASS}:focus-visible {
    background: var(--secondary-background-color);
    box-shadow: 0 0 0 2px var(--primary-color);
    color: var(--primary-text-color);
  }

  .${BUTTON_CLASS}:active {
    color: var(--primary-color);
  }

  .${BUTTON_CLASS} svg {
    display: block;
    fill: currentColor;
    height: 18px;
    pointer-events: none;
    width: 18px;
  }
`;

function copyWithFallback(value) {
  if (navigator.clipboard?.writeText) {
    return navigator.clipboard.writeText(value).catch(() => fallbackCopy(value));
  }

  fallbackCopy(value);
  return Promise.resolve();
}

function fallbackCopy(value) {
  const textarea = document.createElement("textarea");
  textarea.value = value;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  textarea.remove();
}

function notify(element, message) {
  element.dispatchEvent(
    new CustomEvent("hass-notification", {
      bubbles: true,
      composed: true,
      detail: { message },
    })
  );
}

function createCopyButton(code, row) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = BUTTON_CLASS;
  button.setAttribute("aria-label", row.ariaLabel);
  button.title = row.ariaLabel;
  button.innerHTML = `
    <svg aria-hidden="true" viewBox="0 0 24 24" focusable="false">
      <path d="${COPY_ICON_PATH}"></path>
    </svg>
  `;

  button.addEventListener("click", async (event) => {
    event.preventDefault();
    event.stopPropagation();

    const value = (code.textContent || "").trim();
    if (!value) {
      return;
    }

    await copyWithFallback(value);
    notify(button, row.copiedMessage);
  });

  return button;
}

function rowForListItem(listItem) {
  const text = Array.from(listItem.childNodes)
    .filter((node) => node.nodeType === Node.TEXT_NODE)
    .map((node) => node.textContent)
    .join("");

  return CREDENTIAL_ROWS.find((row) =>
    row.labels.some((label) => text.includes(label))
  );
}

function enhanceRoot(root) {
  ensureStyles(root);

  root.querySelectorAll("ha-markdown-element li").forEach((listItem) => {
    if (listItem.querySelector(`.${BUTTON_CLASS}`)) {
      return;
    }

    const row = rowForListItem(listItem);
    const code = listItem.querySelector("code");
    if (!row || !code) {
      return;
    }

    code.insertAdjacentElement("afterend", createCopyButton(code, row));
  });
}

function ensureStyles(root) {
  if (root.getElementById?.(STYLE_ID)) {
    return;
  }

  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = BUTTON_STYLES;

  if (root instanceof Document) {
    root.head.appendChild(style);
    return;
  }

  root.appendChild(style);
}

function collectRoots(root) {
  const roots = [root];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT);

  while (walker.nextNode()) {
    const element = walker.currentNode;
    if (element.shadowRoot) {
      roots.push(element.shadowRoot);
      roots.push(...collectRoots(element.shadowRoot));
    }
  }

  return roots;
}

function enhanceCredentialRows() {
  collectRoots(document).forEach(enhanceRoot);
}

const observer = new MutationObserver(enhanceCredentialRows);
observer.observe(document.documentElement, { childList: true, subtree: true });
window.setInterval(enhanceCredentialRows, 1000);
enhanceCredentialRows();
