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


def _extract_sells(
    text: str,
) -> list[Proposition]:
    pattern = re.compile(
        r"^(?P<subject>.+?)\s+"
        r"sells\s+"
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
            predicate="sells",
            object=_normalize_text(
                match.group("object")
            ).rstrip("."),
            attributes={},
        )
    ]


def _extract_provides(
    text: str,
) -> list[Proposition]:
    pattern = re.compile(
        r"^(?P<subject>.+?)\s+"
        r"provides\s+"
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
            predicate="provides",
            object=_normalize_text(
                match.group("object")
            ).rstrip("."),
            attributes={},
        )
    ]


def _extract_offers(
    text: str,
) -> list[Proposition]:
    pattern = re.compile(
        r"^(?P<subject>.+?)\s+"
        r"offers\s+"
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
            predicate="offers",
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
    patterns = (
        re.compile(
            r"^(?P<subject>.+?)\s+"
            r"has\s+"
            r"(?P<count>\d+|"
            r"zero|one|two|three|four|five|six|seven|eight|nine|ten|"
            r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|"
            r"seventeen|eighteen|nineteen|twenty)"
            r"\s+"
            r"(?:employees?|people)"
            r"\.?$",
            re.IGNORECASE,
        ),
        re.compile(
            r"^(?P<subject>.+?)\s+"
            r"employs\s+"
            r"(?P<count>\d+|"
            r"zero|one|two|three|four|five|six|seven|eight|nine|ten|"
            r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|"
            r"seventeen|eighteen|nineteen|twenty)"
            r"\s+"
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
                object=_normalize_number_word(
                    match.group("count")
                ),
                attributes={},
            )
        ]

    return []


def _extract_office_count(
    text: str,
) -> list[Proposition]:
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

    return [
        Proposition(
            subject=_normalize_text(
                match.group("subject")
            ),
            predicate="has_offices",
            object=_normalize_number_word(
                match.group("count")
            ),
            attributes={},
        )
    ]


def _extract_office_locations(
    text: str,
) -> list[Proposition]:
    pattern = re.compile(
        r"^(?P<subject>.+?)\s+"
        r"has\s+offices\s+in\s+"
        r"(?P<locations>.+?)"
        r"\.?$",
        re.IGNORECASE,
    )

    match = pattern.match(text)

    if not match:
        return []

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

    if not locations:
        return []

    return [
        Proposition(
            subject=_normalize_text(
                match.group("subject")
            ),
            predicate="has_offices",
            object=str(len(locations)),
            attributes={},
        )
    ]


def _extract_planet_count(
    text: str,
) -> list[Proposition]:
    pattern = re.compile(
        r"^(?:the\s+)?"
        r"(?P<subject>our\s+solar\s+system)"
        r"\s+has\s+"
        r"(?P<count>\d+|"
        r"zero|one|two|three|four|five|six|seven|eight|nine|ten)"
        r"\s+planets?"
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
            predicate="has_planets",
            object=_normalize_number_word(
                match.group("count")
            ),
            attributes={},
        )
    ]


def _extract_founded(
    text: str,
) -> list[Proposition]:
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


def _extract_entered_into(
    text: str,
) -> list[Proposition]:
    pattern = re.compile(
        r"^(?P<subject>.+?)\s+"
        r"entered\s+"
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
            predicate="entered_into",
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
        r"(?P<object>"
        r"first\s+product|"
        r"platform|"
        r"product|"
        r"service"
        r")"
        r"(?:\s+in\s+"
        r"(?P<date>"
        r"(?:(?:January|February|March|April|May|June|"
        r"July|August|September|October|November|December)"
        r"\s+)?"
        r"(?:19|20)\d{2}"
        r"))?"
        r"\.?$",
        re.IGNORECASE,
    )

    match = pattern.match(text)

    if not match:
        return []

    attributes: dict[str, str] = {}

    date = match.group("date")

    if date:
        year_match = re.search(
            r"(?:19|20)\d{2}",
            date,
        )

        if year_match:
            attributes["year"] = year_match.group(0)

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


def _extract_percentage_claim(
    text: str,
) -> list[Proposition]:
    pattern = re.compile(
        r"^(?P<subject>.+?)\s+"
        r"makes\s+up\s+about\s+"
        r"(?P<percentage>\d+(?:\.\d+)?)"
        r"\s+percent\s+of\s+"
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
            predicate="percentage_of",
            object=_normalize_text(
                match.group("object")
            ),
            attributes={
                "percentage": match.group(
                    "percentage"
                ),
            },
        )
    ]


def _extract_largest_claim(
    text: str,
) -> list[Proposition]:
    pattern = re.compile(
        r"^(?P<subject>.+?)\s+"
        r"is\s+the\s+largest\s+"
        r"(?P<object>.+?)"
        r"(?:\s+on\s+Earth)?"
        r"\.?$",
        re.IGNORECASE,
    )

    match = pattern.match(text)

    if not match:
        return []

    category = _normalize_text(
        match.group("object")
    )
    category = re.sub(
        r"\bbasin\b",
        "",
        category,
        flags=re.IGNORECASE,
    )
    category = _normalize_text(category)

    largest_object = _normalize_text(
        match.group("subject")
    )
    largest_object = re.sub(
        r"^the\s+",
        "",
        largest_object,
        flags=re.IGNORECASE,
    )

    return [
        Proposition(
            subject=category,
            predicate="largest",
            object=largest_object,
            attributes={},
        )
    ]


# ---------------------------------------------------------------------------
# Compound sentence handling
# ---------------------------------------------------------------------------

_PREDICATE_STARTS = (
    r"manufactures",
    r"sells",
    r"provides",
    r"offers",
    r"operates\s+in",
    r"has",
    r"employs",
    r"was\s+founded",
    r"founded",
    r"is\s+headquartered\s+in",
    r"generated",
    r"reported\s+annual\s+revenue",
    r"consists\s+of",
    r"expanded\s+into",
    r"entered",
    r"launched",
    r"makes\s+up",
    r"is\s+the\s+largest",
)


def _extract_subject(
    text: str,
) -> str | None:
    predicate_pattern = re.compile(
        r"\b(?:"
        + "|".join(_PREDICATE_STARTS)
        + r")\b",
        re.IGNORECASE,
    )

    match = predicate_pattern.search(text)

    if not match:
        return None

    subject = text[:match.start()].strip()

    if not subject:
        return None

    return _normalize_text(subject)


def _find_compound_boundaries(
    text: str,
) -> list[int]:
    """
    Find positions where a coordinated factual clause starts.

    Examples:

        DataCore has 120 employees and operates in five countries.
                                     ^
        Acme launched its platform in 2021 and expanded into Rwanda.
                                                 ^

    Only an 'and' followed by a known predicate is considered
    a compound boundary. This prevents normal object lists such
    as:

        backup software and cloud storage

    from being incorrectly split.
    """

    pattern = re.compile(
        r"\s+and\s+"
        r"(?=(?:"
        + "|".join(_PREDICATE_STARTS)
        + r")\b)",
        re.IGNORECASE,
    )

    return [
        match.start()
        for match in pattern.finditer(text)
    ]


def _split_compound_sentence(
    text: str,
) -> list[str]:
    """
    Split a sentence into independent factual clauses.

    The subject is inherited by subsequent clauses.

    Example:

        DataCore has 120 employees and operates in five countries.

    becomes:

        DataCore has 120 employees.
        DataCore operates in five countries.
    """

    normalized = _normalize_text(
        text
    ).rstrip(".")

    if not normalized:
        return []

    subject = _extract_subject(
        normalized
    )

    boundaries = _find_compound_boundaries(
        normalized
    )

    if not boundaries:
        return [normalized]

    clauses: list[str] = []

    start = 0

    for boundary in boundaries:
        clause = normalized[
            start:boundary
        ].strip()

        if clause:
            clauses.append(
                clause
            )

        start = boundary

    final_clause = normalized[
        start:
    ].strip()

    final_clause = re.sub(
        r"^and\s+",
        "",
        final_clause,
        flags=re.IGNORECASE,
    ).strip()

    if final_clause:
        if subject:
            clauses.append(
                f"{subject} {final_clause}"
            )
        else:
            clauses.append(
                final_clause
            )

    return clauses


def _split_comma_coordinated_claims(
    text: str,
) -> list[str]:
    """
    Handle comma-separated factual clauses when the second
    clause begins with a known predicate.

    Example:

        Acme was founded in 2018, has 500 employees.

    becomes:

        Acme was founded in 2018.
        Acme has 500 employees.
    """

    normalized = _normalize_text(
        text
    ).rstrip(".")

    subject = _extract_subject(
        normalized
    )

    if not subject:
        return [normalized]

    pattern = re.compile(
        r",\s*(?=(?:"
        + "|".join(_PREDICATE_STARTS)
        + r")\b)",
        re.IGNORECASE,
    )

    parts = pattern.split(
        normalized
    )

    if len(parts) == 1:
        return [normalized]

    clauses = [
        parts[0].strip()
    ]

    for part in parts[1:]:
        part = part.strip()

        if not part:
            continue

        clauses.append(
            f"{subject} {part}"
        )

    return clauses


def _expand_implicit_subject(
    clauses: list[str],
) -> list[str]:
    """
    Ensure subsequent clauses inherit the original subject
    when the splitter produces an implicit predicate clause.

    This is intentionally conservative.
    """

    if not clauses:
        return []

    subject = _extract_subject(
        clauses[0]
    )

    if not subject:
        return clauses

    expanded = [
        clauses[0]
    ]

    for clause in clauses[1:]:
        stripped = clause.strip()

        if not stripped:
            continue

        if _extract_subject(
            stripped
        ):
            expanded.append(
                stripped
            )
            continue

        expanded.append(
            f"{subject} {stripped}"
        )

    return expanded


def _prepare_clauses(
    sentence: str,
) -> list[str]:
    """
    Prepare a sentence for deterministic proposition extraction.
    """

    normalized = _normalize_text(
        sentence
    ).rstrip(".")

    if not normalized:
        return []

    clauses = _split_compound_sentence(
        normalized
    )

    prepared: list[str] = []

    for clause in clauses:
        comma_clauses = (
            _split_comma_coordinated_claims(
                clause
            )
        )

        prepared.extend(
            comma_clauses
        )

    return _expand_implicit_subject(
        prepared
    )


# ---------------------------------------------------------------------------
# Proposition extraction
# ---------------------------------------------------------------------------

def extract_propositions(
    text: str,
) -> list[Proposition]:
    """
    Extract deterministic structured propositions.

    The extractor intentionally handles a high-confidence set
    of factual patterns rather than attempting general NLP parsing.

    Compound claims are split into independent propositions so
    that contradictions can be detected at the individual-claim
    level.

    Example:

        DataCore has 120 employees and operates in five countries.

    produces:

        DataCore | has_employees | 120
        DataCore | operates_in   | five countries
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
        _extract_sells,
        _extract_provides,
        _extract_offers,
        _extract_operates_in,
        _extract_employee_count,
        _extract_office_locations,
        _extract_office_count,
        _extract_planet_count,
        _extract_founded,
        _extract_headquartered_in,
        _extract_revenue,
        _extract_composition,
        _extract_expanded_into,
        _extract_entered_into,
        _extract_launched,
        _extract_capital,
        _extract_percentage_claim,
        _extract_largest_claim,
    )

    for sentence in sentences:
        sentence = sentence.strip()

        if not sentence:
            continue

        clauses = _prepare_clauses(
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