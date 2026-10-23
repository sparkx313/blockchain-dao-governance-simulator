# DAO Governance Ballot Analyzer

Compare recorded proposal ballots under token-weighted and quadratic-credit voting rules. The tool analyzes a ballot CSV you supply; it does not generate voters, proposals, or results.

## Ballot CSV

Required columns:

| Column | Meaning |
| --- | --- |
| `proposal_id` | Stable proposal identifier |
| `title` | Proposal title, consistent across its rows |
| `voter_id` | Stable voter identifier |
| `vote` | `yes`, `no`, or `abstain` |
| `voting_power` | Token voting power for this voter on this proposal |
| `quadratic_credits` | Credits spent on this vote; abstentions spend zero |
| `quadratic_budget` | The voter's total credit budget, repeated consistently on each row |

Include one row for every eligible voter on every proposal. Use `abstain` rows for eligible voters who did not cast a vote so turnout denominators include them. Each voter may have one row per proposal, and the sum of their `quadratic_credits` across the CSV cannot exceed their budget.

For quadratic voting, credits represent cost: spending `c` credits casts `sqrt(c)` votes in the indicated direction. This is distinct from applying a square-root transform to token balances.

## Analyze

Requires Python 3.10 or newer and has no third-party dependencies.

```bash
python main.py --input path/to/ballots.csv --output governance_results.csv --quorum 0.10 --approval-threshold 0.50
```

The output contains two rows per proposal. Token-weighted turnout is yes/no token power divided by eligible token supply. Quadratic turnout is credits spent divided by eligible credit budgets. A mechanism passes when its turnout meets `--quorum` and its yes share meets `--approval-threshold`.

## Scope

This analyzes supplied ballots; it is not connected to a blockchain or a DAO contract. It does not simulate conviction voting, holographic consensus, voter turnout, Sybil resistance, or attack costs. The outcome depends on the eligibility list, budgets, and thresholds in the input and command line.
