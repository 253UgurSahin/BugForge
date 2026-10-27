# Recon: {{app}} ({{platform}})

Product: {{product name}}   Company: {{company name}}   Domains: {{app.example, example.com}}
Slice: {{the part being rebuilt, the core loop first}}
For: {{who the rebuild is for}}
Date: {{YYYY-MM-DD}}
Account terms: {{checked YYYY-MM-DD: no clause against building a competing product}}

<!-- Replace every {{...}}, then delete this comment. Write "none seen" rather than leaving a
     section empty. Quotes from the app's pages go in a quote block with their URL (rules.md 1).
     Account terms may also be "public sources only, because ..." or "n/a: the app has no
     accounts (site terms checked YYYY-MM-DD, or not reachable)". -->

## Sources

| # | source | URL | read on | how | untrusted.py | notes |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | help center | {{https://...}} | {{YYYY-MM-DD}} | {{fetched, user's copy or secondhand}} | {{no hits}} | {{...}} |

Not reached: {{URL and why, or none}}

## Core loop

{{One sentence: the thing people pay for.}}

## Screens

| ID | screen | route or how to reach it | purpose | key components | states seen | screenshot (state) |
| --- | --- | --- | --- | --- | --- | --- |
| S01 | {{...}} | {{/...}} | {{...}} | {{...}} | {{empty, filled, error}} | {{S01.png, S01-mobile.png (logged in, 3 items) or none}} |

## Flows

```
F01 {{goal}}
    S01 -> S02 -> S03
    happy path clicks: {{n}}
    edge: {{cases seen or described in the help docs}}
```

## Components

| component | variants | states | used on |
| --- | --- | --- | --- |
| Button | primary, secondary, ghost, danger | default, hover, focus, disabled, loading | all |

## Inferred data model

```
{{Entity}}  {{fields}}
            evidence: {{screen IDs, help articles, API docs}}
            confidence: {{high | medium | guess}}
```

Relationships: {{User 1-n EventType, EventType 1-n Booking, ...}}

## Feature matrix

In `features.csv`. Must: {{n}}, should: {{n}}, could: {{n}}, skip: {{n}}.

## Out of scope (cannot or should not be cloned)

- {{licensed content, the network and its users, partner deals: each a skip row too}}

## Size

Screens {{n}}, flows {{n}}, entities {{n}}. Hard parts: {{list}}. Size: {{S | M | L | XL}}.
