# Self-Checking Loop Prompt

Use this prompt when you want an assistant to keep improving the work until it meets a strict quality bar.

```text
SELF-CHECKING LOOP

You will work in an iterative loop until the task meets the required quality bar.

TASK
[Describe exactly what you want produced.]

SUCCESS CRITERIA
Score each criterion strictly from 1-10. No soft passes.

1. [Criterion 1]
2. [Criterion 2]
3. [Criterion 3]

LOOP PROTOCOL
Repeat the following steps until the work is final:

PLAN
State the single next step you will take.

DO
Produce or improve the work.

VERIFY
Score the current result from 1-10 against each success criterion.
Be brutally honest.
List exactly what is still weak, incomplete, or risky.
Tie every score to specific evidence in the current work.

DECIDE
If every criterion scores 8 or higher, print:

FINAL

Then provide the finished result and stop.

If any criterion scores below 8, print:

ITERATING

Then continue the loop, fixing the lowest-scoring criterion first.

RULES
- Never call the work final until every success criterion scores 8 or higher.
- Each iteration must directly improve the weakest score from the previous VERIFY step.
- Do not ask me questions.
- If information is missing, make a sensible assumption, state it briefly, and continue.
- Keep the work concrete, useful, and aligned with the task.
- Do not hide flaws in the verification step.
- Begin immediately and continue until FINAL.
```

