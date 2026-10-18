# Slot-otter 3D card explorer

Public site: <https://ifilot.github.io/slot-otter/>

A static GitHub Pages website for rotating and zooming the **cards and their
brackets only**. No motherboard models are shipped. Visitors choose Classic or
Forge; the viewer library and selected model download only after clicking
**Explore in 3D**. The page starts with small WebP posters. Everything, including
the Draco decoder, is served from the same Pages site; no CDN is required.

## Develop and verify

Requires Node.js 20.19+ or 22+.

```sh
cd website
npm ci
npm run dev
```

Production build and browser checks:

```sh
npm run build
npx playwright install --with-deps chromium
npm test
```

The build copies the existing README thumbnails as posters and the dependency's
Draco decoder into ignored `public/` folders. It generates model download sizes
and third-party notices. Model URLs include content fingerprints so updated
hardware geometry replaces cached models after deployment. `dist/`, dependencies,
and test outputs are ignored.
The browser tests check on-demand loading, card switching, drag rotation, zoom,
reset, download failure/retry, local decoder requests, and a narrow mobile layout.

`.github/workflows/website.yml` builds and tests on relevant pull requests and
pushes. Successful pushes to `master` deploy `website/dist` through GitHub Actions
and GitHub Pages. The workflow can also be started manually. The repository's
Pages publishing source must be **GitHub Actions**.

## Regenerate the models

The versioned GLBs are small web assets, not full Blender scenes. They contain
Draco-compressed geometry and two 1024-pixel copper color textures per card.
The model files are approximately 1.3 MB (Forge) and 1.7 MB (Classic).
Run these commands from the repository root with Blender 4.5+ and its Draco
export support:

```sh
blender --background pcb/cpld/render/slot-otter-cpld-rev1.blend \
  --python-exit-code 1 --python tools/export_web_models.py -- \
  --output website/public/models/forge.glb
blender --background pcb/release/render/slot-otter-discrete.blend \
  --python-exit-code 1 --python tools/export_web_models.py -- \
  --output website/public/models/classic.glb
```

The exporter preserves the source hardware geometry, converts the copper color
shaders to portable UV textures, stands the card upright, combines its meshes,
and compresses the geometry. It reduces texture resolution and simplifies the
surface shaders for browser use. It does not change the source Blender files.
Both models include underside screw heads, continuous threaded shanks through
the bracket and board, and rounded Nyloc-style nuts with visible nylon inserts
on the component side. The threads are
geometry, so they remain visible while rotating the cards.
After regenerating, rebuild and run the browser checks before committing.

## Licenses

Card-derived models retain CERN-OHL-S-2.0; card posters retain CC-BY-SA-4.0.
Website and export scripts use GPL-3.0-or-later, consistent with the repository's
[licensing statement](../LICENSE.md). Third-party component models retain their
upstream terms and KiCad design exception. Model-viewer and Draco use Apache-2.0;
Three.js uses MIT. The deployed `NOTICE.txt` includes dependency notices and
links to the hardware source and complete project license terms.
