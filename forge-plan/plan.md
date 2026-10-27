# Plan: {{app name}}

Profile: {{laravel | django | next | static}}
PWA: {{yes | no}}
Mode: {{clone | idea}}
Date: {{YYYY-MM-DD}}

<!-- Replace every {{...}}, then delete this comment. Profile and PWA: the label plus exactly one
     word from its list, at the start of the line. The forge gate reads them. -->

## Why

{{Two or three lines: what the user said, which row of "How to pick a profile" fits, what was not
chosen and why. Why it is or is not a PWA.}}

## Stack and versions

Versions checked {{YYYY-MM-DD}}.

| part | choice | version or image |
| --- | --- | --- |
| framework | {{plus the starter kit (laravel) or the Vite template (static)}} | |
| runtime | | |
| database | | |
| auth | | |
| styling | {{Tailwind CSS or plain CSS}} | |
| unit tests | | |
| end-to-end tests | Playwright | |
| payments | {{Stripe test mode, Payment Links, or none}} | |
| email | {{SMTP (Mailpit in development), or none}} | |
| background jobs | | |

Compose services: {{app, web, db, mailpit, worker}}

## Screens and flows

{{Clone mode: "In recon.md", plus only the screens and flows this plan adds, numbered on from
recon's last ID. Idea mode: every screen and flow.}}

| ID | screen | route | purpose | key components | states |
| --- | --- | --- | --- | --- | --- |
| {{S01}} | {{book an appointment}} | {{/book}} | {{...}} | {{...}} | {{empty, filled, error, no permission}} |

```
{{F01 book an appointment
    S01 -> S02 -> S03
    happy path clicks: 4
    edge: slot taken meanwhile, payment fails, back button on the bank page}}
```

## Entities and schema

| table | owner | what it holds | deleted when |
| --- | --- | --- | --- |
| {{bookings}} | {{user_id}} | {{...}} | {{the user deletes their account}} |

```sql
{{the first migration, as SQL or in the profile's syntax}}
```

Rules the database enforces:
- {{no double booking}}: {{the method from profiles.md for this database}}

## Routes and API

| method | path | what it does | who may call | input | output | flow |
| --- | --- | --- | --- | --- | --- | --- |
| {{GET}} | {{/bookings}} | {{list my bookings}} | {{logged in, own rows only}} | {{page}} | {{list}} | {{F02}} |
| {{POST}} | {{/bookings/:id/cancel}} | {{cancel, refund by the rule}} | {{the booker, own rows only}} | {{id}} | {{status}} | {{F03}} |
| {{POST}} | {{/stripe/webhook}} | {{payment and refund events}} | {{Stripe, signature checked}} | {{event}} | {{200}} | {{F01}} |

## Auth and roles

- Who may create an account: {{anyone (public sign-up) | only staff (no sign-up page; accounts made by a command)}}
- Sign up, log in, email verification, password reset: {{how, per the profile}}
- Roles: {{none | owner, admin, member}}. Access check: {{the one function or policy}}
- Account deletion and data export: {{how}}

## Payments

{{None, or the lines below.}}
- Money goes to: {{the user's own Stripe account}}
- What is paid for: {{...}}; {{one-off | subscription | deposit}}; prices in EUR incl. VAT: {{...}}
- Cancelling and refunds: {{deadline, full or partial, who starts it}}
- No-shows: {{what happens, or n/a}}
- How: {{Stripe Checkout with iDEAL in test mode, webhook at /stripe/webhook | Payment Links (static)}}

## Emails

| email | sent when | to | queued? |
| --- | --- | --- | --- |
| {{verify your email}} | {{sign up}} | {{the new user}} | {{yes}} |

## Background jobs

| job | trigger or schedule (UTC) | what it does | on failure |
| --- | --- | --- | --- |
| {{send reminders}} | {{every 15 minutes}} | {{...}} | {{retry 3 times, then log}} |

## The parts that bite

- Time zones and daylight saving: {{...}}
- Idempotent webhooks: {{...}}
- Races (two people, one slot; a double click on pay): {{...}}
- Holding a slot or stock during payment: {{...}}
- Uploads (size, type, file names, where they live): {{...}}
- GDPR deletion and export (and what tax law makes you keep): {{...}}
- Rate limits (login, sign up, anything that sends email): {{...}}
- Other (search, realtime, multi-tenancy, the PWA rules): {{...}}

## Build order

1. Vertical slice: {{the core loop end to end; its screens, tables and routes}}
2. Must-haves: {{..., with each must C-ID row next to the feature it changes}}
3. Should-haves: {{...}}
4. Could-haves: {{...}}
5. Fixes from compare (the other C-IDs): {{...}}

Not building: {{rows with clone=skip, and why}}

## Decisions log

| date | decision | why | rejected |
| --- | --- | --- | --- |
| {{YYYY-MM-DD}} | {{profile laravel}} | {{...}} | {{django: ...}} |
