# three.js, for the examples only

`three.module.js` and `three.core.js` are three.js 0.187.0 (https://threejs.org), minified with
esbuild and otherwise unchanged. MIT licence: see `LICENSE` in this folder.

The examples load it through an import map, from this folder, so the gallery works offline and asks
nothing of another host. An app that forge works on never uses this copy: there three is installed
with npm in the app itself.
