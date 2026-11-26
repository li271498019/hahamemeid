"""Public checker. It never awards points. RPC failure is 'unclear', not a discrepancy."""

import json

from tools.season1.hashutil import keccak256


REGISTRATION_TYPE = "https://eips.ethereum.org/EIPS/eip-8004#registration-v1"


def task_pack_hash(body: dict) -> str:
    raw = json.dumps(body, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return "0x" + keccak256(raw).hex()


def registration_format(document):
    """Return match / discrepancy / unclear. A format miss is not a separate reward."""
    if document is None:
        return "unclear"
    if not isinstance(document, dict):
        return "discrepancy"
    if document.get("type") == REGISTRATION_TYPE:
        return "match"
    return "discrepancy"


def check_scores(expect, observed, rpc_error=False):
    """expect and observed are {agentId: {count, sum, generation}} or None if unread.

    observed is None when the RPC did not answer. That is unclear, even if the
    task pack expected zeros.
    """
    if rpc_error or observed is None:
        return "unclear"
    if expect.keys() != observed.keys():
        return "discrepancy"
    for key, want in expect.items():
        got = observed[key]
        if int(want["count"]) != int(got["count"]) or int(want["sum"]) != int(got["sum"]):
            return "discrepancy"
        if int(want["generation"]) != int(got["generation"]):
            return "discrepancy"
    return "match"


def last_rating_per_rater(events):
    """events: {agentId, raterAiId, stars, block, logIndex}. Count is unique raters."""
    latest = {}
    for event in sorted(events, key=lambda row: (row["block"], row["logIndex"])):
        latest[(event["agentId"], event["raterAiId"])] = event
    by_agent = {}
    for (agent_id, _rater), event in latest.items():
        bucket = by_agent.setdefault(agent_id, {"count": 0, "sum": 0})
        bucket["count"] += 1
        bucket["sum"] += int(event["stars"])
    return by_agent


def verdict_code(verdict: str) -> int:
    if verdict == "match":
        return 0
    if verdict == "discrepancy":
        return 1
    raise ValueError("unclear is not a payable verdict")
