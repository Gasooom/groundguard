# Datasheet — `gg-claims-v2` (not yet constructed)

**Status: no records yet.** The format, validator, review workflow, split
freezing and benchmark runner exist (M4a). The records do not. Construction
is blocked on source access (see "Blocker").

## Purpose

The held-out evaluation set for the claim-level engine: multi-sentence
public-domain sources, AI-drafted answers and controlled perturbations,
claim-level gold labels reviewed by a person, and a frozen dev/test split by
context group. It replaces `gg-legacy-v1` (seen during development, heavily
duplicated) as the basis for any generalization claim.

## Planned composition (owner decisions, M4)

| Property | Plan |
|---|---|
| Domains | health information; finance and science (public agency figures, public science pages) |
| Sources | US federal government works (public domain), e.g. agency health pages, statistical releases, science pages. Every source records URL, publisher, title, retrieval date and licence |
| Size target | ≥ 300 answers / ≥ 900 claims for v1.0 (methodology §5.1). A smaller first batch will be released as 0.x if that target is not met |
| Answers | AI-drafted answers to the source (`answer_origin = ai_drafted`) plus controlled perturbations (`perturbation`: negation, qualifier swap, number/unit change, date swap, extra list item, superlative swap, entity swap) |
| Labels | Drafted by construction or judgment (`label_basis`), **every record reviewed by the owner** before it can be LABELED |
| Annotators | one (owner). Agreement not measured |
| Split | by `context_group`, hash-assigned, test fraction 0.4, frozen with `groundguard annotate freeze` |

## Blocker

The M4a development environment's network policy denies the source hosts
(cdc.gov, nih.gov, medlineplus.gov, fda.gov, nasa.gov, usgs.gov, noaa.gov,
bls.gov and sec.gov were tried). Source text must be verbatim and
traceable, so it is not reconstructed from memory. To proceed, either:

1. allow the source domains in the environment's network settings, after
   which drafting continues in this repository, or
2. collect the source passages yourself (copy the text, URL and retrieval
   date) into a file, and drafting proceeds from that file.

## Known limitations (by design)

- Single annotator, so no agreement statistic.
- AI-drafted answers may not match the error distribution of a production
  model. Perturbations are synthetic by construction.
- Two domains only. Results must not be generalized to other domains.
