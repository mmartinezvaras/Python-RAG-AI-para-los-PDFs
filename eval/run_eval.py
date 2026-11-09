"""Evaluate the RAG system on a question set with known answers, and compare configurations.

For every question in eval/questions.jsonl and every retrieval mode it measures:

* Retrieval hit@k — the article that holds the answer is among the retrieved passages.
* MRR@k          — how high that article ranks (1.0 = always first).
* Answer accuracy — the answer contains the expected facts (keyword check, then an LLM judge).
* Abstention     — for questions NOT answerable from the documents, the system says so.
* The best cosine similarity per question, to calibrate the relevance gate (RAG_MIN_RELEVANCE).

Usage:
    python -m eval.run_eval                      # both modes, writes eval/results.md
    python -m eval.run_eval --modes hybrid --limit 5
    python -m eval.run_eval --retrieval-only     # no LLM calls, seconds instead of minutes
    python -m eval.run_eval --suggest-threshold  # prints a calibrated RAG_MIN_RELEVANCE

RAG_EVAL_PAUSE=4 waits that many seconds between questions (free API tiers limit requests per minute).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from rag import config

QUESTIONS = Path(__file__).with_name("questions.jsonl")
RESULTS = Path(__file__).with_name("results.md")

JUDGE_PROMPT = """You are grading an answer produced by a question-answering system.

Question: {question}
Expected answer: {expected}
System answer: {answer}

Does the system answer state the same essential facts as the expected answer (same numbers and
units; wording, extra detail, citations like [1] and language may differ)?
Reply with a single word: true or false."""

_ABSTAIN = re.compile(
    r"no (he encontrado|se encuentra|encuentro|aparece|se menciona|incluye|contiene|dispongo|tengo informaci)"
    r"|no lo s[eé]|no (se )?especifica|don'?t (know|have|include|contain)|do(es)? not (include|contain|mention|specify)"
    r"|couldn'?t find|not (found|mentioned|included) in|no information",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\[\d+\]", " ", text)  # citation markers are not facts


def keyword_match(answer: str, groups: list[list[str]] | None) -> bool:
    """Every group must be satisfied by one of its alternatives. Numbers must match as whole
    numbers ('1' doesn't match '15'); words match as prefixes ('mes' matches 'meses')."""
    if not groups:
        return False
    text = _normalize(answer)
    for alternatives in groups:
        ok = False
        for alt in alternatives:
            alt = _normalize(alt)
            pattern = rf"(?<![\d,.]){re.escape(alt)}(?![\d])" if alt[:1].isdigit() else rf"\b{re.escape(alt)}"
            if re.search(pattern, text):
                ok = True
                break
        if not ok:
            return False
    return True


def is_abstention(answer_text: str) -> bool:
    return bool(_ABSTAIN.search(answer_text))


def judge(question: str, expected: str, answer_text: str, keywords: list[list[str]] | None = None) -> bool:
    if keywords and keyword_match(answer_text, keywords):
        return True
    from rag.providers import get_llm

    verdict = get_llm(config.JUDGE_MODEL).complete(
        JUDGE_PROMPT.format(question=question, expected=expected, answer=answer_text)
    )
    words = re.findall(r"\b(true|false)\b", verdict.lower())
    return bool(words) and words[0] == "true"


# ------------------------------------------------------------------------------------------


@dataclass
class Row:
    question: str
    answerable: bool
    hit: bool = False
    reciprocal_rank: float = 0.0
    best_relevance: float = 0.0
    grounded: bool = True
    correct: bool | None = None
    answer: str = ""
    seconds: float = 0.0


@dataclass
class ModeReport:
    mode: str
    rows: list[Row] = field(default_factory=list)

    def _answerable(self):
        return [r for r in self.rows if r.answerable]

    def _unanswerable(self):
        return [r for r in self.rows if not r.answerable]

    def metrics(self) -> dict[str, str]:
        ans, una = self._answerable(), self._unanswerable()
        pct = lambda xs: f"{100 * sum(xs) / len(xs):.0f}%" if xs else "–"  # noqa: E731
        m = {
            "Retrieval hit@k": pct([r.hit for r in ans]),
            "MRR@k": f"{statistics.mean(r.reciprocal_rank for r in ans):.2f}" if ans else "–",
        }
        graded = [r.correct for r in ans if r.correct is not None]
        if graded:
            m["Answer accuracy"] = pct(graded)
        abst = [r.correct for r in una if r.correct is not None]
        if abst:
            m["Correct “not in the documents”"] = pct(abst)
        m["Answerable questions blocked by the gate"] = str(sum(not r.grounded for r in ans))
        timed = [r.seconds for r in self.rows if r.seconds]
        if timed:
            m["Median time per answer"] = f"{statistics.median(timed):.1f} s"
        return m


def best_threshold(answerable: list[float], unanswerable: list[float], miss_cost: float = 2.0) -> float:
    """Relevance gate that separates the two groups best, from the best similarity per question.

    Blocking an answerable question costs ``miss_cost``; letting an unanswerable one through
    costs 1, because the prompt still tells the model to say it doesn't know. Returns the
    midpoint of the best gap, rounded down to two decimals."""
    values = sorted(set(answerable + unanswerable))
    candidates = [0.0] + [(a + b) / 2 for a, b in zip(values, values[1:])]
    if values:
        candidates.append(values[-1] + 0.01)

    def cost(t: float) -> float:
        return miss_cost * sum(r < t for r in answerable) + sum(r >= t for r in unanswerable)

    best = min(candidates, key=lambda t: (cost(t), -t))  # on ties, the stricter gate
    return int(best * 100) / 100


def run(modes: list[str], limit: int | None, retrieval_only: bool) -> list[ModeReport]:
    from rag.answer import answer_question, retrieve

    items = [json.loads(line) for line in QUESTIONS.read_text().splitlines() if line.strip()]
    if limit:
        answerable = [q for q in items if q["article"]][:limit]
        items = answerable + [q for q in items if not q["article"]][: max(1, limit // 3)]

    reports = []
    for mode in modes:
        report = ModeReport(mode)
        pause = float(os.getenv("RAG_EVAL_PAUSE", "0"))
        for item in items:
            if pause:
                time.sleep(pause)
            row = Row(question=item["question"], answerable=bool(item["article"]))
            result = retrieve(item["question"], mode=mode)
            row.best_relevance = result.best_relevance
            if row.answerable:
                for rank, p in enumerate(result.passages, start=1):
                    if item["article"] in p.articles.split(","):
                        row.hit, row.reciprocal_rank = True, 1.0 / rank
                        break
            if not retrieval_only:
                start = time.perf_counter()
                ans = answer_question(item["question"], mode=mode)
                row.seconds = time.perf_counter() - start
                row.answer, row.grounded = ans.text, ans.grounded
                if row.answerable:
                    row.correct = ans.grounded and judge(item["question"], item["expected"], ans.text, item["keywords"])
                else:
                    row.correct = (not ans.grounded) or is_abstention(ans.text)
            status = {True: "✅", False: "❌", None: "·"}[row.correct]
            print(f"[{mode}] {status} hit={int(row.hit)} rel={row.best_relevance:.2f}  {row.question}")
            report.rows.append(row)
        reports.append(report)
    return reports


def to_markdown(reports: list[ModeReport]) -> str:
    names = list(reports[0].metrics())
    lines = [
        "# Evaluation results",
        "",
        f"Generated on {date.today().isoformat()} by `python -m eval.run_eval`. "
        f"LLM `{config.LLM_MODEL}`, embeddings `{config.EMBED_MODEL}`, judge `{config.JUDGE_MODEL}`, "
        f"chunks {config.CHUNK_SIZE}/{config.CHUNK_OVERLAP}, top-k {config.TOP_K}, "
        f"relevance gate {config.MIN_RELEVANCE:.2f}.",
        "",
        "| Metric | " + " | ".join(r.mode for r in reports) + " |",
        "|---|" + "---|" * len(reports),
    ]
    for name in names:
        lines.append(f"| {name} | " + " | ".join(r.metrics().get(name, "–") for r in reports) + " |")

    rel_ans = [r.best_relevance for r in reports[0].rows if r.answerable]
    rel_una = [r.best_relevance for r in reports[0].rows if not r.answerable]
    if rel_ans and rel_una:
        lines += [
            "",
            "**Relevance gate calibration** (best cosine similarity per question): "
            f"answerable min {min(rel_ans):.2f} / median {statistics.median(rel_ans):.2f}; "
            f"not answerable median {statistics.median(rel_una):.2f} / max {max(rel_una):.2f}. "
            f"Suggested gate for this embedding model: **{best_threshold(rel_ans, rel_una):.2f}**.",
        ]

    failures = [(rep.mode, r) for rep in reports for r in rep.rows if r.correct is False or (r.answerable and not r.hit)]
    if failures:
        lines += ["", "## Misses", "", "| Mode | Question | Article found | Answer |", "|---|---|---|---|"]
        for mode, r in failures:
            answer = r.answer.replace("\n", " ").replace("|", "\\|")[:160]
            found = ("yes" if r.hit else "no") if r.answerable else "– (not answerable)"
            lines.append(f"| {mode} | {r.question} | {found} | {answer} |")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--modes", nargs="+", default=["hybrid", "vector"], choices=["hybrid", "vector"])
    parser.add_argument("--limit", type=int, help="Only the first N answerable questions (quick runs).")
    parser.add_argument("--retrieval-only", action="store_true", help="Skip the LLM: retrieval metrics only.")
    parser.add_argument("--out", type=Path, default=RESULTS)
    parser.add_argument(
        "--suggest-threshold", action="store_true", help="Retrieval only; print a calibrated RAG_MIN_RELEVANCE."
    )
    args = parser.parse_args()

    if args.suggest_threshold:
        rows = run(["hybrid"], args.limit, retrieval_only=True)[0].rows
        threshold = best_threshold(
            [r.best_relevance for r in rows if r.answerable], [r.best_relevance for r in rows if not r.answerable]
        )
        print(f"{threshold:.2f}")
        return

    reports = run(args.modes, args.limit, args.retrieval_only)
    markdown = to_markdown(reports)
    args.out.write_text(markdown)
    print("\n" + markdown)


if __name__ == "__main__":
    main()
