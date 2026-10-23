"""Analyze DAO ballots under token-weighted and quadratic voting rules."""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

REQUIRED_COLUMNS = {
    "proposal_id",
    "title",
    "voter_id",
    "vote",
    "voting_power",
    "quadratic_credits",
    "quadratic_budget",
}


def parse_nonnegative(value: str, field: str, row_number: int) -> Decimal:
    try:
        number = Decimal(value.strip())
    except (InvalidOperation, AttributeError) as exc:
        raise ValueError(f"Row {row_number}: {field} must be a finite non-negative number.") from exc
    if not number.is_finite() or number < 0:
        raise ValueError(f"Row {row_number}: {field} must be a finite non-negative number.")
    return number


def load_ballots(path: Path) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Decimal]]:
    if not path.is_file():
        raise ValueError(f"Ballot CSV does not exist: {path}")

    proposals: dict[str, list[dict[str, Any]]] = defaultdict(list)
    titles: dict[str, str] = {}
    budgets: dict[str, Decimal] = {}
    credits_spent: defaultdict[str, Decimal] = defaultdict(Decimal)
    seen_ballots: set[tuple[str, str]] = set()

    with path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames is None:
            raise ValueError("Ballot CSV is missing a header row.")
        reader.fieldnames = [name.strip() for name in reader.fieldnames]
        if any(not name for name in reader.fieldnames):
            raise ValueError("CSV column names cannot be empty.")
        if len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError("CSV column names must be unique after trimming whitespace.")
        missing = REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing:
            raise ValueError("CSV is missing required column(s): " + ", ".join(sorted(missing)))

        for row_number, row in enumerate(reader, start=2):
            if None in row:
                raise ValueError(f"Row {row_number}: contains more fields than the header.")
            proposal_id = (row.get("proposal_id") or "").strip()
            title = (row.get("title") or "").strip()
            voter_id = (row.get("voter_id") or "").strip()
            vote = (row.get("vote") or "").strip().lower()
            if not proposal_id or not title or not voter_id:
                raise ValueError(f"Row {row_number}: proposal_id, title, and voter_id are required.")
            if vote not in {"yes", "no", "abstain"}:
                raise ValueError(f"Row {row_number}: vote must be yes, no, or abstain.")
            ballot_key = (proposal_id, voter_id)
            if ballot_key in seen_ballots:
                raise ValueError(f"Row {row_number}: duplicate ballot for voter {voter_id} on {proposal_id}.")
            seen_ballots.add(ballot_key)
            if proposal_id in titles and titles[proposal_id] != title:
                raise ValueError(f"Row {row_number}: proposal {proposal_id} has inconsistent titles.")
            titles[proposal_id] = title

            voting_power = parse_nonnegative(row.get("voting_power"), "voting_power", row_number)
            quadratic_credits = parse_nonnegative(
                row.get("quadratic_credits"), "quadratic_credits", row_number
            )
            quadratic_budget = parse_nonnegative(
                row.get("quadratic_budget"), "quadratic_budget", row_number
            )
            if voter_id in budgets and budgets[voter_id] != quadratic_budget:
                raise ValueError(f"Row {row_number}: quadratic_budget must be consistent for voter {voter_id}.")
            budgets[voter_id] = quadratic_budget
            credits_spent[voter_id] += quadratic_credits
            if vote == "abstain" and quadratic_credits != 0:
                raise ValueError(f"Row {row_number}: abstaining ballots must spend zero quadratic credits.")
            proposals[proposal_id].append(
                {
                    "title": title,
                    "voter_id": voter_id,
                    "vote": vote,
                    "voting_power": voting_power,
                    "quadratic_credits": quadratic_credits,
                    "quadratic_budget": quadratic_budget,
                }
            )

    if not proposals:
        raise ValueError("Ballot CSV contains no ballot rows.")
    for voter_id, spent in credits_spent.items():
        if spent > budgets[voter_id]:
            raise ValueError(
                f"Voter {voter_id} spent {spent} quadratic credits, exceeding their budget {budgets[voter_id]}."
            )
    return proposals, budgets


def ratio(numerator: Decimal, denominator: Decimal) -> Decimal:
    return numerator / denominator if denominator else Decimal(0)


def analyze(
    proposals: dict[str, list[dict[str, Any]]],
    quorum_threshold: Decimal,
    approval_threshold: Decimal,
) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for proposal_id, ballots in sorted(proposals.items()):
        title = ballots[0]["title"]
        token_supply = sum((ballot["voting_power"] for ballot in ballots), Decimal(0))
        quadratic_budget = sum((ballot["quadratic_budget"] for ballot in ballots), Decimal(0))
        if token_supply <= 0 or quadratic_budget <= 0:
            raise ValueError(f"Proposal {proposal_id} needs positive eligible token supply and quadratic budget.")

        yes_tokens = sum((ballot["voting_power"] for ballot in ballots if ballot["vote"] == "yes"), Decimal(0))
        no_tokens = sum((ballot["voting_power"] for ballot in ballots if ballot["vote"] == "no"), Decimal(0))
        participating_tokens = yes_tokens + no_tokens
        token_yes_share = ratio(yes_tokens, participating_tokens)
        token_turnout = ratio(participating_tokens, token_supply)

        yes_quadratic_votes = sum(
            (ballot["quadratic_credits"].sqrt() for ballot in ballots if ballot["vote"] == "yes"),
            Decimal(0),
        )
        no_quadratic_votes = sum(
            (ballot["quadratic_credits"].sqrt() for ballot in ballots if ballot["vote"] == "no"),
            Decimal(0),
        )
        spent_credits = sum((ballot["quadratic_credits"] for ballot in ballots), Decimal(0))
        quadratic_votes = yes_quadratic_votes + no_quadratic_votes
        quadratic_yes_share = ratio(yes_quadratic_votes, quadratic_votes)
        quadratic_turnout = ratio(spent_credits, quadratic_budget)
        cast_count = sum(ballot["vote"] != "abstain" for ballot in ballots)

        methods = [
            (
                "token_weighted",
                token_supply,
                participating_tokens,
                token_turnout,
                yes_tokens,
                no_tokens,
                token_yes_share,
            ),
            (
                "quadratic_credits",
                quadratic_budget,
                spent_credits,
                quadratic_turnout,
                yes_quadratic_votes,
                no_quadratic_votes,
                quadratic_yes_share,
            ),
        ]
        for method, eligible, participation, turnout, yes, no, yes_share in methods:
            passed = (
                participation > 0
                and turnout >= quorum_threshold
                and yes_share >= approval_threshold
            )
            results.append(
                {
                    "proposal_id": proposal_id,
                    "title": title,
                    "mechanism": method,
                    "eligible_weight": format(eligible, "f"),
                    "participation_weight": format(participation, "f"),
                    "turnout": format(turnout, ".6f"),
                    "yes_weight": format(yes, ".6f"),
                    "no_weight": format(no, ".6f"),
                    "yes_share": format(yes_share, ".6f") if participation > 0 else "",
                    "ballots_cast": str(cast_count),
                    "eligible_voters": str(len(ballots)),
                    "quorum_threshold": format(quorum_threshold, "f"),
                    "approval_threshold": format(approval_threshold, "f"),
                    "passed": str(passed).lower(),
                }
            )
    return results


def parse_threshold(value: str, label: str, allow_zero: bool) -> Decimal:
    try:
        threshold = Decimal(value)
    except InvalidOperation as exc:
        raise argparse.ArgumentTypeError(f"{label} must be a number between 0 and 1.") from exc
    if not threshold.is_finite():
        raise argparse.ArgumentTypeError(f"{label} must be a finite number between 0 and 1.")
    lower_bound_ok = threshold >= 0 if allow_zero else threshold > 0
    if not lower_bound_ok or threshold > 1:
        raise argparse.ArgumentTypeError(f"{label} must be between 0 and 1.")
    return threshold


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare token-weighted and quadratic-credit outcomes from supplied DAO ballots."
    )
    parser.add_argument("--input", required=True, type=Path, help="Ballot CSV.")
    parser.add_argument("--output", type=Path, default=Path("governance_results.csv"))
    parser.add_argument("--quorum", type=lambda value: parse_threshold(value, "Quorum", True), default=Decimal("0.10"))
    parser.add_argument("--approval-threshold", type=lambda value: parse_threshold(value, "Approval threshold", False), default=Decimal("0.50"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.input.resolve() == args.output.resolve():
            raise ValueError("Output path must not overwrite the ballot CSV.")
        proposals, _budgets = load_ballots(args.input)
        results = analyze(proposals, args.quorum, args.approval_threshold)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8", newline="") as destination:
            writer = csv.DictWriter(destination, fieldnames=list(results[0]))
            writer.writeheader()
            writer.writerows(results)
    except (OSError, ValueError, csv.Error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"Analyzed {len(proposals)} proposal(s) under two voting mechanisms.")
    print(f"Wrote results to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
