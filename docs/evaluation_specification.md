# GroundGuard Evaluation Specification

## Grounding

### SUPPORTED

All substantive claims in the answer are supported by the supplied context.

### PARTIALLY_SUPPORTED

Some substantive claims are supported by the supplied context, but at least one substantive claim is unsupported.

### UNSUPPORTED

The substantive claims in the answer cannot be supported by the supplied context.

## Relevance

### RELEVANT

The answer directly addresses the question or task and uses information related to the supplied context.

### IRRELEVANT

The answer does not meaningfully address the question or task.

## Contradiction

### CONTRADICTORY

An answer is CONTRADICTORY when one or more substantive claims directly conflict with information supported by the supplied context.

### NOT_CONTRADICTORY

An answer is NOT_CONTRADICTORY when none of its substantive claims conflict with information supported by the supplied context.

## Important Distinction

An unsupported claim is not automatically contradictory.

Example:

**Context:**

> The company was founded in 2018.

**Answer:**

> The company has 500 employees.

**Label:**

`NOT_CONTRADICTORY`

The context does not support the employee count, but it also does not contradict it.

Example:

**Context:**

> The company was founded in 2018.

**Answer:**

> The company was founded in 2015.

**Label:**

`CONTRADICTORY`

## Annotation Procedure

For each evaluation example:

1. Read the complete context.
2. Read the complete answer.
3. Identify the substantive claims in the answer.
4. Determine whether each claim is supported by the context.
5. Assign the grounding label.
6. Determine whether the answer addresses the intended question or task.
7. Assign the relevance label.
8. Check whether any answer claim conflicts with the context.
9. Assign the contradiction label.
10. Record the final labels and supporting evidence.

## Annotation Principle

Annotators must evaluate the answer against the supplied context.

External knowledge must not be used to mark an unsupported claim as grounded.