from __future__ import annotations

from fastapi.responses import HTMLResponse


DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >
    <title>GroundGuard Dashboard</title>

    <style>
        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            font-family:
                Inter, ui-sans-serif, system-ui, -apple-system,
                BlinkMacSystemFont, "Segoe UI", sans-serif;
            background: #f5f7fa;
            color: #172033;
        }

        header {
            background: #111827;
            color: white;
            padding: 20px 32px;
        }

        header h1 {
            margin: 0;
            font-size: 24px;
        }

        header p {
            margin: 6px 0 0;
            color: #cbd5e1;
            font-size: 14px;
        }

        main {
            max-width: 1200px;
            margin: 32px auto;
            padding: 0 20px;
        }

        .panel {
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 20px;
        }

        .panel h2 {
            margin-top: 0;
            font-size: 18px;
        }

        label {
            display: block;
            font-weight: 600;
            margin: 16px 0 8px;
        }

        textarea,
        input {
            width: 100%;
            padding: 12px;
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            font: inherit;
        }

        textarea {
            min-height: 100px;
            resize: vertical;
        }

        button {
            margin-top: 20px;
            padding: 12px 22px;
            border: 0;
            border-radius: 8px;
            background: #111827;
            color: white;
            font-weight: 600;
            cursor: pointer;
        }

        button:disabled {
            opacity: 0.6;
            cursor: wait;
        }

        .hidden {
            display: none;
        }

        .decision {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 20px;
            margin-bottom: 20px;
        }

        .decision-label {
            font-size: 28px;
            font-weight: 800;
        }

        .score {
            font-size: 20px;
            font-weight: 700;
        }

        .accept {
            color: #15803d;
        }

        .flag {
            color: #b45309;
        }

        .reject {
            color: #b91c1c;
        }

        .grid {
            display: grid;
            grid-template-columns:
                repeat(auto-fit, minmax(180px, 1fr));
            gap: 14px;
        }

        .metric {
            border: 1px solid #e5e7eb;
            border-radius: 10px;
            padding: 16px;
        }

        .metric-title {
            font-size: 13px;
            color: #64748b;
            margin-bottom: 8px;
        }

        .metric-value {
            font-size: 18px;
            font-weight: 700;
        }

        .reason {
            background: #f8fafc;
            border-left: 4px solid #64748b;
            padding: 14px;
            border-radius: 6px;
        }

        .error {
            color: #b91c1c;
            background: #fef2f2;
            border: 1px solid #fecaca;
            padding: 12px;
            border-radius: 8px;
        }
    </style>
</head>

<body>
    <header>
        <h1>GroundGuard</h1>
        <p>LLM Reliability Evaluation Dashboard</p>
    </header>

    <main>
        <section class="panel">
            <h2>Evaluate an Answer</h2>

            <form id="evaluation-form">
                <label for="question">Question</label>
                <textarea
                    id="question"
                    required
                    placeholder="Enter the question..."
                ></textarea>

                <label for="context">Evidence / Context</label>
                <textarea
                    id="context"
                    required
                    placeholder="Enter the supplied evidence..."
                ></textarea>

                <label for="answer">Answer</label>
                <textarea
                    id="answer"
                    required
                    placeholder="Enter the answer to evaluate..."
                ></textarea>

                <label for="threshold">
                    Threshold (optional)
                </label>
                <input
                    id="threshold"
                    type="number"
                    min="0"
                    max="1"
                    step="0.01"
                    placeholder="Default"
                >

                <button id="submit-button" type="submit">
                    Evaluate
                </button>
            </form>

            <div id="error" class="error hidden"></div>
        </section>

        <section id="results" class="panel hidden">
            <div class="decision">
                <div>
                    <div class="metric-title">
                        System Decision
                    </div>
                    <div id="decision" class="decision-label">
                        -
                    </div>
                </div>

                <div>
                    <div class="metric-title">
                        Reliability Score
                    </div>
                    <div id="reliability" class="score">
                        -
                    </div>
                </div>
            </div>

            <div class="grid">
                <div class="metric">
                    <div class="metric-title">Grounding</div>
                    <div id="grounding" class="metric-value">
                        -
                    </div>
                </div>

                <div class="metric">
                    <div class="metric-title">Relevance</div>
                    <div id="relevance" class="metric-value">
                        -
                    </div>
                </div>

                <div class="metric">
                    <div class="metric-title">Contradiction</div>
                    <div id="contradiction" class="metric-value">
                        -
                    </div>
                </div>

                <div class="metric">
                    <div class="metric-title">Threshold</div>
                    <div id="threshold-result" class="metric-value">
                        -
                    </div>
                </div>

                <div class="metric">
                    <div class="metric-title">PII</div>
                    <div id="pii" class="metric-value">
                        -
                    </div>
                </div>

                <div class="metric">
                    <div class="metric-title">
                        Prompt Injection
                    </div>
                    <div
                        id="prompt-injection"
                        class="metric-value"
                    >
                        -
                    </div>
                </div>

                <div class="metric">
                    <div class="metric-title">Safety</div>
                    <div id="safety" class="metric-value">
                        -
                    </div>
                </div>
            </div>

            <div style="margin-top: 20px;">
                <div class="metric-title">Reason</div>
                <div id="reason" class="reason">-</div>
            </div>
        </section>
    </main>

    <script>
        const form = document.getElementById(
            "evaluation-form"
        );

        const button = document.getElementById(
            "submit-button"
        );

        const results = document.getElementById(
            "results"
        );

        const errorBox = document.getElementById(
            "error"
        );

        function setText(id, value) {
            document.getElementById(id).textContent = value;
        }

        function decisionClass(decision) {
            if (decision === "ACCEPT") {
                return "accept";
            }

            if (decision === "FLAG") {
                return "flag";
            }

            return "reject";
        }

        form.addEventListener("submit", async (event) => {
            event.preventDefault();

            errorBox.classList.add("hidden");
            results.classList.add("hidden");
            button.disabled = true;
            button.textContent = "Evaluating...";

            const payload = {
                question: document.getElementById(
                    "question"
                ).value,

                context: document.getElementById(
                    "context"
                ).value,

                answer: document.getElementById(
                    "answer"
                ).value,
            };

            const threshold = document.getElementById(
                "threshold"
            ).value;

            if (threshold !== "") {
                payload.threshold = Number(threshold);
            }

            try {
                const response = await fetch(
                    "/evaluate",
                    {
                        method: "POST",
                        headers: {
                            "Content-Type":
                                "application/json"
                        },
                        body: JSON.stringify(payload),
                    }
                );

                const data = await response.json();

                if (!response.ok) {
                    throw new Error(
                        data.detail ||
                        "Evaluation request failed."
                    );
                }

                setText(
                    "decision",
                    data.system_decision
                );

                const decisionElement =
                    document.getElementById("decision");

                decisionElement.className =
                    "decision-label " +
                    decisionClass(
                        data.system_decision
                    );

                setText(
                    "reliability",
                    data.reliability_score.toFixed(4)
                );

                setText(
                    "grounding",
                    `${data.grounding_label} (${data.grounding_score.toFixed(4)})`
                );

                setText(
                    "relevance",
                    `${data.relevance_label} (${data.relevance_score.toFixed(4)})`
                );

                setText(
                    "contradiction",
                    `${data.contradiction_label} (${data.contradiction_score.toFixed(4)})`
                );

                setText(
                    "threshold-result",
                    data.threshold.toFixed(4)
                );

                setText(
                    "pii",
                    data.pii_detected
                        ? "DETECTED"
                        : "CLEAR"
                );

                setText(
                    "prompt-injection",
                    data.prompt_injection_detected
                        ? "DETECTED"
                        : "CLEAR"
                );

                setText(
                    "safety",
                    data.safety_safe
                        ? "SAFE"
                        : "UNSAFE"
                );

                setText(
                    "reason",
                    data.reason
                );

                results.classList.remove("hidden");
            } catch (error) {
                errorBox.textContent =
                    error.message ||
                    "Evaluation request failed.";

                errorBox.classList.remove("hidden");
            } finally {
                button.disabled = false;
                button.textContent = "Evaluate";
            }
        });
    </script>
</body>
</html>
"""


def dashboard() -> HTMLResponse:
    return HTMLResponse(
        content=DASHBOARD_HTML
    )