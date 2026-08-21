# GroundGuard Human-Labeled Benchmark

## Purpose

The GroundGuard benchmark evaluates whether an LLM-generated answer is grounded, relevant, and non-contradictory with respect to supplied source context.

## Target Size

The V1 benchmark will contain 200–300 human-labeled examples.

## Data Sources

The benchmark will use two primary sources:

1. Synthetic examples created specifically to test controlled grounding, relevance, and contradiction cases.
2. Public factual text used to create more realistic evaluation examples.

## Example Generation

Examples will be constructed to cover:

- Fully supported answers
- Partially supported answers
- Unsupported answers
- Contradictory answers
- Relevant answers
- Irrelevant answers
- Multiple claims
- Paraphrases
- Numerical claims
- Temporal claims
- Edge cases where unsupported information is not contradictory

Synthetic examples will be intentionally designed to test specific failure modes.

Public-text examples will be adapted into context/question/answer records while preserving the source meaning.

## Labeling

Each example will receive human labels for:

- Grounding
- Relevance
- Contradiction

Annotators will follow the rules defined in `docs/evaluation_specification.md`.

## Quality Control

The benchmark will include consistency checks and disagreement handling.

Examples with unclear labeling criteria will be reviewed and either clarified, relabeled, or excluded.

## Reproducibility

Benchmark generation and validation procedures will be documented and stored in the repository.

## Target Distribution

The initial V1 benchmark target is 250 examples.

| Category | Target |
|---|---:|
| Fully supported | 50 |
| Partially supported | 35 |
| Unsupported | 35 |
| Contradictory | 35 |
| Relevant but unsupported | 25 |
| Irrelevant | 25 |
| Multi-claim / edge cases | 25 |
| Numerical / temporal / paraphrase cases | 20 |
| **Total** | **250** |

These targets describe benchmark construction, not expected real-world class frequencies.

Final evaluation results will report the actual class distribution.