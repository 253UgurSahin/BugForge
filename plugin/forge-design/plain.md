# Plain: clear for everyone

Every screen forge designs or builds is clear to someone who has never seen the app and is not good
with computers: think of a grandmother of 75 with reading glasses. She is a capable adult who has run
a household, a business or a career; she is new to this app, not slow. So plain never means childish:
the words are simple and exact, and the tone stays professional, as a good bank, doctor's office or
government letter writes. This holds for every app, at every look level and in every part (design,
build, motion, dashboard, improve, docs). A higher look level adds beauty, never confusion: an effect
sits behind the words and the buttons, never on top of them, and never moves, hides or delays the
main button.

The test for every screen: **within 5 seconds, can she say what this screen is for and what to press?**
And for every sentence: **would a professional firm put it in a letter to her?**

## The rules

| # | rule | good | not | checked by |
| --- | --- | --- | --- | --- |
| 1 | Every button says what it does, with a verb and the thing | "Afspraak maken", "Save address" | "Verzenden", "OK", "Submit", "Klik hier" | plaincheck `vague_label` |
| 2 | One main button per screen: large, in the accent colour, where the eye lands | one filled button; the others outlined or as links | three filled buttons side by side | review, plain walk |
| 3 | Never an icon on its own: icon and word together | 🗑 "Verwijderen" | a lone bin, a lone ⋯ or ☰ | plaincheck `icon_only` |
| 4 | Every field has a label above it that stays visible while typing | "Telefoonnummer" above the box | only a grey placeholder inside it | plaincheck `placeholder_label` |
| 5 | Plain words at language level B1, the user's own words for things | "Je wachtwoord klopt niet" | "Authenticatie mislukt", "Error 401", "undefined" | plaincheck `jargon`, `leak` |
| 6 | Text large enough to read without effort | body text 18px (never under 16px), line height 1.5, lines under 75 characters | 13px grey on grey | review, plain walk |
| 7 | Targets large enough for a finger | buttons and links at least 44 by 44px, 8px apart | a 20px icon next to another | walk (`small_targets`), plain walk |
| 8 | A long form goes in steps, and says where you are | "Stap 2 van 3" and a bar; at most 5 or 6 fields per step | 15 fields on one page | plaincheck `long_form` |
| 9 | An error says what to do, next to the field, in words | "Vul een telefoonnummer in, bijv. 06 12345678" under the field | a red banner at the top: "Invalid input" | plain walk |
| 10 | An empty screen says what to do next, with the button for it | "Nog geen afspraken. Maak je eerste afspraak" + button | a blank table, or "No data" | plain walk |
| 11 | Every action is confirmed in words that repeat what happened | "Je afspraak staat op 3 mei om 14:00." | nothing, "Success", or "Yay, gelukt!! 🎉" | plain walk |
| 12 | Undo instead of "Are you sure?" where it can be undone | "Verwijderd. Ongedaan maken" for 10 seconds | a dialog after every click | review |
| 13 | A short menu that shows where you are, and always a way back | 5 items or fewer, the current one marked, "Terug" or the logo home | 12 menu items, no marked page | plaincheck `long_menu`, plain walk |
| 14 | Things look like what they are | buttons look pressable, links are underlined in text, nothing else looks like a button | grey text that turns out to be a link | review, plain walk |
| 15 | Colour is never the only signal | a red field also has an icon and a sentence | only a red border | review, contrast.py |
| 16 | Simple, never childish: a calm, professional tone | "Uw betaling is ontvangen. U ontvangt de factuur per e-mail." | "Hoera!!", "Oeps, foutje!", emoji in buttons and messages, "simpelweg", "gewoon even", talking down | plaincheck `tone`, review |

Contrast stays WCAG AA (`../forge-design/contrast.py`), focus rings stay visible, and everything that
moves has its calm version (`../forge-design/motion.md`). Those rules are elsewhere; they hold here too.

## Words

Write as a good professional writes to a client: short sentences, one idea each, polite and exact,
at language level B1. Simple words are not informal words: no exclamation marks, jokes, emoji, baby
talk or slang, no "simpelweg" or "gewoon even" (they tell her it should be easy), and nothing that
sounds like talking to a child. "Je" or "u" as the app and its audience already do (a bank, a
practice or a government service: "u"); never both. The user's words for things, never the
database's: "afspraak", not "booking entity"; "klant", not "user record". The words of her own trade
or life stay as they are, even when long: "factuur", "IBAN", "btw", "machtiging", "huisartsenpraktijk".
Jargon means the computer's words (sessie, token, server), not hers.

| instead of | write |
| --- | --- |
| Verzenden, Submit, OK, Doorgaan (on a form) | what happens: "Afspraak maken", "Bestelling plaatsen", "Opslaan" |
| Klik hier, Lees meer, Meer | the place it goes: "Bekijk de prijzen", "Lees hoe het werkt" |
| Authenticatie mislukt, 401 | "Je e-mailadres of wachtwoord klopt niet. Probeer het opnieuw." |
| Er is een fout opgetreden | what went wrong and what to do: "We konden je afspraak niet opslaan. Probeer het over een minuut opnieuw." |
| Sessie verlopen | "U bent een tijd niet actief geweest. Log opnieuw in; uw gegevens zijn bewaard." |
| Invalid input, Ongeldige invoer | the rule: "Een postcode heeft 4 cijfers en 2 letters, bijv. 1234 AB" |
| No data, Geen resultaten | the next step: "Er zijn nog geen klanten. Voeg uw eerste klant toe." |
| Oeps! Er ging iets mis 😕 | calm and exact: "Uw afspraak is niet opgeslagen. Probeer het over een minuut opnieuw." |
| Hoera, gelukt!! | the fact: "Uw afspraak staat op 3 mei om 14:00." |

`../forge-check/plain.json` holds the word lists plaincheck.py looks for, in English and Dutch.

## Patterns

- **The header.** The app's name, one sentence that says what it does for her, and one big button for
  the main task. The effect of the header level (`../forge/levels.md`, "header") lives behind these,
  with enough contrast under the words in every frame.
- **The main screen.** What she came for is the first thing she sees, at the top, with its button. The
  rest below it, in order of how often it is used.
- **Forms.** One column; the label above each field; only the fields that are needed; a field marked
  "(niet verplicht)" when it is optional, not a star for the required ones; the keyboard that fits
  (`type="tel"`, `type="email"`, `inputmode="numeric"`); the button says the result.
- **Lists and tables.** Words for the column names, the important column first, a search box when
  there are more than 20 rows, and the empty state of rule 10.
- **Dashboards.** At most 5 numbers, each with a sentence that says what it means ("12 afspraken deze
  week, 3 meer dan vorige week"); plain bars and lines; the table with the same data next to a chart.
- **Navigation.** The same place on every screen, words with every icon, the current page marked.
  On a phone: a bar at the bottom with at most 5 items, or a menu button that says "Menu".
- **Waiting.** Anything over a second shows what it is doing: "Je afspraak wordt opgeslagen…".

## How it is checked

1. `python3 ../forge-check/plaincheck.py <pages or URLs>`: the rules a page's HTML shows by itself
   (1, 3, 4, 5, 8, 13), with a fix for each. It runs after the build of every screen and in
   `/forge-check test` at every test level.
2. The walk (`../forge-check/walk.md`) measures targets and contrast at three widths.
3. The plain walk (`../forge-check/steps/test.md`, from test level 2): a fresh tester who never saw the
   app does the main tasks from screenshots alone, as the grandmother above, and answers the 5-second
   test for each screen. What she cannot do is a bug in `forge-work/bugs.md`.
4. The design review (`../forge-design/review.md`) scores every screen on these rules next to the brief.
