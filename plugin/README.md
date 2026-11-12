# BugForge

Claude skills that turn an app idea, a URL or a repo into a working, tested, container-ready web app,
and that audit and improve apps you already have, with a look from the app's own world at a level from
1 (Subtle) to 5 (Cinematic), up to living 3D. Clean-room and safe by default: nothing is deployed, and
every change shows on your own localhost first.

| skill | what it does |
| --- | --- |
| `/forge` | Runs a whole project phase by phase, with a gate and your go after each phase, or in auto mode. |
| `/forge-research` | recon and compare: maps an app from its public pages, and puts competitors side by side. |
| `/forge-plan` | The stack profile (Laravel, Django, Next.js or a static site), schema, routes and build order. |
| `/forge-design` | design, brand, dashboard and motion: three moving concepts, then the look built into the app. |
| `/forge-build` | build and pack: scaffolds with the official installer, builds screen by screen, fits the containers. |
| `/forge-check` | test, diff, secure, audit and inspect: tests at your level and the security gate. |
| `/forge-improve` | Fixes what the checks found and the look you pick, on a new branch, one commit each. |
| `/forge-launch` | Landing page, prices in EUR with VAT, privacy policy, terms, basic SEO and a launch checklist. |

The skills call each other's scripts by paths like `../forge-check/scope.py`, so they belong together:
install the plugin, or copy all eight folders.

## Install

In Claude Code:

```
/plugin marketplace add 253UgurSahin/BugForge
```

```
/plugin install bugforge@bugforge
```

## More

The full documentation, the gallery with every look level as a moving preview, and the tests are in
the repo: https://github.com/253UgurSahin/BugForge

MIT licensed, see `LICENSE`.
