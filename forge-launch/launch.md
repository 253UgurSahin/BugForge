# Launch: {{app name}}

Date: {{YYYY-MM-DD}}
Angle: {{the headline: what, for whom}} {{or: no competitor data (compare skipped)}}
Buyers: {{consumers | businesses | both}}
Sells: {{nothing: the app is free | one-off (deposits, orders) | subscriptions | both}}
Domain: {{TO-FILL until the user gives it}}
Pages: / {{/pricing | none: prices on the service or product list | none: free}} /privacy /terms /contact {{/dpa}}
Testimonials: {{none | the person, and the date of their written OK}}
Runs at: {{http://localhost:8080, the compose stack built from this folder on branch forge/launch; service worker: none}}
Concept: {{B (Bridge at night), as the Concept line of forge-work/design/brief.md names it}}
Level: {{4 (Showpiece)}}

<!-- Replace every {{...}}, then delete this comment. A business detail nobody gave you stays TO-FILL.
     Level: the look level as `python3 ../forge/level.py get look` prints it (level.py check look reads it).
     Pricing: one row per tier (subscriptions) or per service or product (one-off). Delete the rows and checklist
     items that do not fit, such as the "Subscriptions" items for a booking app that takes deposits. Nothing sold:
     the Pricing section is one line that says so and where the site says it is free; delete the Stripe items. -->

## Landing page

In the brand voice, in the concept and at the level above. Tick each part once you saw it on the rebuilt stack.

- [ ] Hero: the angle as headline (what, for whom), one line, one button. Levels 1 to 3: a screenshot of the new
      app. Levels 4 and 5: the concept's 3D scene, loaded lazily, with a poster; the headline readable over it.
- [ ] The problem: the top two "hate" themes from feedback.md (or the user's words), in your own words.
- [ ] How it works: three steps of the core flow.
- [ ] Features: the rows with original = no first (what others lack), then the rest; only rows with clone = yes.
- [ ] Prices where they stand (Step 3 of the skill), an FAQ (price, cancelling, your data), a call to action.
- [ ] Footer: pricing (if a page), privacy, terms, contact, the business details; "Cookie settings" with a banner.
- [ ] /contact shows contact details only: a form is a new data flow (rate limit, spam check, queued email, privacy
      policy).
- [ ] Theme variables only (a missing colour is a /forge-design change), self-hosted fonts, images with width and
      height, no third-party scripts. PWA: yes: every page links the manifest and apple-touch-icon, sets theme-color.

## Pricing

| what | for whom | EUR incl. VAT (rate) | interval | trial | Stripe (test): price ID, inline or Payment Link |
| --- | --- | --- | --- | --- | --- |
| {{tier: Solo}} | {{one person}} | {{15.00 (21%)}} | {{month}} | {{14 days}} | {{price_...}} |
| {{deposit: Haircut}} | {{any client}} | {{10.00 of 45.00 (9%)}} | {{one-off}} | {{none}} | {{inline (price_data)}} |

- Competitor prices: {{from compare.md | read again YYYY-MM-DD, untrusted.py: no hits | none (compare skipped)}}
- Price feedback: {{14 of 112 reviews mention price (feedback.md) | none}}
- plan.md: {{unchanged | Payments section updated, decisions log row of YYYY-MM-DD}}
- Shown: {{on /pricing | on the service list and the booking page, with the cancelling and no-show rules}}
- Checkout by hand, test mode, iDEAL "Authorize": {{Solo ok, Team ok | Haircut deposit ok}} ({{YYYY-MM-DD}})

## Privacy, cookies and SEO

- Processors: {{Stripe, Postmark}} (trackers.py, {{YYYY-MM-DD}}); other domains seen: {{none}}; hosting: {{TO-FILL}}
- Cookie banner: {{no (session, CSRF) | yes, for ...}}. Storage: {{list | not checked}}
- Data processing agreement for business customers: {{/dpa | not needed, because ...}}
- pagecheck.py --fail-on low: {{no findings on the 5 pages in the sitemap}}; og:description, og:url and
  twitter:card: {{on every page, e2e test}}
- OG image: {{public/og.png}} (own)

## Legal pages: what each one covers (to verify)

Privacy policy (/privacy):
- [ ] Who you are and how to reach you.
- [ ] What data, why, on what legal basis, and whether giving it is required.
- [ ] How long each kind of data is kept.
- [ ] Every processor (trackers.py plus what the user named), what it gets and where; outside the EU, the
      safeguard (the EU-US Data Privacy Framework or standard contractual clauses).
- [ ] The rights (access, correction, deletion, export, restriction, objection, withdrawing consent) and where in
      the app to use them.
- [ ] Automated decisions (usually none) and the right to complain to the Autoriteit Persoonsgegevens.
- [ ] The cookies and storage items, and every other domain a page loads something from.
- [ ] Business customers' client data: which data the user controls and which they only process for the customer.

Terms (/terms), linked next to the pay button and readable before the order:
- [ ] Who you are, the service, prices and payment. Subscriptions: contract term, renewal and cancelling. One-off:
      the cancelling, refund and no-show rules (a deposit: when it is kept).
- [ ] Liability, Dutch law, complaints.
- [ ] Consumers: the 14-day right of withdrawal, what they pay when the service starts within it, and the model
      withdrawal form. A booking for a set date, or an app that sells nothing: whether the right applies (to
      verify), and if not, why.
- [ ] The app takes money for other businesses: who sells what.

Data processing agreement (/dpa, only when business customers' client data goes through the app):
- [ ] What is processed and for how long, security, the sub-processors, breach reports, deletion at the end.

## Dutch business basics (to verify)

Check against acm.nl (selling to consumers), the KvK and the Belastingdienst. Not legal advice.

- [ ] Business name, legal form, KvK number and, when VAT-registered, the VAT ID (btw-id) on the site. A hobby
      project that earns nothing may not be a business: then none of these, the reason here (to verify with the
      KvK), and a new check once it earns money (ads, donations, a paid plan).
- [ ] Contact details easy to find (footer and /contact): email, phone number, a geographic address.
- [ ] Consumers: prices include VAT and all costs; the terms, the withdrawal rules and the model withdrawal form
      can be read before payment.
- [ ] Subscriptions, consumers: one taken out online can be cancelled online, and after the first year with at most
      a month's notice.
- [ ] Consumers, where the right of withdrawal applies: the withdrawal button works during the 14 days and sends an
      email receipt (EU rule from 19 June 2026: check the date of the Dutch law on acm.nl).
- [ ] A data processing agreement with each processor (the AVG checklist of /forge-check secure), and one offered to each
      business customer whose clients' data the app holds.

## Launch checklist (the user's steps)

- [ ] Legal pages checked by someone qualified; no TO-FILL left: `git grep -n TO-FILL -- ':!forge-work'`
- [ ] The address setting set to the real domain, then the image rebuilt: laravel `APP_URL` or django `SITE_URL`
      in `.env`, next `NEXT_PUBLIC_SITE_URL` or static `VITE_SITE_URL` in `.env.production`. Canonical links,
      sharing tags and the sitemap follow it.
- [ ] Stripe live mode: iDEAL turned on again; subscriptions: the products and prices made again, their live price
      IDs in the app's database and the Customer Portal set up again; live keys only in the server's `.env`; a
      live webhook endpoint with its own signing secret.
- [ ] iDEAL becomes Wero: read Stripe's iDEAL to Wero migration page before going live.
- [ ] Domain, TLS and a reverse proxy in front of the containers (RUN.md from /forge-build pack).
- [ ] SMTP with SPF, DKIM and DMARC; a support address someone reads; a backup restored once.
- [ ] The trademark checks still "to run" in brand.md.
- [ ] First users: a beta list, the places competitors' unhappy users talk (compare.md), the first 10 users
      spoken to by hand. Posts say who you are; never pose as a customer.

## Shown

What the user sees on their own screen (rules.md section 9 of the forge pack).

- Before and after: forge-work/launch/shots/before and after; changed.py: {{VISIBLE CHANGE, 41% of home-1440-light.png}}
- Moves: {{changed.py --moves on the frames of /: something moves | level 1: no frames taken}}
- Clip: {{forge-work/launch/shots/after/home-1440.webm | none (level 1)}}
- motioncount.py --level auto: {{exit 0}}; level.py check look: {{exit 0}}
- Told the user: {{the branch, the address, where to look first, the reduced-motion setting, how to go back}}
