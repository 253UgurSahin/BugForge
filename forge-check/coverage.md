# Coverage: what the security check looked at, and what it did not

forge-check secure copies this table into `forge-work/security.md` under `## Coverage` and fills in the
last column for this project. It follows the OWASP Top 10 (the 2021 edition: check owasp.org for a
newer one), the list most teams and auditors use to ask "did you look at...?". A row is honest only
when it says what was not looked at: a scan that did not run is `not checked`, never `ok`.

Result is one of: `ok` (checked, nothing found), a list of finding IDs (`X003, X007`), `not checked:
why`, or `does not apply: why`.

| OWASP 2021 | in plain words | what forge-check secure runs for it | result |
| --- | --- | --- | --- |
| A01 Broken access control | one user reaches another user's data or an admin's page | authz.py with two users, flowcheck.py (handlers with no owner check), the second-user spec of forge-check test | |
| A02 Cryptographic failures | secrets, passwords or traffic poorly protected | secretscan.py, flowcheck.py (weak hashes and tokens, TLS checks switched off), headers.py (HSTS) | |
| A03 Injection | input ends up in SQL, a shell, a page or a file path | codecheck.py, flowcheck.py (input followed to a risky call), probe.py (reflected input, a database error after a quote) | |
| A04 Insecure design | the flow itself can be abused: prices from the browser, no limit on attempts | the framework and Stripe checks in frameworks.md, by reading the code | |
| A05 Security misconfiguration | debug on, default settings, files served that should not be | headers.py, probe.py (exposed files, debug pages, directory listing, CORS, TRACE), the framework checks, packcheck.py for the containers | |
| A06 Vulnerable and outdated components | a dependency with a known hole, or one nobody can vouch for | deps.py (known holes), supply.py (lockfiles, floating versions, odd sources, look-alike names, licences, SBOM) | |
| A07 Identification and authentication failures | weak login, sessions that leak or never end | the framework checks (the stack's own auth, never home-made), headers.py (cookie flags), forge-check test's login cases (too many attempts, expired session) | |
| A08 Software and data integrity failures | code or data trusted without a check: unsigned webhooks, unsafe deserialising | codecheck.py and flowcheck.py (deserialising), the Stripe webhook check, supply.py (integrity hashes, install scripts) | |
| A09 Security logging and monitoring failures | nobody would notice an attack, or the log itself leaks | flowcheck.py (secrets and personal data written to a log); whether anyone reads the logs is a question for the user | |
| A10 Server-side request forgery | the server fetches a URL an attacker chose | flowcheck.py (request input used as the URL of an outgoing call) | |
| Privacy (AVG/GDPR) | personal data collected, shared or kept without a basis | trackers.py and the AVG/GDPR checklist | |

What no script here can show, and so always goes under `## Not checked` as a question for the user:
who has access to the server and the database, whether backups are tested, whether logs are read,
and whether the people involved know what to do when something leaks.
