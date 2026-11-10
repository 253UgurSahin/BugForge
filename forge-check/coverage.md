# Coverage: what the security check looked at, and what it did not

`/forge-check secure` copies this table into `forge-work/security.md` under `## Coverage` from
level 3 up, with two columns: the OWASP row and the result for this project. It follows the OWASP
Top 10 (the 2021 edition: check owasp.org for a newer one), the list most teams and auditors use to
ask "did you look at...?". A row is honest only when it says what was not looked at: a scan that
did not run is `not checked`, never `ok`.

Result is one of: `ok` (checked, nothing found), a list of finding IDs (`X003, X007`), `not checked:
why`, or `does not apply: why`. The last column says what each level adds to the row (a level
includes the ones below it). At levels 1 and 2 the table is not filled in: those levels run only
on their own, and their report says so. From level 3 every row has a check; a result names what
ran at the level on record, and what a higher level would add, for example `ok: flowcheck.py (no
handler without an owner check); authz.py is level 4`.

| OWASP 2021 | in plain words | what `/forge-check secure` runs for it, by level |
| --- | --- | --- |
| A01 Broken access control | one user reaches another user's data or an admin's page | 3: flowcheck.py (handlers with no owner check), the second-user spec of `/forge-check test` when it ran. 4: authz.py with two users. 5: the access matrix of every route against every role |
| A02 Cryptographic failures | secrets, passwords or traffic poorly protected | 1: secretscan.py. 2: headers.py (HSTS). 3: flowcheck.py (weak hashes and tokens, TLS checks switched off). 5: the git history scanned for secrets |
| A03 Injection | input ends up in SQL, a shell, a page or a file path | 1: codecheck.py. 3: flowcheck.py (input followed to a risky call). 4: probe.py (reflected input, a database error after a quote), semgrep when installed |
| A04 Insecure design | the flow itself can be abused: prices from the browser, no limit on attempts | 3: the framework and Stripe checks in frameworks.md, by reading the code. 5: the threat model per entry point, the abuse and rate-limit cases |
| A05 Security misconfiguration | debug on, default settings, files served that should not be | 2: headers.py. 3: the framework checks. 4: probe.py (exposed files, debug pages, directory listing, CORS, TRACE), the container checks with packcheck.py |
| A06 Vulnerable and outdated components | a dependency with a known hole, or one nobody can vouch for | 2: deps.py (known holes). 3: supply.py (lockfiles, floating versions, odd sources, look-alike names, licences, SBOM). 5: the licence review |
| A07 Identification and authentication failures | weak login, sessions that leak or never end | 2: headers.py (cookie flags). 3: the framework checks (the stack's own auth, never home-made), the login cases of `/forge-check test` when they ran (too many attempts, expired session). 5: the threat model of login and session, the rate limit on login and password reset |
| A08 Software and data integrity failures | code or data trusted without a check: unsigned webhooks, unsafe deserialising | 1: codecheck.py (deserialising). 3: flowcheck.py, the Stripe webhook check, supply.py (integrity hashes, install scripts). 5: webhooks replayed, in the abuse cases |
| A09 Security logging and monitoring failures | nobody would notice an attack, or the log itself leaks | 3: flowcheck.py (secrets and personal data written to a log); whether anyone reads the logs is a question for the user. 5: per entry point in the threat model, whether an attack leaves a trace |
| A10 Server-side request forgery | the server fetches a URL an attacker chose | 3: flowcheck.py (request input used as the URL of an outgoing call). 5: each outgoing call in the threat model |
| Privacy (AVG/GDPR) | personal data collected, shared or kept without a basis | 2: trackers.py. 3: the AVG/GDPR checklist |

What no script here can show, and so always goes under `## Not checked` as a question for the user:
who has access to the server and the database, whether backups are tested, whether logs are read,
and whether the people involved know what to do when something leaks.
