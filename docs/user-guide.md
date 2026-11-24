# BugForge: how to use it

BugForge helps Claude build, check, improve and document a web app on your own computer. You decide
what happens at every step; Claude does the work and shows you the result.

## Install it

In Claude Code, type these two commands, one at a time:

```
/plugin marketplace add 253UgurSahin/BugForge
```

```
/plugin install bugforge@bugforge
```

## Start a project

1. Open Claude Code in the folder of your project, or in an empty folder for a new app.
2. Type `/forge` and say what you want, for example "build my idea: a booking app for my salon" or
   "improve my app".
3. Claude asks how far to go, from 1 to 5. Answer with a number or a name, for example "level 2".
   For a striking header and calm screens, say "look 2, header 4".
4. After each step Claude shows what was done and waits. Reply in your own words, for example
   "ja, ga door". Claude records your words and continues.

If you want Claude to continue without stopping after each step, say "run it all on your own". The
security check always waits for your answer.

## Check an app

Type `/forge-check` and say what you need:

| you say | Claude does |
| --- | --- |
| "test my app" | tests every page and flow, and fixes what fails |
| "is my app safe" | runs the security and privacy check and gives a verdict |
| "audit my code" | reads your code and reports what to improve, including how well it is made |

## Document an app

Type `/forge-docs`. Claude writes a README, the architecture with diagrams, a glossary, the decisions
behind the code and a guide for the people who use the app. Where only you know the answer, Claude
marks it with `TO-FILL` and asks you at the end.

## Where your files are

Plans, reports and screenshots are in the folder `forge-work` in your project. That folder is never
sent anywhere and never committed. Changes to your app are made on a separate branch; merging them is
your decision.

## If something goes wrong

| message | what it means | what to do |
| --- | --- | --- |
| a phase "stays open until every check passes" | a step did not leave everything it should | ask Claude what is missing; it fixes it and checks again |
| "scope.py" refuses an address | the address is not your own app | test your app on localhost, or confirm that the address is yours |
| "Verdict: FAIL" | the security check found a serious problem | let Claude fix the findings, then run the check again |
