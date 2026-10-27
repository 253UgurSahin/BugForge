# Launch: {{app name}}

Date: {{YYYY-MM-DD}}
Angle: {{the headline: what, for whom}} {{or: no competitor data (compare skipped)}}
Buyers: {{consumers | businesses | both}}
Sells: {{one-off (deposits, orders) | subscriptions | both}}
Domain: {{TO-FILL until the user gives it}}
Pages: / {{/pricing | none: prices on the service or product list}} /privacy /terms /contact {{/dpa}}
Testimonials: {{none | the person, and the date of their written OK}}

<!-- Replace every {{...}}, then delete this comment. A business detail nobody gave you stays TO-FILL.
     Pricing: one row per tier (subscriptions) or per service or product (one-off). Delete the rows and checklist
     items that do not fit, such as the "Subscriptions" items for a booking app that takes deposits. -->

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
- pagecheck.py: {{no medium findings on 5 pages}}; low: {{...}}
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
      withdrawal form. A booking for a set date: whether the right applies (to verify), and if not, why.
- [ ] The app takes money for other businesses: who sells what.

Data processing agreement (/dpa, only when business customers' client data goes through the app):
- [ ] What is processed and for how long, security, the sub-processors, breach reports, deletion at the end.

## Dutch business basics (to verify)

Check against acm.nl (selling to consumers), the KvK and the Belastingdienst. Not legal advice.

- [ ] Business name, legal form, KvK number and, when VAT-registered, the VAT ID (btw-id) on the site.
- [ ] Contact details easy to find (footer and /contact): email, phone number, a geographic address.
- [ ] Consumers: prices include VAT and all costs; the terms, the withdrawal rules and the model withdrawal form
      can be read before payment.
- [ ] Subscriptions, consumers: one taken out online can be cancelled online, and after the first year with at most
      a month's notice.
- [ ] Consumers, where the right of withdrawal applies: the withdrawal button works during the 14 days and sends an
      email receipt (EU rule from 19 June 2026: check the date of the Dutch law on acm.nl).
- [ ] A data processing agreement with each processor (forge-secure's AVG checklist), and one offered to each
      business customer whose clients' data the app holds.

## Launch checklist (the user's steps)

- [ ] Legal pages checked by someone qualified; no TO-FILL left: `git grep -n TO-FILL -- ':!forge-work'`
- [ ] `APP_URL` or `SITE_URL` in `.env` (next and static: the value in `.env.production`) set to the real domain,
      then the image rebuilt.
- [ ] Stripe live mode: iDEAL turned on again; subscriptions: the products and prices made again, their live price
      IDs in the app's database and the Customer Portal set up again; live keys only in the server's `.env`; a
      live webhook endpoint with its own signing secret.
- [ ] iDEAL becomes Wero: read Stripe's iDEAL to Wero migration page before going live.
- [ ] Domain, TLS and a reverse proxy in front of the containers (RUN.md from forge-pack).
- [ ] SMTP with SPF, DKIM and DMARC; a support address someone reads; a backup restored once.
- [ ] The trademark checks still "to run" in brand.md.
- [ ] First users: a beta list, the places competitors' unhappy users talk (compare.md), the first 10 users
      spoken to by hand. Posts say who you are; never pose as a customer.
