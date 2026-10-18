// SPDX-License-Identifier: GPL-3.0-or-later
const cards = {
  forge: { title: 'Slot-otter Forge', stage: '01 / FORGE', edition: 'THE CPLD EDITION',
    description: 'The interface logic, brought together in an ATF1504AS CPLD. A compact take on the same 8-bit ISA SD-card interface.',
    logic: 'ATF1504AS CPLD', hardware: 'cpld' },
  classic: { title: 'Slot-otter Classic', stage: '02 / CLASSIC', edition: 'THE ORIGINAL DISCRETE DESIGN',
    description: 'The original Slot-otter, built with discrete logic chips. The same SD-card access for DOS, with every part of the interface on the board.',
    logic: 'Discrete logic chips', hardware: 'release' },
};
const $ = (id) => document.getElementById(id);
const base = new URL('./', document.baseURI);
const homeOrbit = '0deg 75deg 100%';
let selected = 'forge';
let viewer;
let starting = false;
let active = false;
let sizes = {};
const retries = { forge: 0, classic: 0 };

function updateSize() {
  const bytes = sizes[selected];
  $('download-size').textContent = bytes ? `${(bytes / 1e6).toFixed(1)} MB model · loads on request` : 'Loads only the selected card';
}
fetch(new URL('models/sizes.json', base)).then((r) => r.ok ? r.json() : {}).then((data) => { sizes = data; updateSize(); }).catch(() => {});

function selectCard(id) {
  selected = id;
  const card = cards[id];
  for (const button of document.querySelectorAll('[data-model]')) button.setAttribute('aria-pressed', String(button.dataset.model === id));
  $('stage-label').textContent = card.stage;
  $('edition').textContent = card.edition;
  $('card-title').textContent = card.title;
  $('card-description').textContent = card.description;
  $('card-logic').textContent = card.logic;
  $('hardware-link').href = `https://github.com/ifilot/slot-otter/tree/master/pcb/${card.hardware}`;
  $('poster').src = new URL(`posters/${id}.webp`, base).href;
  $('poster').alt = `${card.title} card and bracket`;
  updateSize();
  if (active) loadSelectedModel();
}

function resetView() {
  if (!viewer) return;
  viewer.cameraOrbit = homeOrbit;
  viewer.cameraTarget = 'auto auto auto';
  viewer.fieldOfView = '30deg';
  viewer.jumpCameraToGoal();
}

function loadSelectedModel() {
  $('viewer-status').textContent = `Loading ${cards[selected].title}…`;
  $('reset-view').disabled = true;
  viewer.alt = `Interactive ${cards[selected].title} card and bracket. Drag or use arrow keys to rotate; scroll or pinch to zoom.`;
  const url = new URL(`models/${selected}.glb`, base);
  // Model-viewer caches failed URLs too; a retry must use a fresh cache key.
  if (retries[selected]) url.searchParams.set('retry', retries[selected]);
  viewer.dataset.cardModel = selected;
  viewer.src = url.href;
  resetView();
}

async function startViewer() {
  if (starting) return;
  starting = true;
  $('load-model').disabled = true;
  $('viewer-status').textContent = 'Starting the 3D viewer…';
  try {
    globalThis.ModelViewerElement ??= {};
    globalThis.ModelViewerElement.dracoDecoderLocation = new URL('draco/', base).href;
    // Load the viewer library only after the visitor requests interactive 3D.
    await import('@google/model-viewer');
    const ModelViewer = customElements.get('model-viewer');
    ModelViewer.dracoDecoderLocation = new URL('draco/', base).href;
    viewer ??= document.createElement('model-viewer');
    viewer.setAttribute('camera-controls', '');
    viewer.setAttribute('touch-action', 'pan-y');
    viewer.setAttribute('disable-pan', '');
    viewer.setAttribute('interaction-prompt', 'none');
    viewer.setAttribute('environment-image', 'neutral');
    viewer.setAttribute('exposure', '0.9');
    viewer.setAttribute('shadow-intensity', '0');
    viewer.setAttribute('min-camera-orbit', 'auto auto 45%');
    viewer.setAttribute('max-camera-orbit', 'auto auto 250%');
    viewer.setAttribute('aria-label', 'Interactive card model');
    viewer.addEventListener('load', () => {
      $('viewer-status').textContent = `${cards[selected].title} ready. Drag to rotate.`;
      $('reset-view').disabled = false;
      $('poster').classList.add('hidden');
      resetView();
    });
    viewer.addEventListener('error', () => {
      retries[viewer.dataset.cardModel] += 1;
      $('viewer-status').textContent = 'The 3D model could not load. Check your connection and try again.';
      $('poster').classList.remove('hidden');
      $('launch').classList.remove('hidden');
      $('load-model').disabled = false;
      $('reset-view').disabled = true;
      viewer.remove();
      viewer = undefined;
      active = false;
    });
    $('stage').append(viewer);
    active = true;
    $('launch').classList.add('hidden');
    loadSelectedModel();
  } catch {
    $('viewer-status').textContent = 'The 3D viewer could not start. Check your connection or try a browser with WebGL support.';
    $('load-model').disabled = false;
  } finally {
    starting = false;
  }
}
for (const button of document.querySelectorAll('[data-model]')) button.addEventListener('click', () => selectCard(button.dataset.model));
$('load-model').addEventListener('click', startViewer);
$('reset-view').addEventListener('click', resetView);
