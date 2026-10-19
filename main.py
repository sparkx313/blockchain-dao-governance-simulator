import math
import random
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class Voter:
    address: str
    tokens: float
    preference: float  # -1 to 1, negative=against, positive=for

@dataclass
class Proposal:
    id: str
    title: str
    yes_votes: float = 0
    no_votes: float = 0
    quorum_threshold: float = 0.10
    approval_threshold: float = 0.50

    @property
    def total_votes(self): return self.yes_votes + self.no_votes
    @property
    def approval_rate(self): return self.yes_votes / max(self.total_votes, 1)

def token_weighted_vote(voters: List[Voter], proposal: Proposal) -> bool:
    for v in voters:
        if v.preference > 0:
            proposal.yes_votes += v.tokens * v.preference
        else:
            proposal.no_votes += v.tokens * abs(v.preference)
    return proposal.approval_rate > proposal.approval_threshold

def quadratic_vote(voters: List[Voter], proposal: Proposal) -> bool:
    p = Proposal(id=proposal.id, title=proposal.title,
                 quorum_threshold=proposal.quorum_threshold,
                 approval_threshold=proposal.approval_threshold)
    for v in voters:
        votes = math.sqrt(v.tokens)
        if v.preference > 0:
            p.yes_votes += votes * v.preference
        else:
            p.no_votes += votes * abs(v.preference)
    return p.approval_rate > p.approval_threshold

def simulate_dao(n_voters: int = 100, whale_fraction: float = 0.05):
    voters = []
    for i in range(n_voters):
        is_whale = i < int(n_voters * whale_fraction)
        tokens = random.uniform(100_000, 1_000_000) if is_whale else random.uniform(10, 5_000)
        pref = random.uniform(-1, 1)
        voters.append(Voter(f"0x{i:04x}", tokens, pref))

    p1 = Proposal("P-001", "Fund Protocol Development", quorum_threshold=0.05)
    p2 = Proposal("P-001-qv", "Fund Protocol Development (QV)")

    tw_result = token_weighted_vote(voters, p1)
    qv_result = quadratic_vote(voters, p2)

    print(f"Proposal: {p1.title}")
    print(f"  Token-Weighted : {'PASSED ✅' if tw_result else 'FAILED ❌'}  (yes={p1.approval_rate:.1%})")
    print(f"  Quadratic Vote : {'PASSED ✅' if qv_result else 'FAILED ❌'}")
    total_tokens = sum(v.tokens for v in voters)
    whale_tokens = sum(v.tokens for v in voters if v.tokens > 10_000)
    print(f"  Whale dominance: {whale_tokens/total_tokens:.1%} of total supply")

if __name__ == "__main__":
    simulate_dao(n_voters=500, whale_fraction=0.02)
