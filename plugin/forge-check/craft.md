# Code craft: the rules an audit reads code by

How well the code is made, apart from whether it works today: can a new developer read it, change it
without fear, and test it? The rules come from five books (sources at the end), in our own words. Each
has an ID that audit findings name (`where: app/Billing.php:40 (CR-F1)`).

Two rules come before all others:

- **Leave it cleaner than you found it.** A craft finding is fixed the next time that code is touched,
  in small steps, with a test around it first. Never a big rewrite because a rule says so.
- **A rule serves the reader.** A pattern or an abstraction that removes no real problem is a cost,
  not a gain. Name the problem a finding causes, never only the rule.

`python3 ../forge-check/craftcheck.py .` measures what a scan can see (marked **scan** below); the rest
you find by reading the code, starting with the files that change most (`git log --format= --name-only
| sort | uniq -c | sort -rn | head -20`) and the code around money, login and personal data.

## Names

| ID | look for | fix | source |
| --- | --- | --- | --- |
| CR-N1 | names that hide what a thing is for: `d`, `data2`, `tmp`, `handle()`, `doStuff()` | a name that says why it exists and how it is used | Clean Code ch. 2 |
| CR-N2 | names that mislead or encode: `accountList` that is a map, `strName`, `IFoo`, `m_` | the plain name of what it is | Clean Code ch. 2 |
| CR-N3 | one concept, many words (`fetch`, `get`, `retrieve` for the same thing), or one word for two concepts | one word per concept, used everywhere | Clean Code ch. 2 |
| CR-N4 | code words where the business has its own: `Item` where everyone says `Booking` | the domain's own words, the same as in the glossary | Clean Code ch. 2; Larman ch. 9 (domain model) |

## Functions

| ID | look for | fix | source |
| --- | --- | --- | --- |
| CR-F1 **scan** | functions over 30 lines (low), over 60 (medium) | small functions that each do one thing, named for it; one level of abstraction per function | Clean Code ch. 3 |
| CR-F2 **scan** | more than 3 arguments (low), more than 5 (medium) | group values that belong together in one object, or split the function | Clean Code ch. 3 |
| CR-F3 **scan** | a true/false argument that switches what the function does | two functions with names that say what each does | Clean Code ch. 3 |
| CR-F4 **scan** | nesting deeper than 3 levels (low), 4 (medium) | guard clauses that return early; inner blocks moved into functions | Clean Code ch. 3 |
| CR-F5 | a function that answers a question and also changes something (`isValid()` that saves) | split commands from queries | Clean Code ch. 3 (command query separation) |
| CR-F6 | hidden side effects: a `check` that also logs in, sends mail or changes global state | do the side effect in its own, named step | Clean Code ch. 3 |

## Comments

| ID | look for | fix | source |
| --- | --- | --- | --- |
| CR-K1 | comments that repeat the code, or explain a muddle the code could make clear | a better name or a small function; keep comments for why, warnings and public API | Clean Code ch. 4 |
| CR-K2 **scan** | commented-out code | delete it; git keeps history | Clean Code ch. 4 |
| CR-K3 | change logs, author lines and closing-brace comments inside the code | git log and blame; shorter blocks | Clean Code ch. 4 |
| CR-K4 | a public API or a tricky rule (money, time zones, rounding) with no word of why | one short comment that says why, next to the rule | Clean Code ch. 4 |

## Objects, data and errors

| ID | look for | fix | source |
| --- | --- | --- | --- |
| CR-O1 **scan** | chains through other objects: `order.getCustomer().getAddress().getCity()` | ask the nearest object; tell, don't ask (Law of Demeter) | Clean Code ch. 6; Head First ch. 7 (least knowledge) |
| CR-O2 **scan** | a long switch or if/else chain, above all one that picks by type or status and appears in more places | polymorphism, a Strategy or State object, or a lookup table, so a new case needs no change here | Clean Code ch. 3 and 6; APPP ch. 9 (OCP); Larman ch. 25 (Polymorphism) |
| CR-O3 | objects that are only bags of public data, with the rules spread over services that reach in | move the rule to the object that holds the data (Information Expert) | Clean Code ch. 6; Larman ch. 17 |
| CR-E1 **scan** | errors caught and ignored (empty catch, `except: pass`) | handle, log with context, or let it reach a place that tells the user | Clean Code ch. 7 |
| CR-E2 | error codes and magic return values (`-1`, `false`, `""`) that callers forget to check | exceptions, or a result type the language supports | Clean Code ch. 7 |
| CR-E3 | functions that return or accept `null` where a value is expected, with null checks everywhere | an empty list, a default, or a Null Object | Clean Code ch. 7; APPP ch. 25 (Null Object) |
| CR-B1 | a third-party API (payments, mail, storage) called from many places | one small wrapper of your own: an Adapter, Facade or Gateway, with its own tests | Clean Code ch. 8; APPP ch. 33-34; GoF (Adapter, Facade) |

## Classes and responsibilities

| ID | look for | fix | source |
| --- | --- | --- | --- |
| CR-C1 **scan** | classes with more than 20 methods (low), 35 (medium), or one name with "Manager", "Helper", "Util" doing many jobs | split by responsibility: one reason to change per class (SRP) | Clean Code ch. 10; APPP ch. 8 |
| CR-C2 | a class whose methods each use a different part of its fields (low cohesion) | split it where the fields split | Clean Code ch. 10; Larman ch. 17 (High Cohesion) |
| CR-C3 | a controller or view that holds business rules (prices, permissions, state changes) | a thin controller that delegates to the domain (GRASP Controller, model-view separation) | Larman ch. 13 and 17 |
| CR-C4 | objects created all over the code with `new`, so nothing can be swapped or tested | create where the data is (Creator), or inject what a class needs (dependency injection) | Larman ch. 17; Clean Code ch. 11 |

## SOLID

| ID | principle | look for | source |
| --- | --- | --- | --- |
| CR-S1 | Single Responsibility | one class or module that changes for unrelated reasons (layout and tax rules in one file) | APPP ch. 8 |
| CR-S2 | Open/Closed | adding a case means editing the same switch in several places | APPP ch. 9 |
| CR-S3 | Liskov Substitution | a subclass that throws "not supported", ignores a method or needs `instanceof` checks by its callers | APPP ch. 10 |
| CR-S4 | Interface Segregation | one fat interface whose clients each use a small part, with empty implementations | APPP ch. 12 |
| CR-S5 | Dependency Inversion | business rules that import the database, HTTP client or framework directly | APPP ch. 11 |

## Structure and architecture

| ID | look for | fix | source |
| --- | --- | --- | --- |
| CR-A1 | no clear layers: views query the database, models send mail, the domain imports the framework | layers (UI, application, domain, infrastructure) that only call downward | Larman ch. 13 and 34; Clean Code ch. 11 |
| CR-A2 | cycles between modules or packages (`a` imports `b` imports `a`) | break the cycle with an interface or by moving the shared part (Acyclic Dependencies) | APPP ch. 28 |
| CR-A3 | stable, much-used modules that depend on volatile ones | depend toward stability; keep stable modules abstract | APPP ch. 28 (SDP, SAP) |
| CR-A4 | classes that always change together living far apart | keep what changes together in one package (Common Closure) | APPP ch. 28 |
| CR-A5 | configuration, construction and wiring mixed into business code | build the object graph in one place at start-up | Clean Code ch. 11 |

## General

| ID | look for | fix | source |
| --- | --- | --- | --- |
| CR-G1 **scan** | duplicated blocks of 6 or more lines, above all business rules | one function or class, called from both places | Clean Code ch. 3, 12 and 17 |
| CR-G2 | dead code: functions, routes, flags and files nothing uses | delete them | Clean Code ch. 17 |
| CR-G3 | magic numbers and strings for rules (`* 0.21`, `if status == 3`) | a named constant or enum | Clean Code ch. 17 |
| CR-G4 | each file in its own style | one formatter and linter for the project, run in CI | Clean Code ch. 5 |
| CR-G5 | tests that are slow, depend on each other or on the clock, or test many things at once | fast, independent, repeatable tests with one concept each (F.I.R.S.T.) | Clean Code ch. 9; APPP ch. 4 |

## When a smell asks for a pattern

A pattern is a known answer to a known problem. Name it only when the code shows the problem; a
pattern added "to be ready" is over-design (APPP ch. 20). The OO principles behind them: encapsulate
what varies, prefer composition over inheritance, program to an interface, keep objects loosely
coupled (Head First ch. 1 and 2; GoF ch. 1).

| what you see | pattern that answers it | source |
| --- | --- | --- |
| the same switch on type or status in several places | Strategy, State, or plain polymorphism | GoF; Head First ch. 1 and 10; APPP ch. 22 and 36 |
| objects built in many steps, constructors with many arguments | Builder, Factory Method | GoF; Head First ch. 4 |
| families of related objects chosen together (per tenant, per country) | Abstract Factory | GoF; Larman ch. 35 |
| code that polls, or one change that must update many parts | Observer (events) | GoF; Head First ch. 2; APPP ch. 32 |
| a third-party API spread through the code, or one with an awkward shape | Adapter, Facade, Gateway | GoF; Head First ch. 7; APPP ch. 34 |
| null checks for "nothing there" all over | Null Object | APPP ch. 25 |
| the same steps with small differences in several classes | Template Method | GoF; Head First ch. 8; APPP ch. 22 |
| actions to queue, log, retry or undo | Command | GoF; Head First ch. 6; APPP ch. 21 |
| extra behaviour (caching, logging, retries) by subclass after subclass | Decorator | GoF; Head First ch. 3 |
| a tree of parts and wholes (menus, categories, bundles) | Composite | GoF; Head First ch. 9; APPP ch. 31 |
| a slow, remote or guarded object used as if it were local | Proxy | GoF; Head First ch. 11; APPP ch. 34 |
| global state through singletons that tests cannot replace | dependency injection; a Singleton only for one true resource | GoF; Head First ch. 5; APPP ch. 24 |

## How the audit uses this

1. `python3 ../forge-check/craftcheck.py . --json`: the **scan** rules, with file and line. Read
   each place before it becomes a finding: a long function that is a flat list of fields, or a
   builder chain, is fine. Group one rule into one finding with the worst places in `where`.
2. Read the code with the rest of this list, as far as Step 5 of the audit reaches.
3. Severity: craft findings are **medium** when they put money, login or personal data at risk of a
   wrong change (swallowed errors, duplicated price or permission rules, one class that does all the
   billing), else **low**. A craft problem that already causes a wrong result is a correctness
   finding at its own severity.
4. Each finding says what goes wrong for the business ("a price fix in one place is missed in the
   other"), names the rule ID, and gives the smallest safe fix, with "first a test around it".

## Sources

- Robert C. Martin, *Clean Code: A Handbook of Agile Software Craftsmanship* (2008): ch. 2 names,
  3 functions, 4 comments, 5 formatting, 6 objects and data, 7 error handling, 8 boundaries, 9 unit
  tests, 10 classes, 11 systems, 12 emergence, 17 smells and heuristics.
- Robert C. Martin and Micah Martin, *Agile Principles, Patterns, and Practices in C#* (APPP, 2006):
  ch. 7 design smells, 8-12 SOLID, 20-25 and 31-36 patterns, 28 package principles.
- Craig Larman, *Applying UML and Patterns*, 3rd ed. (2004): ch. 9 domain models, 13 and 34 layers,
  17 and 25 GRASP, 26 and 35 GoF patterns applied, 39 documenting architecture.
- Gamma, Helm, Johnson and Vlissides, *Design Patterns: Elements of Reusable Object-Oriented
  Software* (GoF, 1994): the 23 patterns and the principles of ch. 1.
- Eric Freeman and Elisabeth Freeman, *Head First Design Patterns* (2004): the patterns above and
  the OO principles of each chapter.
