"""Replacement gates, explicit legacy upgrade, and preservation of old history."""
import copy
import hashlib
import json
from pathlib import Path
import unittest

import test_state as harness

odrd = harness.odrd


FIXTURES = Path(__file__).with_name("fixtures")


def rehash(document):
    previous = ""
    for seq, event in enumerate(document["events"], 1):
        event.update(seq=seq, previous=previous)
        event.pop("hash", None)
        event["hash"] = hashlib.sha256(odrd.encoded(event)).hexdigest()
        previous = event["hash"]
    return document


def event_after(document, kind, data):
    result = copy.deepcopy(document)
    result["events"].append({"at": odrd.utc(), "type": kind, "data": data})
    return rehash(result)


class ReplacementUpgradeTests(unittest.TestCase):
    # Reuse the CLI harness without inheriting and rerunning its 23 test cases.
    setUp = harness.StateTests.setUp
    tearDown = harness.StateTests.tearDown
    cli = harness.StateTests.cli
    add = harness.StateTests.add
    proof = harness.StateTests.proof
    decide = harness.StateTests.decide
    revise = harness.StateTests.revise
    statuses = harness.StateTests.statuses

    def fixture(self, name="replacement_revision"):
        self.state.write_bytes((FIXTURES / f"legacy-{name}.json").read_bytes())
        return json.loads(self.state.read_text())

    def replan(self, old, replacement):
        return self.cli("replan", "--node", old, "--replacement", replacement,
                        "--reason", "Current approach replaced")

    def verified(self, key):
        self.proof(key)
        self.decide(key)

    def setup_replacement_graph(self, controls=False, chain=False):
        self.add("old")
        self.add("replacement")
        if chain:
            self.add("newest")
        self.add("consumer", depends=["old"])
        self.add("consumer_child", parent="consumer")
        self.add("transitive", depends=["consumer"])
        self.add("unrelated")
        if controls:
            self.add("blocked", depends=["old"], optional=True)
            self.add("rejected", kind="hypothesis", depends=["old"], optional=True)
            self.decide("blocked", "block")
            self.proof("rejected", "contradicts")
            self.decide("rejected", "reject")
        self.replan("old", "replacement")
        for key in ["replacement"] + (["newest"] if chain else []) + ["consumer_child", "consumer", "transitive", "unrelated", "root"]:
            self.verified(key)
        self.assertTrue(self.cli("status")["mission_verified"])

    def test_new_journal_binds_initial_schema_in_hashed_init(self):
        document = json.loads(self.state.read_text())
        self.assertEqual(document["schema"], 2)
        self.assertEqual(document["events"][0]["data"]["schema_version"], 2)
        self.add("child")
        self.assertEqual(json.loads(self.state.read_text())["schema"], 2)
        self.assertFalse(self.cli("status")["upgrade_required"])
        self.cli("upgrade", "--reason", "Already version 2", ok=False, code=2)

    def test_revision_invalidates_replacement_consumers_and_preserves_unrelated_and_controls(self):
        self.setup_replacement_graph(controls=True)
        before = self.statuses()
        self.revise("replacement")
        self.verified("replacement")
        after = self.statuses()
        for key in ("consumer", "consumer_child", "transitive"):
            self.assertGreater(after[key]["revision"], before[key]["revision"])
            self.assertEqual(after[key]["status"], "pending")
            self.decide(key, ok=False)
        self.assertEqual(after["unrelated"]["revision"], before["unrelated"]["revision"])
        self.assertEqual(after["unrelated"]["status"], "complete")
        for key, status in (("blocked", "blocked"), ("rejected", "rejected")):
            self.assertEqual(after[key]["status"], status)
            self.assertEqual(after[key]["control_decision"], before[key]["control_decision"])
        for key in ("consumer_child", "consumer", "transitive", "root"):
            self.verified(key)
        self.assertTrue(self.cli("validate")["mission_verified"])

    def test_new_evidence_and_child_add_follow_effective_gate(self):
        self.setup_replacement_graph()
        before = self.statuses()
        self.proof("replacement")
        self.decide("replacement")
        self.assertEqual(self.statuses()["consumer"]["status"], "pending")
        self.assertGreater(self.statuses()["consumer"]["revision"], before["consumer"]["revision"])
        for key in ("consumer_child", "consumer", "transitive", "root"):
            self.verified(key)
        before = self.statuses()
        self.add("replacement_child", parent="replacement")
        self.verified("replacement_child")
        self.verified("replacement")
        after = self.statuses()
        self.assertEqual(after["consumer"]["status"], "pending")
        self.assertGreater(after["consumer"]["revision"], before["consumer"]["revision"])
        self.assertEqual(after["unrelated"]["status"], "complete")

    def test_chained_replan_never_retains_old_consumer_proof(self):
        self.setup_replacement_graph(chain=True)
        before = self.statuses()
        self.replan("replacement", "newest")
        after = self.statuses()
        self.assertEqual(after["newest"]["status"], "complete")
        self.assertEqual(after["consumer"]["status"], "pending")
        self.assertGreater(after["consumer"]["revision"], before["consumer"]["revision"])
        self.decide("consumer", ok=False)
        for key in ("consumer_child", "consumer", "transitive", "root"):
            self.verified(key)
        self.assertTrue(self.cli("status")["mission_verified"])
        self.proof("newest")
        self.decide("newest")
        self.assertEqual(self.statuses()["consumer"]["status"], "pending")

    def test_legacy_readback_is_readonly_and_never_claims_current_completion(self):
        for name in ("replacement_revision", "replacement_evidence", "chained_replan"):
            with self.subTest(name=name):
                self.fixture(name)
                before = self.state.read_bytes()
                for command in ("status", "validate", "next"):
                    result = self.cli(command)
                    self.assertFalse(result["mission_verified"])
                    self.assertTrue(result["upgrade_required"])
                    self.assertEqual((result["initial_schema"], result["current_schema"]), (1, 1))
                    self.assertFalse(any(row["status"] in {"complete", "retained"} for row in result["nodes"]))
                    if command == "next":
                        self.assertEqual(result["recommended"], [])
                    if command == "validate":
                        self.assertTrue(result["valid"])
                    self.assertEqual(self.state.read_bytes(), before)

    def test_all_ordinary_legacy_writes_require_explicit_upgrade(self):
        self.fixture()
        calls = [
            ("add", "--id", "extra", "--parent", "root", "--kind", "outcome", "--outcome", "extra", "--criterion", "extra checked", "--uncertainty", "unknown", "--risk", "2", "--information", "2", "--cost", "1"),
            ("evidence", "--node", "root", "--criterion", "root checked", "--source", "urn:test:root", "--observation", "checked", "--verdict", "supports"),
            ("decide", "--node", "root", "--action", "complete", "--reason", "Recheck"),
            ("resolve", "--node", "root", "--evidence", "e1", "--basis", "e2", "--reason", "Recheck"),
            ("revise", "--node", "root", "--outcome", "Recheck", "--criterion", "root checked", "--reason", "Recheck"),
            ("replan", "--node", "replacement", "--replacement", "consumer", "--reason", "Recheck"),
        ]
        for command, *args in calls:
            with self.subTest(command=command):
                run = self.cli(command, *args, ok=False, code=2)
                self.assertIn("explicit upgrade", run.stderr)
        self.cli("upgrade", "--reason", "", ok=False, code=2)
        self.cli("upgrade", ok=False, code=2)

    def test_explicit_upgrade_preserves_history_and_requires_then_allows_fresh_recovery(self):
        for name in ("replacement_revision", "replacement_evidence", "chained_replan"):
            with self.subTest(name=name):
                before = self.fixture(name)
                old = odrd.load(self.state)
                result = self.cli("upgrade", "--reason", "Revalidate legacy evidence with resolved gates")
                self.assertFalse(result["mission_verified"])
                after = json.loads(self.state.read_text())
                self.assertEqual(after["schema"], before["schema"])
                self.assertEqual(after["events"][:-1], before["events"])
                self.assertEqual(after["events"][-1]["type"], "upgrade")
                self.assertEqual(after["events"][-1]["data"]["to_schema"], 2)
                new = odrd.load(self.state)
                self.assertEqual(new.current_schema, 2)
                self.assertFalse(new.upgrade_required)
                self.assertEqual(new.original_objective, old.original_objective)
                self.assertEqual(new.original_criteria, old.original_criteria)
                self.assertEqual(new.original_constraints, old.original_constraints)
                self.assertEqual(new.controls, old.controls)
                for key in old.nodes:
                    self.assertEqual(odrd.current(new.node(key))["revision"],
                                     odrd.current(old.node(key))["revision"] + int(old.active(key)))
                    self.assertFalse(new.verified(key))
                self.decide("root", ok=False)
                self.cli("upgrade", "--reason", "Repeat upgrade", ok=False, code=2)
                for key in ("replacement", "newest", "consumer_child", "consumer", "transitive", "root"):
                    if key in new.nodes and new.active(key):
                        for criterion in odrd.current(new.node(key))["criteria"]:
                            self.proof(key, criterion=criterion)
                        self.decide(key)
                self.assertTrue(self.cli("validate")["mission_verified"])
                self.assertEqual(json.loads(self.state.read_text())["events"][:len(before["events"])], before["events"])
                target = "newest" if name == "chained_replan" else "replacement"
                self.proof(target, criterion=target + " checked")
                self.decide(target)
                self.assertEqual(self.statuses()["consumer"]["status"], "pending")

    def test_upgrade_keeps_block_reject_and_original_constraints(self):
        before = self.fixture("controls")
        old = odrd.load(self.state)
        self.cli("upgrade", "--reason", "Preserve controls while revalidating")
        new = odrd.load(self.state)
        self.assertEqual(new.controls, old.controls)
        self.assertEqual(new.original_constraints, ["preserve original input"])
        self.assertEqual(new.original_criteria, ["result accepted"])
        self.assertEqual(new.original_constraints, odrd.current(new.node("root"))["constraints"])
        self.assertEqual(json.loads(self.state.read_text())["events"][:-1], before["events"])
        rows = self.statuses()
        self.assertEqual(rows["root"]["status"], "blocked")
        self.assertEqual(rows["blocked"]["status"], "blocked")
        self.assertEqual(rows["theory"]["status"], "rejected")
        self.assertEqual(rows["unrelated"]["status"], "pending")
        self.assertEqual(self.cli("next")["recommended"], [])
        self.decide("root", ok=False)
        self.decide("blocked", ok=False)
        self.decide("theory", "retain", ok=False)

    def test_header_flip_and_invalid_version_types_never_enable_old_proof(self):
        legacy = self.fixture()
        for value in (2, 3, True, "1"):
            with self.subTest(header=value):
                forged = copy.deepcopy(legacy)
                forged["schema"] = value
                self.state.write_text(json.dumps(forged))
                self.cli("validate", ok=False, code=2)
        for value in (2, True, "1", 3):
            with self.subTest(marker=value):
                forged = copy.deepcopy(legacy)
                forged["events"][0]["data"]["schema_version"] = value
                self.state.write_text(json.dumps(rehash(forged)))
                self.cli("validate", ok=False, code=2)

    def test_incomplete_or_malformed_upgrade_is_rejected_without_write(self):
        original = self.fixture()
        ledger = odrd.load(self.state)
        valid = {"to_schema": 2, "reason": "Explicit migration", "updates":
                 ledger.updates(key for key in ledger.nodes if ledger.active(key))}
        mutations = []
        for target in (1, 3, True, "2"):
            data = copy.deepcopy(valid)
            data["to_schema"] = target
            mutations.append(data)
        data = copy.deepcopy(valid)
        data["updates"].pop("root")
        mutations.append(data)
        data = copy.deepcopy(valid)
        data["updates"].update(ledger.updates(["old"]))
        mutations.append(data)
        data = copy.deepcopy(valid)
        data["updates"]["consumer"]["revision"] += 1
        mutations.append(data)
        data = copy.deepcopy(valid)
        data["updates"]["root"]["criteria"] = ["easier acceptance"]
        mutations.append(data)
        data = copy.deepcopy(valid)
        data["reason"] = ""
        mutations.append(data)
        for index, data in enumerate(mutations):
            with self.subTest(mutation=index):
                forged = event_after(original, "upgrade", data)
                self.state.write_text(json.dumps(forged))
                self.cli("validate", ok=False, code=2)
        self.state.write_text(json.dumps(event_after(event_after(original, "upgrade", valid), "upgrade", valid)))
        self.cli("validate", ok=False, code=2)


if __name__ == "__main__":
    unittest.main()
