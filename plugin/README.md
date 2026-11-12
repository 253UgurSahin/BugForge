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

## Data and network

BugForge has no server of its own: nothing is sent to or kept by BugForge. Everything it writes, such
as plans, reports, screenshots and your business details for a privacy policy, stays in your project's
`forge-work/` folder and in your own app. It reads your code, your app's database and pages, and, for
recon, an account of your own that you sign in to. Passwords and keys are never printed or stored by it.

The skills only reach these outside services, and only for the step named:

| service | when |
| --- | --- |
| the sites and apps you name | recon, compare and inspect read their public pages at human speed; recon may also read pages behind your own login |
| review sites (app stores and Apple's reviews feed, Trustpilot, Kiyoh, G2, Capterra, Reddit, Tweakers, Hacker News via hn.algolia.com) | compare, to collect what users say about competitors |
| registry.npmjs.org, PyPI, Packagist, osv.dev | dependency and vulnerability checks (`npm audit`, `pip-audit`) |
| endoflife.date | audit, to check whether a framework or database version still gets updates |
| npm and the official installers (create-next-app, Vite, Laravel, Playwright, Lighthouse) | downloads the tools a step needs, after you agree |
| Stripe (test mode) | payments you build into your own app, with your own test keys |

Active security tests (probes, the access check) run only against your own app, on hosts you list.

Privacy: https://github.com/253UgurSahin/BugForge/blob/main/PRIVACY.md

## More

The full documentation, the gallery with every look level as a moving preview, and the tests are in
the repo: https://github.com/253UgurSahin/BugForge

MIT licensed, see `LICENSE`.
