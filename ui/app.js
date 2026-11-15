"use strict";

const byId = id => document.getElementById(id);
const status = byId("status");
const sheet = byId("sheet");
const inspector = byId("inspector");
const previews = byId("previews");
const previewImages = previews.querySelectorAll("img");
const imageCache = new Map();
const installed = byId("installed");
const vocabularies = byId("vocabularies");
const componentLabels = new Map();


let batch;
let selection = 0;
let busy = false;
let previewRequest = 0;
const background = byId("background");

function sprites() {
  return batch.candidates.flatMap(candidate => candidate.sprites);
}

function selected() {
  return sprites()[selection];
}

function spriteLabel(index, sprite) {
  const candidate = batch.candidates[Math.floor(index / 4)];
  const label = candidate.label ? `${candidate.key} · ${candidate.label}` : (componentLabels.get(candidate.key) ?? candidate.key.replaceAll("_", " "));
  return `${label} · ${sprite.angle}°`;
}

function loadImage(url) {
  if (!imageCache.has(url)) {
    const image = new Image();
    image.src = url;
    imageCache.set(url, image.decode().then(() => image));
  }
  return imageCache.get(url);
}

function renderSheet() {
  const rows = byId("candidates");
  rows.replaceChildren();
  byId("save-batch").href = `/batch/${batch.id}.zip`;
  const canReroll = batch.can_reroll && batch.generated.length > 0;
  byId("row-actions").hidden = !canReroll;

  batch.candidates.forEach((candidate, candidateIndex) => {
    const row = rows.insertRow();
    const number = document.createElement("th");
    number.scope = "row";
    number.textContent = candidate.label ? `${candidate.key} · ${candidate.label}` : (componentLabels.get(candidate.key) ?? candidate.key);
    row.append(number);
    candidate.sprites.forEach((sprite, rotationIndex) => {
      const index = candidateIndex * 4 + rotationIndex;
      const button = document.createElement("button");
      const image = document.createElement("img");
      button.type = "button";
      button.dataset.sprite = index;
      button.setAttribute("aria-pressed", String(index === selection));
      button.addEventListener("click", () => inspect(index, true));
      image.alt = spriteLabel(index, sprite);
      image.width = 64;
      image.height = 128;
      image.style.backgroundColor = background.value;
      image.src = sprite.url;
      button.append(image);
      row.insertCell().append(button);
    });
    if (canReroll) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = "Reroll";
      button.setAttribute("aria-label", `Reroll row ${candidate.key}`);
      button.dataset.reroll = candidate.key;
      button.disabled = busy;
      button.addEventListener("click", () => {
        selection = candidateIndex * 4 + selection % 4;
        showSheet();
        reroll(candidate.key);
      });
      row.insertCell().append(button);
    }
  });
}

function showSheet(restoreFocus = false) {
  ++previewRequest;
  inspector.hidden = true;
  sheet.hidden = false;
  for (const button of sheet.querySelectorAll("[data-sprite]")) {
    const current = Number(button.dataset.sprite) === selection;
    button.setAttribute("aria-pressed", String(current));
    if (restoreFocus && current) button.focus();
  }
}

async function inspect(index, moveFocus = false) {
  const request = ++previewRequest;
  selection = (index + sprites().length) % sprites().length;
  const sprite = selected();
  const label = spriteLabel(selection, sprite);
  sheet.hidden = true;
  inspector.hidden = false;
  byId("caption").textContent = label;
  const key = batch.candidates[Math.floor(selection / 4)].key;
  const current = batch.generated.some(entry => entry.id === key);
  byId("reroll").hidden = !current || !batch.can_reroll;
  const geometry = byId("save-geometry");
  geometry.hidden = !current;
  geometry.href = `/geometry/${batch.id}/${key}`;
  byId("save").href = sprite.url + "?download";
  previews.hidden = true;
  if (moveFocus) byId("back").focus();

  try {
    const image = await loadImage(sprite.url);
    if (request !== previewRequest) return;
    for (const preview of previewImages) {
      preview.src = image.src;
      preview.alt = label;
    }
    previews.hidden = false;
  } catch {
    if (request === previewRequest) status.textContent = "Could not load sprite.";
  }
}

async function generate(settings, endpoint, replaceRow = false) {
  if (busy) return;
  busy = true;
  byId("render-scenes").disabled = true;
  byId("render-component").disabled = true;
  setRerollDisabled(true);
  status.textContent = replaceRow ? "Rerolling row…" : "Rendering batch…";
  const start = performance.now();
  try {
    const result = await fetch(endpoint, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(settings),
    });
    const data = await result.json();
    if (!result.ok) throw new Error(data.error);
    batch = data;
    if (!replaceRow) imageCache.clear();
    if (!replaceRow) selection = 0;
    renderSheet();
    if (replaceRow && !inspector.hidden) await inspect(selection);
    else showSheet(replaceRow);
    const message = replaceRow ? `Rerolled row ${settings.candidate}`
      : `${batch.candidates.length} rows · ${sprites().length} sprites`;
    const requestSeconds = ((performance.now() - start) / 1000).toFixed(2);
    const serverTime = Number.isFinite(batch.server_ms)
      ? ` · server ${(batch.server_ms / 1000).toFixed(2)} s`
      : "";
    status.textContent = `${message} · request ${requestSeconds} s${serverTime}`;
  } catch (error) {
    status.textContent = error.message;
  } finally {
    busy = false;
    updateBatchButton();
    byId("render-component").disabled = false;
    setRerollDisabled(false);
  }
}

async function spritePng(sprite) {
  const image = await loadImage(sprite.url);
  const canvas = document.createElement("canvas");
  canvas.width = image.naturalWidth;
  canvas.height = image.naturalHeight;
  canvas.getContext("2d").drawImage(image, 0, 0);
  return encodePng(canvas);
}

function encodePng(canvas) {
  return new Promise((resolve, reject) => {
    canvas.toBlob(blob => blob ? resolve(blob) : reject(new Error("PNG encoding failed")), "image/png");
  });
}

async function sheetPng() {
  const candidates = batch.candidates;
  const canvas = document.createElement("canvas");
  canvas.width = 4 * 64;
  canvas.height = candidates.length * 128;
  const drawing = canvas.getContext("2d");
  const color = background.value;
  if (color) {
    drawing.fillStyle = color;
    drawing.fillRect(0, 0, canvas.width, canvas.height);
  }
  for (const [row, candidate] of candidates.entries()) {
    const images = await Promise.all(candidate.sprites.map(sprite => loadImage(sprite.url)));
    images.forEach((image, column) => drawing.drawImage(image, column * 64, row * 128));
  }
  return encodePng(canvas);
}

async function copyImage(makePng) {
  try {
    if (!navigator.clipboard?.write || !window.ClipboardItem) {
      throw new Error("This browser does not support copying PNG images. Use Save instead.");
    }
    // Start the clipboard write during the click, including in Safari.
    await navigator.clipboard.write([new ClipboardItem({"image/png": makePng()})]);
    status.textContent = "Copied image.";
  } catch (error) {
    status.textContent = error.message || "Could not copy image. Use Save instead.";
  }
}

function selectedVocabularies() {
  return new FormData(installed).getAll("vocabularies");
}

function updateBatchButton() {
  byId("render-scenes").disabled = busy || selectedVocabularies().length === 0;
}

installed.addEventListener("change", updateBatchButton);
installed.addEventListener("submit", event => {
  event.preventDefault();
  generate({
    vocabularies: selectedVocabularies(),
    seed: byId("assembly-seed").valueAsNumber,
    silhouette: byId("silhouette").value,
  }, "/compose");
});

function setRerollDisabled(disabled) {
  byId("reroll").disabled = disabled;
  for (const button of sheet.querySelectorAll("[data-reroll]")) button.disabled = disabled;
}

function reroll(candidate) {
  generate({batch: batch.id, candidate}, "/reroll", true);
}

byId("reroll").addEventListener("click", () => {
  reroll(batch.candidates[Math.floor(selection / 4)].key);
});

byId("render-component").addEventListener("click", () => {
  generate({component: byId("component-choice").value}, "/render-component");
});

async function readJSON(path) {
  const response = await fetch(path, {cache: "no-store"});
  const value = await response.json();
  if (!response.ok) throw new Error(value.error);
  return value;
}

async function loadInputs() {
  try {
    const [names, components] = await Promise.all([readJSON("/vocabularies"), readJSON("/components")]);
    for (const name of names) {
      const input = document.createElement("input");
      input.type = "checkbox";
      input.name = "vocabularies";
      input.value = name;
      input.checked = name === "Dry material handling";
      const label = document.createElement("label");
      label.append(input, name);
      vocabularies.append(label, document.createElement("br"));
    }
    installed.hidden = false;
    updateBatchButton();
    components.forEach(component => componentLabels.set(component.id, component.label));
    byId("component-choice").replaceChildren(
      ...components.map(component => new Option(component.label, component.id))
    );
    byId("component-preview").hidden = components.length === 0;
  } catch (error) {
    status.textContent = error.message;
  }
}
loadInputs();
function updateBackground() {
  for (const image of sheet.querySelectorAll("img")) {
    image.style.backgroundColor = background.value;
  }
  for (const preview of previewImages) {
    preview.style.backgroundColor = background.value;
  }
}
background.addEventListener("change", updateBackground);
updateBackground();
byId("back").addEventListener("click", () => showSheet(true));
byId("previous").addEventListener("click", () => inspect(selection - 1));
byId("next").addEventListener("click", () => inspect(selection + 1));
byId("copy").addEventListener("click", () => copyImage(() => spritePng(selected())));
byId("copy-sheet").addEventListener("click", () => copyImage(sheetPng));
byId("save-sheet").addEventListener("click", async () => {
  try {
    const url = URL.createObjectURL(await sheetPng());
    const link = document.createElement("a");
    link.href = url;
    link.download = "becher-contact-sheet.png";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (error) {
    status.textContent = error.message;
  }
});
document.addEventListener("keydown", event => {
  if (inspector.hidden || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey ||
      event.target.closest("input, select, textarea, [contenteditable]")) return;
  const actions = {
    Escape: () => showSheet(true),
    ArrowLeft: () => inspect(selection - 1),
    ArrowRight: () => inspect(selection + 1),
  };
  if (!Object.hasOwn(actions, event.key)) return;
  event.preventDefault();
  actions[event.key]();
});
