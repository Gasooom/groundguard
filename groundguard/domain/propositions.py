from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Proposition:
    """
    A normalized factual proposition.

    Example:
        NovaTech manufactures electric bikes.

    becomes:

        subject   = "NovaTech"
        predicate = "manufactures"
        object    = "electric bikes"
        attributes = {}
    """

    subject: str
    predicate: str
    object: str
    attributes: dict[str, str] = field(default_factory=dict)


def _normalize_text(text: str) -> str:
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _normalize_number_word(value: str) -> str:
    """
    Normalize simple English number words used by the benchmark.

    Examples:
        five -> 5
        three -> 3
        120 -> 120
    """

    numbers = {
        "zero": "0",
        "one": "1",
        "two": "2",
        "three": "3",
        "four": "4",
        "five": "5",
        "six": "6",
        "seven": "7",
        "eight": "8",
        "nine": "9",
        "ten": "10",
        "eleven": "11",
        "twelve": "12",
        "thirteen": "13",
        "fourteen": "14",
        "fifteen": "15",
        "sixteen": "16",
        "seventeen": "17",
        "eighteen": "18",
        "nineteen": "19",
        "twenty": "20",
    }

    normalized = _normalize_text(value).lower()

    return numbers.get(
        normalized,
        normalized,
    )


def _extract_manufactures(
    text: str,
) -> list[Proposition]:
    pattern = re.compile(
        r"^(?P<subject>.+?)\s+"
        r"manufactures\s+"
        r"(?P<object>.+?)"
        r"\.?$",
        re.IGNORECASE,
    )

    match = pattern.match(text)

    if not match:
        return []

    return [
        Proposition(
            subject=_normalize_text(
                match.group("subject")
            ),
            predicate="manufactures",
            object=_normalize_text(
                match.group("object")
            ).rstrip("."),
            attributes={},
        )
    ]


def _extract_operates_in(
    text: str,
) -> list[Proposition]:
    pattern = re.compile(
        r"^(?P<subject>.+?)\s+"
        r"operates\s+in\s+"
        r"(?P<locations>.+?)"
        r"\.?$",
        re.IGNORECASE,
    )

    match = pattern.match(text)

    if not match:
        return []

    subject = _normalize_text(
        match.group("subject")
    )

    locations_text = (
        match.group("locations")
        .rstrip(".")
        .strip()
    )

    locations_text = re.sub(
        r",?\s+and\s+",
        ",",
        locations_text,
        flags=re.IGNORECASE,
    )

    locations = [
        location.strip()
        for location in locations_text.split(",")
        if location.strip()
    ]

    return [
        Proposition(
            subject=subject,
            predicate="operates_in",
            object=location,
            attributes={},
        )
        for location in locations
    ]


def _extract_employee_count(
    text: str,
) -> list[Proposition]:
    """
    Extract employee-count claims.

    Supported forms:

        NovaTech has 250 employees.
        NovaTech has 250 people.
        NovaTech employs 120 employees.
        NovaTech employs 120 people.

    All normalize to:

        predicate = "has_employees"
        object = numeric count
    """

    patterns = (
        re.compile(
            r"^(?P<subject>.+?)\s+"
            r"has\s+"
            r"(?P<count>\d+)\s+"
            r"(?:employees?|people)"
            r"\.?$",
            re.IGNORECASE,
        ),
        re.compile(
            r"^(?P<subject>.+?)\s+"
            r"employs\s+"
            r"(?P<count>\d+)\s+"
            r"(?:employees?|people)"
            r"\.?$",
            re.IGNORECASE,
        ),
    )

    for pattern in patterns:
        match = pattern.match(text)

        if not match:
            continue

        return [
            Proposition(
                subject=_normalize_text(
                    match.group("subject")
                ),
                predicate="has_employees",
                object=match.group("count"),
                attributes={},
            )
        ]

    return []


def _extract_office_count(
    text: str,
) -> list[Proposition]:
    """
    Extract office-count claims.

    Examples:

        Orion Labs has five offices.
        Orion Labs has 5 offices.
    """

    pattern = re.compile(
        r"^(?P<subject>.+?)\s+"
        r"has\s+"
        r"(?P<count>\d+|"
        r"zero|one|two|three|four|five|six|seven|eight|nine|ten|"
        r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|"
        r"seventeen|eighteen|nineteen|twenty)"
        r"\s+offices?"
        r"\.?$",
        re.IGNORECASE,
    )

    match = pattern.match(text)

    if not match:
        return []

    count = _normalize_number_word(
        match.group("count")
    )

    return [
        Proposition(
            subject=_normalize_text(
                match.group("subject")
            ),
            predicate="has_offices",
            object=count,
            attributes={},
        )
    ]


def _extract_founded(
    text: str,
) -> list[Proposition]:
    """
    Extract company founding-year claims.

    Example:

        Acme Technologies was founded in 2018.

    becomes:

        Acme Technologies / founded / company / year=2018
    """

    pattern = re.compile(
        r"^(?P<subject>.+?)\s+"
        r"(?:was\s+)?founded\s+in\s+"
        r"(?P<year>(?:19|20)\d{2})"
        r"\.?$",
        re.IGNORECASE,
    )

    match = pattern.match(text)

    if not match:
        return []

    return [
        Proposition(
            subject=_normalize_text(
                match.group("subject")
            ),
            predicate="founded",
            object="company",
            attributes={
                "year": match.group("year"),
            },
        )
    ]


def _extract_headquartered_in(
    text: str,
) -> list[Proposition]:
    """
    Extract headquarters-location claims.

    Example:

        NovaTech is headquartered in Nairobi.
    """

    pattern = re.compile(
        r"^(?P<subject>.+?)\s+"
        r"is\s+headquartered\s+in\s+"
        r"(?P<object>[A-Za-z][A-Za-z\s-]*?)"
        r"\.?$",
        re.IGNORECASE,
    )

    match = pattern.match(text)

    if not match:
        return []

    return [
        Proposition(
            subject=_normalize_text(
                match.group("subject")
            ),
            predicate="headquartered_in",
            object=_normalize_text(
                match.group("object")
            ),
            attributes={},
        )
    ]


def _extract_revenue(
    text: str,
) -> list[Proposition]:
    """
    Extract annual revenue claims.

    Supported examples:

        NovaTech generated $40 million in revenue in 2023.
        NovaTech reported annual revenue of $4 million in 2023.
    """

    patterns = (
        re.compile(
            r"^(?P<subject>.+?)\s+"
            r"generated\s+"
            r"\$?(?P<amount>[\d,.]+)"
            r"\s+(?P<unit>million|billion|thousand)"
            r"\s+in\s+revenue"
            r"(?:\s+in\s+"
            r"(?P<year>(?:19|20)\d{2}))?"
            r"\.?$",
            re.IGNORECASE,
        ),
        re.compile(
            r"^(?P<subject>.+?)\s+"
            r"reported\s+annual\s+revenue\s+of\s+"
            r"\$?(?P<amount>[\d,.]+)"
            r"\s+(?P<unit>million|billion|thousand)"
            r"(?:\s+in\s+"
            r"(?P<year>(?:19|20)\d{2}))?"
            r"\.?$",
            re.IGNORECASE,
        ),
    )

    for pattern in patterns:
        match = pattern.match(text)

        if not match:
            continue

        amount = match.group("amount")
        unit = match.group("unit").lower()

        attributes: dict[str, str] = {}

        year = match.group("year")

        if year:
            attributes["year"] = year

        return [
            Proposition(
                subject=_normalize_text(
                    match.group("subject")
                ),
                predicate="revenue",
                object=f"{amount} {unit}",
                attributes=attributes,
            )
        ]

    return []


def _extract_composition(
    text: str,
) -> list[Proposition]:
    """
    Extract composition claims.

    Example:

        Water consists of two hydrogen atoms and one oxygen atom.

    The complete composition is preserved as the object because
    the proposition represents a single compositional fact.
    """

    pattern = re.compile(
        r"^(?P<subject>.+?)\s+"
        r"consists\s+of\s+"
        r"(?P<object>.+?)"
        r"\.?$",
        re.IGNORECASE,
    )

    match = pattern.match(text)

    if not match:
        return []

    return [
        Proposition(
            subject=_normalize_text(
                match.group("subject")
            ),
            predicate="composition",
            object=_normalize_text(
                match.group("object")
            ).rstrip("."),
            attributes={},
        )
    ]


def _extract_expanded_into(
    text: str,
) -> list[Proposition]:
    pattern = re.compile(
        r"^(?P<subject>.+?)\s+"
        r"expanded\s+into\s+"
        r"(?P<object>[A-Za-z][A-Za-z\s-]*?)"
        r"(?:\s+in\s+"
        r"(?P<year>(?:19|20)\d{2}))?"
        r"\.?$",
        re.IGNORECASE,
    )

    match = pattern.match(text)

    if not match:
        return []

    attributes: dict[str, str] = {}

    year = match.group("year")

    if year:
        attributes["year"] = year

    return [
        Proposition(
            subject=_normalize_text(
                match.group("subject")
            ),
            predicate="expanded_into",
            object=_normalize_text(
                match.group("object")
            ),
            attributes=attributes,
        )
    ]


def _extract_launched(
    text: str,
) -> list[Proposition]:
    pattern = re.compile(
        r"^(?P<subject>.+?)\s+"
        r"launched\s+"
        r"(?:its\s+)?"
        r"(?P<object>platform|product|service)"
        r"(?:\s+in\s+"
        r"(?P<year>(?:19|20)\d{2}))?"
        r"\.?$",
        re.IGNORECASE,
    )

    match = pattern.match(text)

    if not match:
        return []

    attributes: dict[str, str] = {}

    year = match.group("year")

    if year:
        attributes["year"] = year

    return [
        Proposition(
            subject=_normalize_text(
                match.group("subject")
            ),
            predicate="launched",
            object=_normalize_text(
                match.group("object")
            ),
            attributes=attributes,
        )
    ]


def _extract_capital(
    text: str,
) -> list[Proposition]:
    patterns = [
        re.compile(
            r"^(?P<subject>[A-Za-z][A-Za-z\s-]*)"
            r"'s\s+capital(?:\s+city)?\s+is\s+"
            r"(?P<object>[A-Za-z][A-Za-z\s-]*)"
            r"\.?$",
            re.IGNORECASE,
        ),
        re.compile(
            r"^(?:the\s+)?capital(?:\s+city)?\s+of\s+"
            r"(?P<subject>[A-Za-z][A-Za-z\s-]*)"
            r"\s+is\s+"
            r"(?P<object>[A-Za-z][A-Za-z\s-]*)"
            r"\.?$",
            re.IGNORECASE,
        ),
        re.compile(
            r"^(?P<object>[A-Za-z][A-Za-z\s-]*)"
            r"\s+is\s+the\s+capital\s+of\s+"
            r"(?P<subject>[A-Za-z][A-Za-z\s-]*)"
            r"\.?$",
            re.IGNORECASE,
        ),
    ]

    for pattern in patterns:
        match = pattern.match(text)

        if not match:
            continue

        return [
            Proposition(
                subject=_normalize_text(
                    match.group("subject")
                ),
                predicate="capital_city",
                object=_normalize_text(
                    match.group("object")
                ),
                attributes={},
            )
        ]

    return []


def _extract_subject(
    text: str,
) -> str | None:
    """
    Extract the grammatical subject before the first supported predicate.
    """

    predicate_pattern = re.compile(
        r"\b(?:"
        r"manufactures|"
        r"operates\s+in|"
        r"has|"
        r"employs|"
        r"was\s+founded|"
        r"founded|"
        r"is\s+headquartered\s+in|"
        r"generated|"
        r"reported\s+annual\s+revenue|"
        r"consists\s+of|"
        r"expanded\s+into|"
        r"launched"
        r")\b",
        re.IGNORECASE,
    )

    match = predicate_pattern.search(text)

    if not match:
        return None

    subject = text[:match.start()].strip()

    if not subject:
        return None

    return _normalize_text(subject)


def _split_compound_sentence(
    text: str,
) -> list[str]:
    """
    Split simple coordinated factual claims while preserving
    the original subject.
    """

    normalized = _normalize_text(
        text
    ).rstrip(".")

    subject = _extract_subject(
        normalized
    )

    if not subject:
        return [normalized]

    split_pattern = re.compile(
        r"\s+and\s+"
        r"(?=(?:"
        r"manufactures|"
        r"operates\s+in|"
        r"has|"
        r"employs|"
        r"was\s+founded|"
        r"founded|"
        r"is\s+headquartered\s+in|"
        r"generated|"
        r"reported\s+annual\s+revenue|"
        r"consists\s+of|"
        r"expanded\s+into|"
        r"launched"
        r")\b)",
        re.IGNORECASE,
    )

    parts = split_pattern.split(
        normalized
    )

    if len(parts) == 1:
        return [normalized]

    first_part = parts[0].strip()

    clauses = [first_part]

    for part in parts[1:]:
        part = part.strip()

        if not part:
            continue

        clauses.append(
            f"{subject} {part}"
        )

    return clauses


def extract_propositions(
    text: str,
) -> list[Proposition]:
    """
    Extract deterministic structured propositions from text.

    The extractor intentionally handles a narrow, high-confidence
    set of factual patterns. It does not attempt general NLP parsing.
    """

    normalized = _normalize_text(
        text
    )

    if not normalized:
        return []

    propositions: list[Proposition] = []

    sentences = re.split(
        r"(?<=[.!?])\s+",
        normalized,
    )

    extractors = (
        _extract_manufactures,
        _extract_operates_in,
        _extract_employee_count,
        _extract_office_count,
        _extract_founded,
        _extract_headquartered_in,
        _extract_revenue,
        _extract_composition,
        _extract_expanded_into,
        _extract_launched,
        _extract_capital,
    )

    for sentence in sentences:
        sentence = sentence.strip()

        if not sentence:
            continue

        clauses = _split_compound_sentence(
            sentence
        )

        for clause in clauses:
            clause = clause.strip()

            if not clause:
                continue

            for extractor in extractors:
                result = extractor(
                    clause
                )

                if result:
                    propositions.extend(
                        result
                    )
                    break

    return propositions