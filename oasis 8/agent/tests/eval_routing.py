"""
ROUTING EVALUATION.

Measures how often agent.models.pick() sends a question to the right model,
against a hand-labelled set of questions written the way plant staff ask them.

    python -m agent.tests.eval_routing
    python -m agent.tests.eval_routing --verbose      show every question

Why this exists
---------------
Model selection is deterministic here - a keyword match, no model involved. The
obvious objection is that a small language model would classify better. This
harness is how that claim gets settled with a number instead of an opinion:
run it, read the accuracy, look at which questions fail.

Labels are the model KEY in agent/config.py, not the model name, so swapping a
model does not invalidate the set.
"""

import sys

from agent.models import pick

# (question, expected_key, has_images)
#
# "coding" means the request genuinely needs arithmetic or code.
# "general" means prose, retrieval, drafting or explanation.
# "vision" means an image is attached - decided structurally, not by wording.
CASES = [
    # ---------------------------------------------------------- general: retrieval
    ("Why does the seal on P-101 keep failing?", "general", False),
    ("What is the interlock set point on the crude distillation column?", "general", False),
    ("What permits are required for a mechanical seal replacement?", "general", False),
    ("Summarise the findings of the 2026 inspection report.", "general", False),
    ("What does the HAZOP say about high pressure in the reflux drum?", "general", False),
    ("Which SOP covers seal replacement?", "general", False),
    ("What PPE is specified for work on P-101?", "general", False),
    ("Explain what a mechanical seal does.", "general", False),

    # ------------------------------------------- general: drafting (writes a file)
    ("Draft an approval note for replacing the seal on P-101.", "general", False),
    ("Write a letter to the contractor about the delayed inspection.", "general", False),
    ("Prepare a short report on P-101 reliability.", "general", False),
    ("Make a presentation for the safety review meeting.", "general", False),
    ("Draft an email to the maintenance lead about the seal failure.", "general", False),

    # ------------------------------- general: words that LOOK numeric but are prose
    # These are the traps. A broad keyword list routes them wrong.
    ("What is the function of the mechanical seal?", "general", False),
    ("Summarise the maintenance history for P-101.", "general", False),
    ("What is the total scope of the inspection programme?", "general", False),
    ("Give me an analysis of recurring failures.", "general", False),
    ("What formula does the SOP recommend for torque?", "general", False),
    ("Is there an average expected life for this seal type?", "general", False),
    ("How many people are required for this job?", "general", False),
    ("Implement the recommendations from the inspection report.", "general", False),
    ("Debug the communication problem with the contractor.", "general", False),

    # ------------------------------------------------------------------- coding
    ("Calculate the average of 187, 246, 188 and 94.", "coding", False),
    ("Calculate the total downtime in hours.", "coding", False),
    ("Compute the mean time between failures for P-101.", "coding", False),
    ("Work out the cost of four seal replacements at 18500 each.", "coding", False),
    ("How many days between 12 March 2026 and 28 August 2026?", "coding", False),
    ("What is the sum of the last three repair costs?", "coding", False),
    ("Write a script to parse the maintenance log.", "coding", False),
    ("Write code to convert the workbook to CSV.", "coding", False),
    ("Give me a Python function to compute MTBF.", "coding", False),
    ("Write an SQL query for downtime by month.", "coding", False),
    ("Write a regex that matches equipment tags like P-101.", "coding", False),

    # ------------------------------------------------------------------- vision
    ("What does this drawing show?", "vision", True),
    ("Read the nameplate in this photograph.", "vision", True),
    # wording says calculate, but an image is attached - structure must win
    ("Calculate the flow from the values on this gauge.", "vision", True),
]

# Deliberately hard phrasings - how plant staff actually ask for numbers, using
# words the keyword list does not contain. Kept separate so the headline figure
# is not flattered by the easy set, and so the gap is visible.
ADVERSARIAL = [
    ("Tell me the running total of failures this year.", "coding", False),
    ("How much did we spend on seals in 2025?", "coding", False),
    ("What proportion of failures were seal-related?", "coding", False),
    ("Count the entries in the maintenance log.", "coding", False),
    ("Add up the downtime for Q1.", "coding", False),
    ("Multiply the unit cost by four.", "coding", False),
    ("What percentage of the pumps are due for inspection?", "coding", False),
    ("What is the pump curve for P-101?", "general", False),
    ("Average temperature is mentioned in the SOP - what does it say?", "general", False),
    ("The report computes the risk score - explain how.", "general", False),
    ("Is Python used anywhere in the control system?", "general", False),
    ("Calculate nothing, just summarise the report.", "general", False),
]


def score(cases, verbose=False):
    by_label = {}
    wrong = []

    for question, expected, has_images in cases:
        images = ["dummy.png"] if has_images else None
        got, reason = pick(question, images)
        ok = got == expected
        by_label.setdefault(expected, [0, 0])
        by_label[expected][1] += 1
        if ok:
            by_label[expected][0] += 1
        else:
            wrong.append((question, expected, got))
        if verbose:
            print(f"  [{'ok ' if ok else 'MISS'}] {expected:<8} -> {got:<8} {question}")

    return len(cases) - len(wrong), len(cases), by_label, wrong


def report(title, cases, verbose):
    correct, total, by_label, wrong = score(cases, verbose)
    print(f"\n  {title}: {correct}/{total}  ({100 * correct / total:.1f}%)")
    for label, (c, n) in sorted(by_label.items()):
        print(f"      {label:<10} {c}/{n}")
    if wrong:
        print("      misrouted:")
        for q, exp, got in wrong:
            print(f"        {exp} -> {got}   {q}")
    return correct, total


NOTE = """
  What a misroute costs
  ---------------------
  Nothing, for correctness. Model selection decides WHICH MODEL WRITES PROSE.
  It does not decide what runs. Arithmetic is done by the calculate tool and
  counts and totals by query_data, both chosen by the model from the tool
  catalogue inside the loop, after it has seen real results.

  So "Add up the downtime for Q1." routes to general - a miss - and still
  calls calculate and still returns an exact figure. The number does not come
  from the model's head under either routing.

  This is the design claim: correctness lives in the tool layer, not the model
  layer. Routing is an optimisation. A wrong route is slower or less idiomatic,
  never wrong.

  Cost per routing decision: 0 model calls, 0 tokens, deterministic and
  repeatable. A language model asked to make the same choice costs one full
  call per request and cannot be regression-tested like this.
"""

if __name__ == "__main__":
    v = "--verbose" in sys.argv
    print("\n  ROUTING EVALUATION - agent.models.pick()")
    print("  " + "-" * 44)
    c1, t1 = report("Representative questions", CASES, v)
    c2, t2 = report("Adversarial phrasings", ADVERSARIAL, v)
    print(f"\n  OVERALL: {c1 + c2}/{t1 + t2}  "
          f"({100 * (c1 + c2) / (t1 + t2):.1f}%)")
    print(NOTE)
    sys.exit(0)
