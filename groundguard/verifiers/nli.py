"""Optional NLI backend (``pip install groundguard[nli]``).

An entailment model scores (premise = candidate evidence, hypothesis = claim)
pairs. The verifier picks the candidate with the highest entailment score:

    entailment >= entail_threshold        -> SUPPORTED
    else max contradiction >= threshold   -> CONTRADICTED
    else                                  -> NOT_ENOUGH_INFO

It replaces the lexical backend at the end of the chain. The guards and
structured facts still run first and can veto. ``raw_score`` is the
deciding model probability; it is not a calibrated confidence until a
calibrator is fitted for this exact model revision.

No NLI result is claimed in this repository until someone runs
``scripts/run_nli_benchmark.sh`` where the model can be downloaded and
commits the run files.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Callable, Protocol, Sequence

from groundguard.core.errors import GroundGuardError
from groundguard.core.types import Claim, ClaimVerdict, EvidenceSpan


class VerifierUnavailable(GroundGuardError):
    """An optional verifier backend cannot be loaded (missing extra or model)."""


@dataclass(frozen=True)
class NLIScores:
    entailment: float
    neutral: float
    contradiction: float


class NLIModel(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def revision(self) -> str: ...

    def predict(self, pairs: Sequence[tuple[str, str]]) -> list[NLIScores]: ...


_REGISTRY: dict[str, Callable[[str], NLIModel]] = {}


def register_nli_model(prefix: str, factory: Callable[[str], NLIModel]) -> None:
    """Register an in-process model factory for model ids starting with ``prefix``
    (used by tests and by deployments that bring their own model server)."""

    _REGISTRY[prefix] = factory


@lru_cache(maxsize=4)
def get_nli_model(model_id: str, revision: str) -> NLIModel:
    for prefix, factory in _REGISTRY.items():
        if model_id.startswith(prefix):
            return factory(revision)
    return TransformersNLIModel(model_id, revision)


class TransformersNLIModel:
    """A Hugging Face sequence-classification NLI model, loaded lazily on CPU.

    ``revision`` should be a commit hash so runs are reproducible; it is
    recorded in the verifier id.
    """

    def __init__(self, model_id: str, revision: str, *, batch_size: int = 16, max_length: int = 512) -> None:
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as error:  # pragma: no cover - exercised only without the extra
            raise VerifierUnavailable(
                "the NLI backend needs the optional extra: pip install 'groundguard[nli]'"
            ) from error
        try:
            self._tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision)
            self._model = AutoModelForSequenceClassification.from_pretrained(model_id, revision=revision)
        except Exception as error:  # pragma: no cover - network / model errors
            raise VerifierUnavailable(f"could not load NLI model {model_id}@{revision}: {error}") from error
        self._model.eval()
        self._torch = torch
        self._name = model_id
        self._revision = revision
        self._batch_size = batch_size
        self._max_length = max_length
        self._index = self._label_index(self._model.config.id2label)

    @staticmethod
    def _label_index(id2label: dict[int, str]) -> dict[str, int]:
        index: dict[str, int] = {}
        for position, label in id2label.items():
            lowered = label.lower()
            for key in ("entail", "neutral", "contradict"):
                if key in lowered:
                    index[key] = int(position)
        if set(index) != {"entail", "neutral", "contradict"}:
            raise VerifierUnavailable(f"model labels {id2label} are not entailment/neutral/contradiction")
        return index

    @property
    def name(self) -> str:
        return self._name

    @property
    def revision(self) -> str:
        return self._revision

    def predict(self, pairs: Sequence[tuple[str, str]]) -> list[NLIScores]:  # pragma: no cover - needs the model
        results: list[NLIScores] = []
        for start in range(0, len(pairs), self._batch_size):
            batch = pairs[start : start + self._batch_size]
            encoded: Any = self._tokenizer(
                [premise for premise, _ in batch],
                [hypothesis for _, hypothesis in batch],
                padding=True,
                truncation=True,
                max_length=self._max_length,
                return_tensors="pt",
            )
            with self._torch.no_grad():
                probabilities = self._model(**encoded).logits.softmax(dim=-1).tolist()
            for row in probabilities:
                results.append(
                    NLIScores(
                        entailment=row[self._index["entail"]],
                        neutral=row[self._index["neutral"]],
                        contradiction=row[self._index["contradict"]],
                    )
                )
        return results


@dataclass(frozen=True)
class NLIVerifier:
    model: NLIModel
    entail_threshold: float = 0.5
    contradict_threshold: float = 0.5

    def __post_init__(self) -> None:
        for value in (self.entail_threshold, self.contradict_threshold):
            if not 0.0 < value < 1.0:
                raise ValueError("NLI thresholds must be in (0, 1)")

    @property
    def name(self) -> str:
        return "nli"

    @property
    def version(self) -> str:
        return (
            f"1-{self.model.name}@{self.model.revision}"
            f"-e{self.entail_threshold:g}-c{self.contradict_threshold:g}"
        )

    def verify(self, claim: Claim, candidates: Sequence[EvidenceSpan]) -> ClaimVerdict:
        identifier = f"{self.name}@{self.version}"
        if not candidates:
            return ClaimVerdict(claim.id, "NOT_ENOUGH_INFO", 0.0, (), identifier,
                                "No candidate evidence was found.")
        scores = self.model.predict([(candidate.text, claim.text) for candidate in candidates])
        entail_index = max(range(len(scores)), key=lambda i: (scores[i].entailment, -i))
        contradict_index = max(range(len(scores)), key=lambda i: (scores[i].contradiction, -i))
        best_entail = scores[entail_index]
        best_contradict = scores[contradict_index]
        signals = {
            "entailment": round(best_entail.entailment, 6),
            "contradiction": round(best_contradict.contradiction, 6),
        }
        if best_entail.entailment >= self.entail_threshold:
            return ClaimVerdict(claim.id, "SUPPORTED", best_entail.entailment, (candidates[entail_index],),
                                identifier, f"The model judges the evidence to entail the claim "
                                f"(p={best_entail.entailment:.2f}).", signals)
        if best_contradict.contradiction >= self.contradict_threshold:
            return ClaimVerdict(claim.id, "CONTRADICTED", best_contradict.contradiction,
                                (candidates[contradict_index],), identifier,
                                f"The model judges the evidence to contradict the claim "
                                f"(p={best_contradict.contradiction:.2f}).", signals)
        return ClaimVerdict(claim.id, "NOT_ENOUGH_INFO", best_entail.entailment, (candidates[entail_index],),
                            identifier, "The model finds neither entailment nor contradiction above threshold.",
                            signals)
