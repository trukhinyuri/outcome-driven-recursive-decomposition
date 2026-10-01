"""Behavioral CLI tests: objective safety, durable history and real gate checks."""
import importlib.util
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "skills/outcome-decomposition/scripts/odrd.py"
spec = importlib.util.spec_from_file_location("odrd", SCRIPT)
odrd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(odrd)


class StateTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.base = Path(self.directory.name).resolve()
        self.state = self.base / "mission.json"
        self.cli("init", "--goal", "Ship a verified result", "--criterion", "result accepted",
                 "--constraint", "preserve original input")

    def tearDown(self):
        self.directory.cleanup()

    def cli(self, command, *args, ok=True, path=None, code=None):
        before = self.state.read_bytes() if self.state.exists() else None
        run = subprocess.run([sys.executable, str(SCRIPT), command, str(path or self.state), *args],
                             capture_output=True, text=True, timeout=10)
        if ok:
            self.assertEqual(run.returncode, 0, run.stderr)
        else:
            self.assertNotEqual(run.returncode, 0, run.stdout)
            if code is not None:
                self.assertEqual(run.returncode, code, run.stderr)
            self.assertEqual(before, self.state.read_bytes() if self.state.exists() else None,
                             "failed command mutated state")
            self.assertFalse(Path(str(self.state) + ".lock").exists())
        return json.loads(run.stdout) if run.stdout and not args[-1:] == ("--summary",) else run

    def add(self, key, parent="root", kind="outcome", criterion=None, **kwargs):
        args = ["--id", key, "--parent", parent, "--kind", kind, "--outcome", f"Deliver {key}",
                "--criterion", criterion or f"{key} checked", "--uncertainty", "not yet tested",
                "--risk", "4", "--cost", "2", "--information", "3"]
        for dependency in kwargs.pop("depends", []):
            args.extend(["--depends", dependency])
        if kwargs.pop("optional", False):
            args.append("--optional")
        return self.cli("add", *args, **kwargs)

    def proof(self, key, verdict="supports", criterion=None, artifact=None, source="urn:test:observed"):
        args = ["--node", key, "--criterion", criterion or ("result accepted" if key == "root" else f"{key} checked"),
                "--source", source, "--observation", "independent readback of the actual result", "--verdict", verdict]
        if artifact:
            args.extend(["--artifact", str(artifact)])
        return self.cli("evidence", *args)["event"]["data"]["id"]

    def decide(self, key, action="complete", ok=True):
        return self.cli("decide", "--node", key, "--action", action, "--reason", "actual criteria readback", ok=ok)

    def revise(self, key, criterion=None, ok=True):
        return self.cli("revise", "--node", key, "--outcome", f"Revised {key}", "--criterion",
                        criterion or ("result accepted" if key == "root" else f"{key} checked"),
                        "--reason", "new input invalidates prior observation", ok=ok)

    def statuses(self):
        return {row["id"]: row for row in self.cli("status")["nodes"]}

    def test_root_needs_own_evidence_and_every_criterion(self):
        self.add("child")
        self.proof("child")
        self.decide("child")
        self.decide("root", ok=False)
        self.assertFalse(self.cli("status")["mission_verified"])
        self.proof("root")
        self.decide("root")
        self.assertTrue(self.cli("validate")["mission_verified"])
        self.revise("root")
        self.assertEqual(self.cli("status")["original_objective"], "Ship a verified result")
        self.assertEqual(self.statuses()["child"]["revision"], 2)
        self.decide("root", ok=False)
        self.revise("root", criterion="easier substitute", ok=False)

    def test_no_empty_provenance_no_fake_complete_no_overwrite(self):
        self.decide("root", ok=False)
        self.cli("init", "--goal", "replace mission", "--criterion", "anything", ok=False)
        self.cli("evidence", "--node", "root", "--criterion", "result accepted", "--source", "",
                 "--observation", "looks good", "--verdict", "supports", ok=False)
        self.cli("evidence", "--node", "root", "--criterion", "wrong", "--source", "urn:test:readback",
                 "--observation", "looks good", "--verdict", "supports", ok=False)
        self.cli("evidence", "--node", "root", "--criterion", "result accepted", "--source", "trust me",
                 "--observation", "looks good", "--verdict", "supports", ok=False)
        self.proof("root", "inconclusive")
        self.decide("root", ok=False)

    def test_conflict_needs_explicit_justified_resolution(self):
        contradiction = self.proof("root", "contradicts")
        support = self.proof("root")
        self.decide("root", ok=False)
        self.cli("resolve", "--node", "root", "--evidence", contradiction, "--basis", support,
                 "--reason", "", ok=False)
        self.cli("resolve", "--node", "root", "--evidence", contradiction, "--basis", support,
                 "--reason", "Readback confirms the defect was repaired")
        self.decide("root")
        self.assertTrue(self.cli("status")["mission_verified"])
        self.proof("root", "contradicts")
        self.assertEqual(self.statuses()["root"]["status"], "stale")
        self.assertFalse(self.cli("status")["mission_verified"])

    def test_artifact_capture_and_tamper(self):
        artifact = self.base / "result.txt"
        artifact.write_text("actual accepted output", encoding="utf-8")
        self.proof("root", artifact=artifact)
        self.decide("root")
        self.assertTrue(self.cli("validate")["valid"])
        artifact.write_text("unexpected mutation", encoding="utf-8")
        result = self.cli("validate", ok=False, code=1)
        self.assertTrue(result["artifact_errors"])
        self.assertFalse(result["mission_verified"])
        self.decide("root", ok=False)

    def test_dependencies_cycles_orphans_duplicate_ids(self):
        self.add("a")
        self.add("b", depends=["a"])
        self.add("b", ok=False)
        self.add("orphan", parent="absent", ok=False)
        self.add("unknown", depends=["absent"], ok=False)
        self.add("cycle", parent="a", depends=["root"], ok=False)
        self.proof("b")
        self.decide("b", ok=False)
        result = self.cli("next")
        self.assertEqual([r["id"] for r in result["recommended"]], ["a"])
        self.assertIn("not true VOI", result["recommended"][0]["priority_reason"])
        self.proof("a")
        self.decide("a")
        self.proof("b")
        self.decide("b")
        self.assertEqual([r["id"] for r in self.cli("next")["recommended"]], ["root"])

    def test_rejection_pivot_and_hidden_descendants(self):
        self.add("theory", kind="hypothesis")
        self.add("trial", parent="theory", kind="experiment")
        self.proof("theory", "contradicts")
        self.decide("theory", "reject")
        self.proof("root")
        self.decide("root", ok=False)
        self.assertEqual(self.cli("next")["recommended"], [])
        self.add("bad_child", parent="theory", ok=False)
        self.add("alternative")
        self.cli("replan", "--node", "theory", "--replacement", "alternative",
                 "--reason", "test falsified the original route")
        self.assertEqual(self.statuses()["trial"]["status"], "superseded")
        self.assertEqual([r["id"] for r in self.cli("next")["recommended"]], ["alternative"])
        self.proof("alternative")
        self.decide("alternative")
        self.decide("root", ok=False)
        self.proof("root")
        self.decide("root")
        self.assertTrue(self.cli("validate")["mission_verified"])

    def test_optional_rejected_hypothesis_is_knowledge_not_parent_proof(self):
        self.add("speculation", kind="hypothesis", optional=True)
        self.decide("speculation", "reject", ok=False)
        self.proof("speculation", "contradicts")
        self.decide("speculation", "reject")
        self.decide("root", ok=False)
        self.proof("root")
        self.decide("root")
        self.assertTrue(self.cli("status")["mission_verified"])

    def test_revision_invalidates_transitive_dependents_and_history_survives_resume(self):
        self.add("a")
        self.add("descendant", parent="a")
        self.add("b", depends=["a"])
        self.add("c", depends=["b"])
        for key in ["descendant", "a", "b", "c"]:
            self.proof(key)
            self.decide(key)
        before = json.loads(self.state.read_text())["events"]
        before_rows = self.statuses()
        self.revise("a")
        rows = self.statuses()
        self.assertTrue(all(rows[k]["revision"] == before_rows[k]["revision"] + 1 and rows[k]["status"] == "pending"
                            for k in ["a", "descendant", "b", "c"]))
        after = json.loads(self.state.read_text())["events"]
        self.assertEqual(after[:len(before)], before)
        self.decide("b", ok=False)
        self.assertTrue(self.cli("validate")["valid"])

    def test_replan_redirects_dependency_and_invalidates_old_proof(self):
        self.add("a")
        self.add("b", depends=["a"])
        self.proof("a")
        self.decide("a")
        self.proof("b")
        self.decide("b")
        self.add("new")
        old_revision = self.statuses()["b"]["revision"]
        self.cli("replan", "--node", "a", "--replacement", "new", "--reason", "better route")
        self.assertEqual(self.statuses()["b"]["revision"], old_revision + 1)
        self.decide("b", ok=False)
        self.proof("new")
        self.decide("new")
        self.proof("b")
        self.decide("b")
        self.assertEqual(self.statuses()["b"]["status"], "complete")

    def test_replan_cannot_create_dependency_cycle_or_optional_escape(self):
        self.add("a")
        self.add("b", depends=["a"])
        self.cli("replan", "--node", "a", "--replacement", "b", "--reason", "cycle", ok=False)
        self.add("optional", optional=True)
        self.cli("replan", "--node", "a", "--replacement", "optional", "--reason", "drop work", ok=False)
        self.cli("replan", "--node", "root", "--replacement", "a", "--reason", "replace goal", ok=False)

    def test_leaf_revision_never_resurrects_parent_integration(self):
        self.add("a")
        self.add("sibling")
        for key in ("a", "sibling", "root"):
            self.proof(key)
            self.decide(key)
        before = self.statuses()
        self.revise("a")
        self.proof("a")
        self.decide("a")
        rows = self.statuses()
        self.assertEqual(rows["sibling"]["revision"], 1)
        self.assertEqual(rows["sibling"]["status"], "complete")
        self.assertGreater(rows["root"]["revision"], before["root"]["revision"])
        self.assertFalse(self.cli("status")["mission_verified"])
        self.decide("root", ok=False)
        self.proof("root")
        self.decide("root")

    def test_added_work_and_later_observation_need_fresh_integration(self):
        self.proof("root")
        self.decide("root")
        self.add("new_child")
        self.proof("new_child")
        self.decide("new_child")
        self.assertFalse(self.cli("status")["mission_verified"])
        self.proof("root")
        self.decide("root")
        self.proof("new_child")
        self.assertEqual(self.statuses()["new_child"]["status"], "stale")
        self.decide("new_child")
        self.assertFalse(self.cli("status")["mission_verified"])
        self.proof("root")
        self.decide("root")
        self.assertTrue(self.cli("validate")["mission_verified"])

    def test_blocked_root_survives_child_observation_and_child_revision(self):
        self.add("child")
        decision = self.decide("root", "block")["event"]
        self.proof("child")
        rows = self.statuses()
        self.assertEqual(rows["root"]["status"], "blocked")
        self.assertEqual(rows["root"]["control_decision"]["seq"], decision["seq"])
        self.assertLess(rows["root"]["control_decision"]["revision"], rows["root"]["revision"])
        self.assertEqual(self.cli("next")["recommended"], [])
        self.decide("child", ok=False)
        self.revise("child")
        self.assertEqual(self.statuses()["root"]["status"], "blocked")
        self.assertEqual(self.cli("next")["recommended"], [])
        self.revise("root")
        self.assertEqual(self.statuses()["root"]["status"], "pending")
        self.assertEqual([r["id"] for r in self.cli("next")["recommended"]], ["child"])

    def test_rejected_hypothesis_survives_descendant_evidence(self):
        self.add("theory", kind="hypothesis")
        self.add("trial", parent="theory", kind="experiment")
        self.proof("theory", "contradicts")
        decision = self.decide("theory", "reject")["event"]
        self.proof("trial")
        rows = self.statuses()
        self.assertEqual(rows["theory"]["status"], "rejected")
        self.assertEqual(rows["theory"]["control_decision"]["seq"], decision["seq"])
        self.assertEqual(self.cli("next")["recommended"], [])
        self.decide("trial", ok=False)
        self.revise("trial")
        self.assertEqual(self.statuses()["theory"]["status"], "rejected")
        self.assertEqual(self.cli("next")["recommended"], [])
        self.revise("theory")
        self.assertEqual([r["id"] for r in self.cli("next")["recommended"]], ["trial"])

    def test_child_add_and_replan_never_clear_blocked_ancestor(self):
        self.decide("root", "block")
        self.add("first")
        self.add("second")
        self.assertEqual(self.statuses()["root"]["status"], "blocked")
        self.assertEqual(self.cli("next")["recommended"], [])
        self.cli("replan", "--node", "first", "--replacement", "second", "--reason", "different branch route")
        self.assertEqual(self.statuses()["root"]["status"], "blocked")
        self.assertEqual(self.cli("next")["recommended"], [])
        self.assertTrue(self.cli("validate")["valid"])

    def test_ancestor_revision_does_not_clear_descendant_control(self):
        self.add("child")
        self.decide("child", "block")
        self.revise("root")
        self.assertEqual(self.statuses()["child"]["status"], "blocked")
        self.assertEqual(self.cli("next")["recommended"], [])
        self.revise("child")
        self.assertEqual([r["id"] for r in self.cli("next")["recommended"]], ["child"])

    def test_discovered_dependency_edit_and_clear_are_traced(self):
        self.add("a")
        self.add("b")
        self.proof("b")
        self.decide("b")
        self.cli("revise", "--node", "b", "--outcome", "Deliver b", "--criterion", "b checked",
                 "--depends", "a", "--reason", "discovered actual prerequisite")
        self.assertEqual(self.statuses()["b"]["depends"], ["a"])
        self.proof("b")
        self.decide("b", ok=False)
        self.cli("revise", "--node", "a", "--outcome", "Deliver a", "--criterion", "a checked",
                 "--depends", "b", "--reason", "invalid circular route", ok=False)
        self.cli("revise", "--node", "b", "--outcome", "Deliver b", "--criterion", "b checked",
                 "--clear-depends", "--reason", "direct measurement disproved prerequisite")
        self.assertEqual(self.statuses()["b"]["depends"], [])
        self.proof("b")
        self.decide("b")

    def test_each_criterion_requires_own_support(self):
        state = self.base / "multi.json"
        self.cli("init", "--goal", "two observations", "--criterion", "one", "--criterion", "two", path=state)
        self.cli("evidence", "--node", "root", "--criterion", "one", "--source", "urn:test:one",
                 "--observation", "observed one", "--verdict", "supports", path=state)
        self.cli("decide", "--node", "root", "--action", "complete", "--reason", "only one proved", path=state, ok=False)
        self.cli("evidence", "--node", "root", "--criterion", "two", "--source", "urn:test:two",
                 "--observation", "observed two", "--verdict", "supports", path=state)
        self.cli("decide", "--node", "root", "--action", "complete", "--reason", "both observed", path=state)
        self.assertTrue(self.cli("validate", path=state)["mission_verified"])

    def test_invalid_scores_symlinks_and_bad_arguments_do_not_write(self):
        for value in ("nan", "inf", "-1", "0", "1e-320"):
            self.cli("add", "--id", "bad", "--parent", "root", "--kind", "outcome", "--outcome", "bad",
                     "--criterion", "bad", "--uncertainty", "bad", "--risk", "3", "--cost", value,
                     "--information", "3", ok=False)
        self.cli("decide", "--node", "root", "--action", "complete", ok=False)
        link = self.base / "alias.json"
        link.symlink_to(self.state)
        self.cli("init", "--goal", "clobber", "--criterion", "x", path=link, ok=False)
        directory_link = self.base / "dirlink"
        directory_link.symlink_to(self.base, target_is_directory=True)
        self.cli("init", "--goal", "clobber", "--criterion", "x", path=directory_link / "new.json", ok=False)
        self.assertFalse((self.base / "new.json").exists())

    def test_hash_chain_detects_history_tamper(self):
        document = json.loads(self.state.read_text())
        document["events"][0]["data"]["outcome"] = "easier objective"
        self.state.write_text(json.dumps(document), encoding="utf-8")
        self.cli("validate", ok=False, code=2)

    def test_rehashed_inconsistent_completion_is_invalid(self):
        document = json.loads(self.state.read_text())
        event = {"seq": 2, "at": odrd.utc(), "type": "decide", "previous": document["events"][0]["hash"],
                 "data": {"node": "root", "revision": 1, "action": "complete", "reason": "fabricated success"}}
        event["hash"] = hashlib.sha256(odrd.encoded(event)).hexdigest()
        document["events"].append(event)
        self.state.write_text(json.dumps(document), encoding="utf-8")
        self.cli("validate", ok=False, code=2)

    def test_cooperative_concurrent_writers_do_not_lose_events(self):
        jobs = []
        for key in ("first", "second"):
            jobs.append(subprocess.Popen([sys.executable, str(SCRIPT), "add", str(self.state), "--id", key,
                "--parent", "root", "--kind", "outcome", "--outcome", key, "--criterion", key,
                "--uncertainty", "not checked", "--risk", "2", "--cost", "1", "--information", "3"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
        for job in jobs:
            output, error = job.communicate(timeout=10)
            self.assertEqual(job.returncode, 0, error)
            self.assertEqual(json.loads(output)["recorded"], "add")
        self.assertEqual(set(self.statuses()), {"root", "first", "second"})
        self.assertEqual(self.cli("validate")["events"], 3)
        self.assertFalse(Path(str(self.state) + ".lock").exists())

    def test_multicriterion_integrated_completion_and_retained_hypothesis(self):
        self.add("hypothesis", kind="hypothesis")
        self.add("experiment", parent="hypothesis", kind="experiment")
        self.add("deliverable", kind="deliverable", depends=["hypothesis"])
        self.proof("experiment")
        self.decide("experiment")
        self.proof("hypothesis")
        self.decide("hypothesis", "complete", ok=False)
        self.decide("hypothesis", "retain")
        self.proof("deliverable")
        self.decide("deliverable")
        self.revise("root")
        # Recheck actual artifacts after a mission-wide revision, never reuse old evidence.
        for key, action in [("experiment", "complete"), ("hypothesis", "retain"), ("deliverable", "complete")]:
            self.proof(key)
            self.decide(key, action)
        self.proof("root")
        self.decide("root")
        result = self.cli("validate")
        self.assertTrue(result["valid"] and result["mission_verified"])
        self.assertEqual(self.cli("next")["recommended"], [])
        summary = self.cli("status", "--summary")
        self.assertIn("Mission verified: True", summary.stdout)


if __name__ == "__main__":
    unittest.main()
