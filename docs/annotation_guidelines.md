# GroundGuard Annotation Guidelines

## Purpose

These guidelines define how human annotators label GroundGuard benchmark examples.

Annotators evaluate an answer against the supplied context and question.

External knowledge must not be used to mark an unsupported claim as grounded.

## Annotation Steps

For every example:

1. Read the question.
2. Read the complete context.
3. Read the complete answer.
4. Identify the substantive claims in the answer.
5. Evaluate grounding.
6. Evaluate relevance.
7. Evaluate contradiction.
8. Record evidence supporting the labels.

## Grounding

### SUPPORTED

Use SUPPORTED when all substantive claims in the answer are supported by the supplied context.

### PARTIALLY_SUPPORTED

Use PARTIALLY_SUPPORTED when some substantive claims are supported but at least one substantive claim is unsupported.

### UNSUPPORTED

Use UNSUPPORTED when the substantive claims in the answer cannot be supported by the supplied context.

## Relevance

### RELEVANT

Use RELEVANT when the answer directly addresses the question or task.

### IRRELEVANT

Use IRRELEVANT when the answer does not meaningfully address the question or task.

## Contradiction

### CONTRADICTORY

Use CONTRADICTORY when one or more substantive claims directly conflict with information supported by the context.

### NOT_CONTRADICTORY

Use NOT_CONTRADICTORY when no substantive claim conflicts with the supplied context.

## Important Distinction

Unsupported does not automatically mean contradictory.

If the context does not provide enough information to verify a claim, the claim may be unsupported without being contradictory.

## Evidence

Annotators must record the relevant context evidence used to justify their labels.

Evidence should be specific rather than a general statement such as:

"Seems correct."

## External Knowledge

Do not use outside knowledge to determine whether an answer is grounded.

The supplied context is the grounding reference.

## Unclear Cases

If an example cannot be labeled confidently using these rules:

1. Mark the example for review.
2. Record the reason for uncertainty.
3. Do not guess.
4. The example will be reviewed during consistency checking.

## Labeling Principle

The goal is not to make the answer appear correct.

The goal is to apply the labeling rules consistently to the supplied context, question, and answer.