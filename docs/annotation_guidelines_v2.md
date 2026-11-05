# GroundGuard Annotation Guidelines v2 (claim level)

Applies to `gg-claims-v2` and later claim-level datasets. The v1 guide
(`annotation_guidelines.md`) remains the reference for `gg-legacy-v1`.
Label definitions follow `EVALUATION_METHODOLOGY.md` §3. This guide adds
the practical rules.

## 1. Roles and the review gate

- **Drafter.** Writes candidate records. AI-drafted records use the reserved
  drafter id `ai-assistant` and start as `NEEDS_REVIEW`. A drafter's label
  is a proposal, never a gold label.
- **Reviewer.** A person who checks every claim against the source text and
  accepts, edits or excludes the record. Only reviewed records become
  `LABELED`, and only `LABELED` records can enter a frozen split. The
  validator rejects `ai-assistant` as a reviewer.
- **Second annotator.** Not available for v1.0 (owner decision, M4). Reports
  state "single annotator, agreement not measured".

## 2. What a claim is

A claim is a minimal statement that can be checked on its own against the
sources. Split an answer where its parts could have different labels:

| Answer | Claims |
|---|---|
| "Drug Q is approved for adults and is taken once daily." | "Drug Q is approved for adults" · "Drug Q is taken once daily" |
| "The agency reported 3.1% growth in 2023." | one claim (value and year form one fact) |
| "Based on the sources, the trial enrolled 400 people." | "the trial enrolled 400 people" (drop meta-phrases) |

Do not create claims for questions, hedges ("I'm not sure"), or statements
about the sources themselves ("The context does not say").

`answer_span` is the character range of the claim's wording in the answer,
half-open `[start, end)`. Conjunct claims may borrow a subject from elsewhere
in the sentence. In that case the span covers only the part the claim adds.

## 3. Labels

| Label | Use when | Evidence |
|---|---|---|
| `SUPPORTED` | The sources state the claim. A careful reader needs no outside knowledge | required: exact quote(s) |
| `CONTRADICTED` | The sources state the claim's negation, or an incompatible value for the same attribute of the same entity and scope | required: exact quote(s) |
| `NOT_ENOUGH_INFO` | Neither of the above, including claims that are true in the world but absent from the sources | optional: nearest related quote |

Decision rules (methodology §3.1, restated):

1. **Scope and qualifiers.** "approved for adults" does not support a claim
   about children. That is `NOT_ENOUGH_INFO`, unless the source makes the
   restriction exclusive ("only adults", "not approved for children"), in
   which case it is `CONTRADICTED`.
2. **Numbers.** Same unit and different value: `CONTRADICTED`. Different
   units: convert first. Approximate wording ("about 78%") supports a value
   only if the source is approximate in the same way.
3. **Dates.** A year attached to a different event in the source is not
   support ("opened in 2015, moved in 2019" does not support "opened in 2019").
4. **Lists.** An extra item is `NOT_ENOUGH_INFO`, unless the source says the
   list is complete ("its only products are…").
5. **Superlatives.** "X is the largest" contradicts "Y is the largest" for the
   same category. Tag `superlative`.
6. **Outside knowledge.** Never use it, even when you know the claim is true.

## 4. Evidence quotes

- A quote must be an **exact substring** of the source text, including
  punctuation and capitalization. The validator rejects anything else.
- Quote the shortest span that fully justifies the label, normally one
  sentence.
- For claims that need two sentences, add two evidence items.

## 5. Phenomenon tags

Tag every claim with each phenomenon that makes it hard (or `none`):
`negation`, `qualifier`, `number`, `unit`, `date`, `paraphrase`,
`coreference`, `list_exhaustiveness`, `entity_confusion`, `superlative`,
`multi_source`. Tags drive the per-phenomenon breakdown in reports, so tag
what is true of the claim, not what you expect the system to find hard.

## 6. Answer-level fields

- `relevance`: `RELEVANT` if the answer addresses the question that was asked.
- `completeness`: `INCOMPLETE` if the sources contain information the
  question asks for and the answer omits it. This is **not** a grounding
  label: an incomplete answer can have only `SUPPORTED` claims.

## 7. Uncertain and excluded records

- If you can label a record but are unsure, accept it with `u`. The record
  is marked `uncertain` with your reason, and reports count uncertain
  records separately.
- If a record cannot be labeled consistently (ambiguous source, broken
  text, a question the sources cannot address), exclude it with `x` and a
  reason. Excluded records are listed in the split manifest.
- Do not guess.

## 8. Workflow

```bash
groundguard annotate status benchmark/datasets/gg-claims-v2/records.jsonl
groundguard annotate review benchmark/datasets/gg-claims-v2/records.jsonl --reviewer <your-id>
groundguard annotate freeze benchmark/datasets/gg-claims-v2/records.jsonl --version 1.0.0
```

`review` saves after every record and can be stopped with `q` at any
prompt. `freeze` refuses while any record is unreviewed. After freezing,
any edit to `records.jsonl` invalidates the split, so a correction means a
new dataset version.

## 9. Held-out discipline

Do not inspect system predictions on test-split records before the frozen
test run. Every test run is logged in
`benchmark/results/TEST_ACCESS_LOG.jsonl` with its purpose.
