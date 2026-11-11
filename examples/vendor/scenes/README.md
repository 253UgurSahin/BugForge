# The scene kit, for the examples only

A copy of `forge-design/scenes/` (the 3D scene kit of forge-design), so the gallery runs from this
folder alone. `tests/test_examples.py` checks that every file here equals the one in
`forge-design/scenes/`: change the kit there, then copy it here.

The pages load `three` through an import map that points at `../vendor/three/three.module.js`.
