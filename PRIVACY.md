# Privacy

BugForge is a set of Claude skills (the `plugin/` folder of this repository). It has no server, no
account and no analytics of its own. This page says what it does with data when Claude runs it.

## What it reads

- Your project: its code, its configuration and, for tests and dashboards, its database and pages on
  your own computer (localhost).
- Pages of sites and apps you name: recon, compare and inspect read their public pages; recon can also
  read pages behind an account of your own that you sign in to yourself.
- Reviews of competitors on public review sites, for compare.

This can include personal data, such as the names and email addresses in your app's database, or your
own business details (name, address, KvK number) that you give for a privacy policy or terms.

## What it stores

Everything BugForge writes stays in your own project: plans, reports, screenshots and test results in
its `forge-work/` folder, and the code, pages and documents it builds into your app. Passwords and keys
are never printed, and never written to a file that git tracks. Nothing is sent to or kept by BugForge
or its author.

## What it sends

BugForge sends no data to its author. The outside services the skills reach, and the step that reaches
them, are listed in [plugin/README.md](plugin/README.md#data-and-network): the sites you name, review
sites, package registries and vulnerability databases, endoflife.date, the official installers, and
Stripe in test mode with your own keys. Claude itself, and any connector you use with it, handle data
under Anthropic's and that service's own terms.

## Retention and deletion

BugForge keeps nothing. To remove what it wrote, delete the `forge-work/` folder in your project (it is
never committed) and revert the changes you do not want.

## Children

BugForge is a tool for building software and is not intended for users under 18.

## Contact

Questions: open an issue at https://github.com/253UgurSahin/BugForge/issues
