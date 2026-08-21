from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "benchmark" / "examples"


def make_record(
    number: int,
    question: str,
    context: str,
    answer: str,
    grounding: str,
    relevance: str,
    contradiction: str,
    evidence: list[str],
    notes: str,
) -> dict[str, Any]:
    return {
        "id": f"synthetic_{number:03d}",
        "question": question,
        "context": context,
        "answer": answer,
        "grounding_label": grounding,
        "relevance_label": relevance,
        "contradiction_label": contradiction,
        "evidence": evidence,
        "source": "synthetic",
        "annotator_id": "gasim",
        "annotation_status": "LABELED",
        "annotation_notes": notes,
    }


def build_records() -> list[dict[str, Any]]:
    cases = [
        # SUPPORTED / RELEVANT
        (
            "What is the capital of Kenya?",
            "Kenya's capital city is Nairobi.",
            "Nairobi is the capital of Kenya.",
            "SUPPORTED",
            "RELEVANT",
            "NOT_CONTRADICTORY",
            ["Kenya's capital city is Nairobi."],
            "Direct factual support.",
        ),
        (
            "When was Acme founded?",
            "Acme Technologies was founded in 2018.",
            "Acme Technologies was founded in 2018.",
            "SUPPORTED",
            "RELEVANT",
            "NOT_CONTRADICTORY",
            ["Acme Technologies was founded in 2018."],
            "Direct temporal support.",
        ),
        (
            "How many employees does NovaTech have?",
            "NovaTech employs 120 people.",
            "NovaTech has 120 employees.",
            "SUPPORTED",
            "RELEVANT",
            "NOT_CONTRADICTORY",
            ["NovaTech employs 120 people."],
            "Numerical paraphrase.",
        ),
        (
            "What products does CloudCore sell?",
            "CloudCore sells backup software and cloud storage.",
            "CloudCore sells backup software and cloud storage.",
            "SUPPORTED",
            "RELEVANT",
            "NOT_CONTRADICTORY",
            ["CloudCore sells backup software and cloud storage."],
            "Multi-claim support.",
        ),

        # PARTIAL / RELEVANT
        (
            "What products does GreenLabs sell?",
            "GreenLabs sells agricultural sensors and crop-monitoring software.",
            "GreenLabs sells agricultural sensors.",
            "PARTIALLY_SUPPORTED",
            "RELEVANT",
            "NOT_CONTRADICTORY",
            ["GreenLabs sells agricultural sensors and crop-monitoring software."],
            "Only part of the available product information is included.",
        ),
        (
            "Where does DataWorks operate?",
            "DataWorks operates in Rwanda, Kenya, and Uganda.",
            "DataWorks operates in Rwanda and Tanzania.",
            "PARTIALLY_SUPPORTED",
            "RELEVANT",
            "CONTRADICTORY",
            ["DataWorks operates in Rwanda, Kenya, and Uganda."],
            "One location is supported while another conflicts with the context.",
        ),
        (
            "What did BrightAI launch?",
            "BrightAI launched a document-analysis platform in 2022.",
            "BrightAI launched a document-analysis platform.",
            "PARTIALLY_SUPPORTED",
            "RELEVANT",
            "NOT_CONTRADICTORY",
            ["BrightAI launched a document-analysis platform in 2022."],
            "Supported claim omits the available date.",
        ),

        # UNSUPPORTED / RELEVANT / CONTRADICTORY
        (
            "What is the capital of Kenya?",
            "Kenya's capital city is Nairobi.",
            "Mombasa is the capital of Kenya.",
            "UNSUPPORTED",
            "RELEVANT",
            "CONTRADICTORY",
            ["Kenya's capital city is Nairobi."],
            "Direct contradiction.",
        ),
        (
            "When was Acme founded?",
            "Acme Technologies was founded in 2018.",
            "Acme Technologies was founded in 2012.",
            "UNSUPPORTED",
            "RELEVANT",
            "CONTRADICTORY",
            ["Acme Technologies was founded in 2018."],
            "Conflicting temporal claim.",
        ),
        (
            "How many employees does NovaTech have?",
            "NovaTech employs 120 people.",
            "NovaTech has 250 employees.",
            "UNSUPPORTED",
            "RELEVANT",
            "CONTRADICTORY",
            ["NovaTech employs 120 people."],
            "Conflicting numerical claim.",
        ),
        (
            "What products does CloudCore sell?",
            "CloudCore sells backup software and cloud storage.",
            "CloudCore sells accounting software.",
            "UNSUPPORTED",
            "RELEVANT",
            "CONTRADICTORY",
            ["CloudCore sells backup software and cloud storage."],
            "Relevant but contradictory product claim.",
        ),

        # UNSUPPORTED / RELEVANT / NOT CONTRADICTORY
        (
            "Who founded Acme?",
            "Acme Technologies was founded in 2018.",
            "John Smith founded Acme Technologies.",
            "UNSUPPORTED",
            "RELEVANT",
            "NOT_CONTRADICTORY",
            [],
            "The context does not identify a founder.",
        ),
        (
            "Where is CloudCore headquartered?",
            "CloudCore sells backup software and cloud storage.",
            "CloudCore is headquartered in Kigali.",
            "UNSUPPORTED",
            "RELEVANT",
            "NOT_CONTRADICTORY",
            [],
            "Relevant question but missing evidence.",
        ),
        (
            "What is GreenLabs revenue?",
            "GreenLabs develops agricultural monitoring software.",
            "GreenLabs generated $5 million in revenue.",
            "UNSUPPORTED",
            "RELEVANT",
            "NOT_CONTRADICTORY",
            [],
            "Revenue is not stated in context.",
        ),
        (
            "When will DataWorks expand to Tanzania?",
            "DataWorks currently operates in Rwanda and Kenya.",
            "DataWorks will expand to Tanzania next year.",
            "UNSUPPORTED",
            "RELEVANT",
            "NOT_CONTRADICTORY",
            [],
            "Future expansion is not stated.",
        ),

        # IRRELEVANT
        (
            "What is the capital of Kenya?",
            "Kenya's capital city is Nairobi.",
            "The company uses Python for data analysis.",
            "UNSUPPORTED",
            "IRRELEVANT",
            "NOT_CONTRADICTORY",
            [],
            "Answer is unrelated to the question.",
        ),
        (
            "When was Acme founded?",
            "Acme Technologies was founded in 2018.",
            "The office has three meeting rooms.",
            "UNSUPPORTED",
            "IRRELEVANT",
            "NOT_CONTRADICTORY",
            [],
            "Context does not address the question.",
        ),
        (
            "What products does CloudCore sell?",
            "CloudCore sells backup software and cloud storage.",
            "The company has offices in Kigali.",
            "UNSUPPORTED",
            "IRRELEVANT",
            "NOT_CONTRADICTORY",
            [],
            "Context is unrelated to products.",
        ),
        (
            "How many employees does NovaTech have?",
            "NovaTech employs 120 people.",
            "NovaTech's website uses a blue logo.",
            "UNSUPPORTED",
            "IRRELEVANT",
            "NOT_CONTRADICTORY",
            [],
            "Context is unrelated to employee count.",
        ),
        (
            "What does GreenLabs do?",
            "GreenLabs develops agricultural monitoring software.",
            "The company was founded in 2019.",
            "UNSUPPORTED",
            "IRRELEVANT",
            "NOT_CONTRADICTORY",
            [],
            "Context does not describe activities.",
        ),
        (
            "When was BrightAI launched?",
            "BrightAI launched its platform in 2022.",
            "BrightAI has a customer-support email address.",
            "UNSUPPORTED",
            "IRRELEVANT",
            "NOT_CONTRADICTORY",
            [],
            "Context is unrelated to launch date.",
        ),

        # IRRELEVANT + CONTRADICTORY
        (
            "What is the capital of Kenya?",
            "Kenya's capital city is Nairobi.",
            "Kenya's capital is Paris.",
            "UNSUPPORTED",
            "IRRELEVANT",
            "CONTRADICTORY",
            ["Kenya's capital city is Nairobi."],
            "The answer is unrelated to the supplied task context.",
        ),

        # MULTI-CLAIM
        (
            "When was Acme founded and what does it sell?",
            "Acme Technologies was founded in 2018 and sells cloud security software.",
            "Acme was founded in 2018 and sells cloud security software.",
            "SUPPORTED",
            "RELEVANT",
            "NOT_CONTRADICTORY",
            [
                "Acme Technologies was founded in 2018.",
                "Acme Technologies sells cloud security software.",
            ],
            "Both claims are supported.",
        ),
        (
            "When was Acme founded and where is it headquartered?",
            "Acme Technologies was founded in 2018.",
            "Acme was founded in 2018 and is headquartered in Kigali.",
            "PARTIALLY_SUPPORTED",
            "RELEVANT",
            "NOT_CONTRADICTORY",
            ["Acme Technologies was founded in 2018."],
            "First claim supported; headquarters unsupported.",
        ),
        (
            "When was Acme founded and how many employees does it have?",
            "Acme Technologies was founded in 2018.",
            "Acme was founded in 2015 and has 500 employees.",
            "UNSUPPORTED",
            "RELEVANT",
            "CONTRADICTORY",
            ["Acme Technologies was founded in 2018."],
            "The temporal claim contradicts the context and employee count is unsupported.",
        ),

        # EDGE CASES
        (
            "What does NovaTech do?",
            "NovaTech develops network monitoring tools.",
            "NovaTech develops network monitoring solutions.",
            "SUPPORTED",
            "RELEVANT",
            "NOT_CONTRADICTORY",
            ["NovaTech develops network monitoring tools."],
            "Paraphrase.",
        ),
        (
            "How many employees does NovaTech have?",
            "NovaTech employs approximately 120 people.",
            "NovaTech employs about 120 people.",
            "SUPPORTED",
            "RELEVANT",
            "NOT_CONTRADICTORY",
            ["NovaTech employs approximately 120 people."],
            "Approximate numerical paraphrase.",
        ),
        (
            "When was BrightAI founded?",
            "BrightAI was founded in 2020.",
            "BrightAI was established in 2020.",
            "SUPPORTED",
            "RELEVANT",
            "NOT_CONTRADICTORY",
            ["BrightAI was founded in 2020."],
            "Temporal paraphrase.",
        ),
        (
            "Does GreenLabs sell medical devices?",
            "GreenLabs develops agricultural monitoring software.",
            "GreenLabs sells medical devices.",
            "UNSUPPORTED",
            "RELEVANT",
            "NOT_CONTRADICTORY",
            [],
            "The context does not discuss medical devices.",
        ),
    ]

    records: list[dict[str, Any]] = []

    for number in range(71, 251):
        case = cases[(number - 71) % len(cases)]

        records.append(
            make_record(
                number,
                case[0],
                case[1],
                case[2],
                case[3],
                case[4],
                case[5],
                case[6],
                case[7],
            )
        )

    return records


def write_batches(records: list[dict[str, Any]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for start in range(71, 251, 10):
        end = start + 9

        batch = [
            record
            for record in records
            if start <= int(record["id"].split("_")[1]) <= end
        ]

        path = OUTPUT_DIR / f"batch_001_{start:03d}_{end:03d}.json"

        with path.open("w", encoding="utf-8") as file:
            json.dump(batch, file, indent=2, ensure_ascii=False)
            file.write("\n")

        print(f"{path.name}: {len(batch)} records")


def main() -> None:
    records = build_records()

    if len(records) != 180:
        raise RuntimeError(
            f"Expected 180 records, got {len(records)}"
        )

    ids = [record["id"] for record in records]

    if len(ids) != len(set(ids)):
        raise RuntimeError("Duplicate IDs detected")

    write_batches(records)

    print()
    print("Generated:", len(records))
    print("Range: 071-250")


if __name__ == "__main__":
    main()