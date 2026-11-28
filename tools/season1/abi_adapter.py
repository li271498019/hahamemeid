"""Load D's handoff. A null module stays null. Mock is only the fallback when no file exists."""

import json
import os
from pathlib import Path

from tools.season1.hashutil import keccak256

DEFAULT_HANDOFF = Path(__file__).resolve().parents[2] / "tools" / "deploy-panel" / "public" / "season1" / "handoff.json"

MOCK_EVENTS = [
    ("DayRootSet", "DayRootSet(uint64,bytes32,uint64,bytes32,uint16,uint16)"),
    ("Redeemed", "Redeemed(uint256,bytes32,address,address,uint8,string,uint64,uint8,uint256,bytes32)"),
    ("FulfillmentAttested", "FulfillmentAttested(uint256,uint256,address,bytes32)"),
    ("Verified", "Verified(bytes32,uint64,uint256,uint64,uint8,bytes32,uint256)"),
    ("FindingCommitted", "FindingCommitted(bytes32,bytes32,address,bytes32)"),
    ("CanonicalAssigned", "CanonicalAssigned(bytes32,bytes32)"),
    ("FindingPaid", "FindingPaid(bytes32,bytes32,bytes32,address,uint256)"),
    ("ValidatorSet", "ValidatorSet(address,bool)"),
    ("RewardSignerSet", "RewardSignerSet(address)"),
    ("TaskPackSet", "TaskPackSet(uint64,bytes32)"),
    ("AccidentDeclared", "AccidentDeclared(uint256,bytes32,address,bytes32)"),
    ("AccidentRefunded", "AccidentRefunded(uint256,bytes32,uint256)"),
    ("AccidentCompensationDeferred", "AccidentCompensationDeferred(uint256,bytes32)"),
    ("AccidentCompensated", "AccidentCompensated(uint256,bytes32,uint256)"),
]


def topic0(signature: str) -> str:
    return "0x" + keccak256(signature.encode()).hex()


def mock_abi():
    return [{"name": name, "signature": sig, "topic0": topic0(sig), "source": "mock"}
            for name, sig in MOCK_EVENTS]


def handoff_path(explicit=None):
    if explicit:
        return explicit
    env = os.environ.get("SEASON1_HANDOFF", "")
    if env:
        return env
    if DEFAULT_HANDOFF.is_file():
        return str(DEFAULT_HANDOFF)
    return ""


def load_adapter(path=None):
    """Return the handoff check. A null module is not replaced with a fake address."""
    path = handoff_path(path)
    if not path or not os.path.isfile(path):
        return {"events": mock_abi(), "mainnet_module": None, "source": "mock", "deployed": False,
                "chainId": None, "path": path or None}
    with open(path, "r", encoding="utf-8") as handle:
        doc = json.load(handle)
    if doc.get("kind") != "season1-handoff":
        raise ValueError("handoff kind")
    mainnet = doc.get("mainnet") or {}
    if mainnet.get("chainId") not in (None, 56):
        raise ValueError("mainnet chainId must be 56")
    module = mainnet.get("module")
    if module in (None, "", "0x" + "00" * 20):
        module = None
    events = doc.get("events") or []
    names = {row["name"] for row in events}
    if "MintConfirmed" in names:
        raise ValueError("handoff still emits MintConfirmed")
    if "FulfillmentAttested" not in names:
        raise ValueError("handoff is missing FulfillmentAttested")
    for row in events:
        expect = topic0(row["signature"])
        if row.get("topic0", "").lower() != expect:
            raise ValueError("topic0 mismatch for %s" % row["name"])
    abi_path = doc.get("abiPath")
    if abi_path:
        repo_abi = Path(path).resolve().parents[4] / abi_path
        if repo_abi.is_file():
            abi = json.loads(repo_abi.read_text())
            abi_names = {item.get("name") for item in abi if item.get("type") == "event"}
            if "FulfillmentAttested" not in abi_names or "MintConfirmed" in abi_names:
                raise ValueError("abi file events disagree with handoff")
    return {
        "events": events,
        "mainnet_module": module,
        "source": "handoff",
        "deployed": module is not None,
        "chainId": mainnet.get("chainId"),
        "path": path,
        "bytecodeBytes": doc.get("bytecodeBytes"),
    }
