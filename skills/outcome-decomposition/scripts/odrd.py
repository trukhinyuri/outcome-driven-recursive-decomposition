#!/usr/bin/env python3
"""Local evidence ledger; records and checks work, never executes it.

The JSON is an append-only hash-chained event log, not a security boundary.
Reported observations and remote locators require human/source verification.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from urllib.parse import urlparse

KINDS = {"outcome", "hypothesis", "experiment", "deliverable"}
ACTIONS = {"retain", "reject", "block", "complete"}
VERDICTS = {"supports", "contradicts", "inconclusive"}


class Invalid(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise Invalid(message)


def clean(value, label):
    require(isinstance(value, str) and bool(value.strip()), f"{label} must be nonempty")
    return value.strip()


def texts(values, label):
    result = [clean(v, label) for v in values]
    require(len(result) == len(set(result)), f"duplicate {label}")
    return result


def identifier(value):
    require(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", value), "invalid node ID")
    return value


def score(value, label, ordinal=False):
    require(isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value > 0, f"{label} must be finite and positive")
    if ordinal:
        require(isinstance(value, int) and 1 <= value <= 5, f"{label} must be an integer from 1 to 5")


def utc():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def safe_path(value):
    path = Path(os.path.abspath(os.path.expanduser(str(value))))
    for part in (path, *path.parents):
        require(not part.is_symlink(), f"symlink path refused: {part}")
    require(path.parent.is_dir(), f"parent directory does not exist: {path.parent}")
    if path.exists():
        require(path.is_file(), f"not a regular file: {path}")
    return path


def fingerprint(value):
    path = safe_path(value)
    require(path.is_file(), f"artifact not found: {path}")
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    after = path.stat()
    require((before.st_size, before.st_mtime_ns, before.st_ino) ==
            (after.st_size, after.st_mtime_ns, after.st_ino), "artifact changed during capture")
    return {"path": str(path), "sha256": digest.hexdigest(), "size": after.st_size}


def locator(value, historical=False):
    value = clean(value, "source locator")
    parsed = urlparse(value)
    valid = (parsed.scheme in {"http", "https"} and bool(parsed.netloc)) or (
        parsed.scheme in {"doi", "urn", "file"} and bool(parsed.path))
    if parsed.scheme == "file" and not historical:
        require(parsed.netloc in {"", "localhost"} and Path(parsed.path).is_file(), "local file source is missing")
    require(valid or (Path(value).is_absolute() and (historical or Path(value).is_file())),
            "source must be an HTTP(S), doi:, urn:, file: locator or existing absolute file")
    return value


@contextmanager
def lock(path):
    lockfile = safe_path(str(path) + ".lock")
    deadline = time.monotonic() + 5
    while True:
        try:
            descriptor = os.open(lockfile, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            break
        except FileExistsError:
            require(time.monotonic() < deadline, f"state locked: {lockfile}; inspect owner before removing a stale lock")
            time.sleep(0.05)
    try:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(json.dumps({"pid": os.getpid(), "created_at": utc()}))
        yield
    finally:
        lockfile.unlink()


def save(path, document, new=False):
    safe_path(path)
    descriptor, temporary = tempfile.mkstemp(prefix=".odrd-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        if new:
            os.link(temporary, path)  # Atomic create without clobbering another file.
        else:
            os.replace(temporary, path)
        if hasattr(os, "O_DIRECTORY"):
            try:
                descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
            except OSError:
                pass  # Rename committed; directory fsync is not supported by every FS.
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def current(node):
    return node["revisions"][-1]


def dependencies(node):
    return current(node)["depends"]


class Ledger:
    def __init__(self, document):
        require(isinstance(document, dict) and document.get("schema") == 1, "unsupported state schema")
        self.document = document
        self.nodes, self.evidence, self.decisions, self.resolutions, self.plans = {}, [], [], [], []
        self.controls = {}  # Explicit block/reject survives automatic proof invalidation.
        events = document.get("events")
        require(isinstance(events, list) and bool(events), "empty event log")
        previous = ""
        for index, event in enumerate(events, 1):
            require(isinstance(event, dict) and event.get("seq") == index and event.get("previous") == previous,
                    "broken event sequence")
            body = {key: value for key, value in event.items() if key != "hash"}
            require(event.get("hash") == hashlib.sha256(encoded(body)).hexdigest(), "event hash mismatch")
            stamp = event.get("at", "")
            require(isinstance(stamp, str) and stamp.endswith("Z"), "timestamp must be UTC")
            datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            self.apply(event["type"], event["data"], index, stamp)
            previous = event["hash"]
        self.check_graph()

    def node(self, key):
        require(key in self.nodes, f"unknown node: {key}")
        return self.nodes[key]

    def superseded(self, key):
        return next((p["replacement"] for p in reversed(self.plans) if p["node"] == key), None)

    def gate(self, key):
        while self.superseded(key):
            key = self.superseded(key)
        return key

    def active(self, key):
        node = self.node(key)
        if self.superseded(key):
            return False
        return node["parent"] is None or self.active(node["parent"])

    def decision(self, key):
        if key in self.controls:
            return self.controls[key]
        rev = current(self.node(key))["revision"]
        return next((d for d in reversed(self.decisions) if d["node"] == key and d["revision"] == rev), None)

    def controlled(self, key):
        while key is not None:
            if key in self.controls:
                return True
            key = self.node(key)["parent"]
        return False

    def fresh(self, key):
        rev = current(self.node(key))["revision"]
        return [e for e in self.evidence if e["node"] == key and e["revision"] == rev]

    def artifact_error(self, evidence):
        if "artifact" not in evidence:
            return None
        try:
            require(fingerprint(evidence["artifact"]["path"]) == evidence["artifact"], "artifact content changed")
        except (Invalid, OSError) as error:
            return f"{evidence['id']}: {error}"
        return None

    def resolved(self, evidence, check_artifacts=True):
        for resolution in self.resolutions:
            if resolution["evidence"] == evidence["id"]:
                basis = next(e for e in self.evidence if e["id"] == resolution["basis"])
                if not check_artifacts or not self.artifact_error(basis):
                    return True
        return False

    def proof_reasons(self, key, check_artifacts=True):
        reasons, fresh = [], self.fresh(key)
        for criterion in current(self.node(key))["criteria"]:
            relevant = [e for e in fresh if e["criterion"] == criterion]
            if not any(e["verdict"] == "supports" and (not check_artifacts or not self.artifact_error(e)) for e in relevant):
                reasons.append(f"no fresh supporting evidence: {criterion}")
            for evidence in relevant:
                if evidence["verdict"] == "contradicts" and not self.resolved(evidence, check_artifacts):
                    reasons.append(f"unresolved contradiction: {evidence['id']}")
                error = self.artifact_error(evidence) if check_artifacts else None
                if error:
                    reasons.append(error)
        return reasons

    def closure_reasons(self, key, trail=(), check_artifacts=True):
        require(key not in trail, "completion gate cycle")
        node = self.node(key)
        reasons = self.proof_reasons(key, check_artifacts)
        gates = list(dependencies(node))
        gates += [child["id"] for child in self.nodes.values()
                  if child["parent"] == key and not child["optional"] and self.active(child["id"])]
        for gate in dict.fromkeys(gates):
            if not self.verified(self.gate(gate), trail + (key,), check_artifacts):
                reasons.append(f"unverified prerequisite/required child: {gate}")
        return reasons

    def verified(self, key, trail=(), check_artifacts=True):
        if not self.active(key) or self.controlled(key):
            return False
        decision = self.decision(key)
        if not decision or decision["action"] not in {"complete", "retain"}:
            return False
        latest = max([int(e["id"][1:]) for e in self.fresh(key)] +
                     [r["seq"] for r in self.resolutions if r["node"] == key] + [0])
        if decision["seq"] < latest:
            return False
        return not self.closure_reasons(key, trail, check_artifacts)

    def status(self, key):
        if not self.active(key):
            return "superseded"
        decision = self.decision(key)
        if not decision:
            return "pending"
        if decision["action"] in {"retain", "complete"}:
            return ("retained" if decision["action"] == "retain" else "complete") if self.verified(key) else "stale"
        return {"reject": "rejected", "block": "blocked"}[decision["action"]]

    def affected(self, key, integration_only=False):
        semantic, integration = (set(), {key}) if integration_only else ({key}, set())
        changed = True
        while changed:
            changed = False
            for node in self.nodes.values():
                if node["id"] not in semantic and (node["parent"] in semantic or
                        (semantic | integration).intersection(dependencies(node))):
                    semantic.add(node["id"])
                    changed = True
            for affected in list(semantic | integration):
                parent = self.node(affected)["parent"]
                if parent and parent not in semantic | integration:
                    integration.add(parent)
                    changed = True
        return sorted(semantic | integration)

    def updates(self, keys):
        result = {}
        for key in sorted(keys):
            revision = current(self.node(key))
            result[key] = {k: revision[k] for k in ("outcome", "criteria", "constraints", "depends", "revision")}
            result[key]["revision"] += 1
        return result

    def invalidate(self, updates, expected, stamp, reason):
        require(sorted(updates) == sorted(expected), "affected verification must be invalidated")
        for key, revision in updates.items():
            node = self.node(key)
            require(revision["revision"] == current(node)["revision"] + 1
                    and all(revision[k] == current(node)[k] for k in ("outcome", "criteria", "constraints", "depends")), "invalid verification invalidation")
            node["revisions"].append(dict(revision, at=stamp, reason=reason))

    def check_graph(self):
        require("root" in self.nodes and self.nodes["root"]["parent"] is None, "mission root missing")
        def visit(key, trail):
            require(key not in trail, "dependency/child gate cycle")
            node = self.node(key)
            gates = [self.gate(d) for d in dependencies(node)] + [n["id"] for n in self.nodes.values()
                     if n["parent"] == key and self.active(n["id"])]
            for gate in gates:
                visit(gate, trail + (key,))
        for key, node in self.nodes.items():
            if key != "root":
                self.node(node["parent"])
                require(node["parent"] is not None, "orphan node")
            for dependency in dependencies(node):
                self.node(dependency)
            visit(key, ())

    def apply(self, kind, data, seq, stamp):
        require(isinstance(data, dict), "invalid event data")
        if kind in {"init", "add"}:
            key = identifier(data["id"])
            require(key not in self.nodes, f"duplicate node ID: {key}")
            require(data["kind"] in KINDS, "invalid node kind")
            outcome = clean(data["outcome"], "outcome")
            criteria = texts(data["criteria"], "criterion")
            require(criteria, "at least one criterion required")
            constraints = texts(data["constraints"], "constraint")
            dependencies = texts(data["depends"], "dependency")
            require(type(data["optional"]) is bool, "optional must be boolean")
            clean(data["uncertainty"], "uncertainty")
            score(data["risk"], "risk", True)
            score(data["information"], "information", True)
            score(data["cost"], "cost")
            require(math.isfinite(data["risk"] * data["information"] / data["cost"]), "cost produces a nonfinite priority")
            if kind == "init":
                require(seq == 1 and key == "root" and data["parent"] is None and not dependencies
                        and data["kind"] == "outcome" and not data["optional"], "invalid mission initialization")
                self.original_objective, self.original_criteria = outcome, list(criteria)
                self.original_constraints = list(constraints)
            else:
                require(seq > 1 and key != "root", "invalid add event")
                require(self.active(data["parent"]), "parent is superseded")
                require(not self.decision(data["parent"]) or self.decision(data["parent"])["action"] != "reject",
                        "rejected parent requires a sibling replan")
                for dependency in dependencies:
                    require(self.active(dependency), "dependency is superseded")
                self.invalidate(data["updates"], self.affected(data["parent"], integration_only=True), stamp,
                                f"child added: {key}")
            self.nodes[key] = dict(data, created_at=stamp, revisions=[{
                "revision": 1, "outcome": outcome, "criteria": criteria, "constraints": constraints, "depends": dependencies,
                "at": stamp, "reason": "initial definition"}])
            self.check_graph()
        elif kind == "evidence":
            node = self.node(data["node"])
            require(self.active(data["node"]), "node is superseded")
            require(data["revision"] == current(node)["revision"], "evidence revision mismatch")
            require(data["criterion"] in current(node)["criteria"], "unknown exact criterion")
            require(data["verdict"] in VERDICTS, "invalid evidence verdict")
            clean(data["observation"], "observation")
            # Historical local sources may disappear; syntax/provenance remains recorded.
            locator(data["source"], historical=True)
            require(data["id"] == f"e{seq}", "invalid evidence ID")
            if "artifact" in data:
                artifact = data["artifact"]
                require(isinstance(artifact, dict) and Path(artifact["path"]).is_absolute()
                        and re.fullmatch(r"[0-9a-f]{64}", artifact["sha256"])
                        and type(artifact["size"]) is int and artifact["size"] >= 0, "invalid artifact record")
            self.evidence.append(dict(data, at=stamp))
            self.invalidate(data["updates"], set(self.affected(data["node"], integration_only=True)) - {data["node"]},
                            stamp, f"new evidence: {data['id']}")
        elif kind == "decide":
            node, action = self.node(data["node"]), data["action"]
            require(self.active(data["node"]), "node is superseded")
            require(data["revision"] == current(node)["revision"] and action in ACTIONS, "invalid decision")
            clean(data["reason"], "decision reason")
            require(action != "retain" or node["kind"] == "hypothesis", "retain applies only to hypotheses")
            require(action != "complete" or node["kind"] != "hypothesis", "hypotheses must be retained or rejected")
            if action in {"complete", "retain"}:
                require(not self.controlled(data["node"]), "explicit control requires a revise/replan before completion")
                require(not self.closure_reasons(data["node"], check_artifacts=False), "decision lacks recorded verification")
            decision = dict(data, at=stamp, seq=seq)
            self.decisions.append(decision)
            if action in {"block", "reject"}:
                self.controls[data["node"]] = decision
        elif kind == "resolve":
            contradiction = next((e for e in self.evidence if e["id"] == data["evidence"]), None)
            basis = next((e for e in self.evidence if e["id"] == data["basis"]), None)
            node = self.node(data["node"])
            require(contradiction and basis, "unknown resolution evidence")
            require(self.active(data["node"]), "node is superseded")
            require(contradiction["node"] == basis["node"] == data["node"]
                    and contradiction["revision"] == basis["revision"] == current(node)["revision"]
                    and contradiction["criterion"] == basis["criterion"]
                    and contradiction["verdict"] == "contradicts" and basis["verdict"] == "supports"
                    and int(basis["id"][1:]) > int(contradiction["id"][1:]), "resolution requires later fresh support for the same criterion")
            clean(data["reason"], "resolution reason")
            require(not any(r["evidence"] == data["evidence"] for r in self.resolutions), "evidence already resolved")
            self.resolutions.append(dict(data, at=stamp, seq=seq))
        elif kind == "revise":
            clean(data["reason"], "revision reason")
            require(self.active(data["node"]), "node is superseded")
            require(sorted(data["updates"]) == self.affected(data["node"]), "revision must invalidate affected nodes")
            for key, revision in data["updates"].items():
                node = self.node(key)
                require(revision["revision"] == current(node)["revision"] + 1, "revision sequence mismatch")
                clean(revision["outcome"], "outcome")
                require(texts(revision["criteria"], "criterion"), "criteria required")
                texts(revision["constraints"], "constraint")
                texts(revision["depends"], "dependency")
                for dependency in revision["depends"]:
                    self.node(dependency)
                if key == "root":
                    require(set(self.original_criteria).issubset(revision["criteria"]), "original mission criteria cannot be removed")
                    require(set(self.original_constraints).issubset(revision["constraints"]), "original mission constraints cannot be removed")
                if key != data["node"]:
                    require(all(revision[k] == current(node)[k] for k in ("outcome", "criteria", "constraints", "depends")), "cascade may only invalidate")
                node["revisions"].append(dict(revision, at=stamp, reason=data["reason"]))
            self.controls.pop(data["node"], None)  # Deliberate revision clears only this node's control.
        elif kind == "replan":
            old, replacement = self.node(data["node"]), self.node(data["replacement"])
            require(old["id"] != "root" and old["id"] != replacement["id"]
                    and self.active(old["id"]) and self.active(replacement["id"])
                    and old["parent"] == replacement["parent"], "replacement must be an active sibling of a nonroot node")
            require(old["optional"] or not replacement["optional"], "required work needs a required replacement")
            clean(data["reason"], "replan reason")
            self.invalidate(data["updates"], set(self.affected(old["id"])) - {old["id"]}, stamp, data["reason"])
            self.plans.append(dict(data, at=stamp))
            self.check_graph()
        else:
            raise Invalid(f"unknown event type: {kind}")

    def append(self, kind, data):
        events = self.document["events"]
        event = {"seq": len(events) + 1, "at": utc(), "type": kind, "data": data,
                 "previous": events[-1]["hash"] if events else ""}
        event["hash"] = hashlib.sha256(encoded(event)).hexdigest()
        candidate = {"schema": 1, "events": events + [event]}
        require(len(encoded(candidate)) <= 20_000_000, "state would exceed the 20 MB limit")
        Ledger(candidate)
        return candidate


def load(path):
    require(path.is_file(), f"state not found: {path}")
    require(path.stat().st_size <= 20_000_000, "state exceeds 20 MB; archive externally before extending")
    with path.open(encoding="utf-8") as stream:
        return Ledger(json.load(stream, parse_constant=lambda value: (_ for _ in ()).throw(Invalid(f"invalid number: {value}"))))


def blockers(ledger, key):
    node = ledger.node(key)
    reasons = []
    if not ledger.active(key):
        return ["superseded branch"]
    parent = node["parent"]
    while parent:
        decision = ledger.decision(parent)
        if decision and decision["action"] in {"reject", "block"}:
            reasons.append(f"ancestor {parent} is {decision['action']}; explicit revise/replan required")
        parent = ledger.node(parent)["parent"]
    for dependency in dependencies(node):
        if not ledger.verified(ledger.gate(dependency)):
            reasons.append(f"dependency {dependency} is not verified")
    decision = ledger.decision(key)
    if decision and decision["action"] in {"reject", "block"}:
        reasons.append(f"node is {decision['action']}; explicit revise/replan required")
    return reasons


def report(ledger, command):
    rows = []
    for key in sorted(ledger.nodes):
        node = ledger.node(key)
        status = ledger.status(key)
        row = {"id": key, "kind": node["kind"], "status": status, "revision": current(node)["revision"],
               "control_decision": ledger.controls.get(key),
               "optional": node["optional"], "outcome": current(node)["outcome"], "depends": dependencies(node),
               "parent": node["parent"], "criteria": current(node)["criteria"], "constraints": current(node)["constraints"],
               "uncertainty": node["uncertainty"], "risk": node["risk"], "information": node["information"], "cost": node["cost"],
               "blocked_by": blockers(ledger, key), "verification_gaps": ledger.closure_reasons(key) if ledger.active(key) else []}
        heuristic = node["risk"] * node["information"] / node["cost"]
        row["priority"] = heuristic
        row["priority_reason"] = f"ordinal heuristic: risk({node['risk']}) * information({node['information']}) / cost({node['cost']}); not true VOI"
        rows.append(row)
    errors = [error for e in ledger.evidence if (error := ledger.artifact_error(e))]
    result = {"original_objective": ledger.original_objective, "mission_verified": ledger.verified("root"),
              "events": len(ledger.document["events"]), "nodes": rows, "artifact_errors": errors}
    if command == "next":
        eligible = [r for r in rows if not r["blocked_by"] and r["status"] not in {"complete", "retained", "superseded"}]
        # Work on children before closing their parent; parent own proof still matters.
        actionable = [r for r in eligible if not any(ledger.active(n["id"]) and not n["optional"]
                       and n["parent"] == r["id"] and not ledger.verified(n["id"]) for n in ledger.nodes.values())]
        result["recommended"] = sorted(actionable, key=lambda r: (-r["priority"], r["id"]))
        result["blocked"] = [r for r in rows if r["blocked_by"] and r["status"] != "superseded"]
    return result


def parser():
    cli = argparse.ArgumentParser(description=__doc__)
    sub = cli.add_subparsers(dest="command", required=True)
    for command in ("init", "add", "evidence", "decide", "resolve", "revise", "replan", "status", "next", "validate"):
        p = sub.add_parser(command)
        p.add_argument("state")
        p.add_argument("--summary", action="store_true", help="human-readable output; default is JSON")
        if command == "init":
            p.add_argument("--goal", required=True)
        if command in {"init", "add", "revise"}:
            p.add_argument("--criterion", action="append", required=True)
            p.add_argument("--constraint", action="append", default=[])
        if command == "add":
            p.add_argument("--id", required=True)
            p.add_argument("--parent", required=True)
            p.add_argument("--kind", choices=sorted(KINDS), required=True)
            p.add_argument("--depends", action="append", default=[])
            p.add_argument("--optional", action="store_true")
            p.add_argument("--uncertainty", required=True)
            p.add_argument("--risk", type=int, required=True)
            p.add_argument("--cost", type=float, required=True)
            p.add_argument("--information", type=int, required=True)
        if command in {"add", "revise"}:
            p.add_argument("--outcome", required=True)
        if command == "revise":
            group = p.add_mutually_exclusive_group()
            group.add_argument("--depends", action="append", help="replace prerequisite list; omit to preserve")
            group.add_argument("--clear-depends", action="store_true")
        if command in {"evidence", "decide", "resolve", "revise", "replan"}:
            p.add_argument("--node", required=True)
        if command == "evidence":
            p.add_argument("--criterion", required=True)
            p.add_argument("--source", required=True)
            p.add_argument("--observation", required=True)
            p.add_argument("--verdict", choices=sorted(VERDICTS), required=True)
            p.add_argument("--artifact")
        if command in {"decide", "resolve", "revise", "replan"}:
            p.add_argument("--reason", required=True)
        if command == "decide":
            p.add_argument("--action", choices=sorted(ACTIONS), required=True)
        if command == "resolve":
            p.add_argument("--evidence", required=True)
            p.add_argument("--basis", required=True)
        if command == "replan":
            p.add_argument("--replacement", required=True)
    return cli


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        path = safe_path(args.state)
        if args.command in {"status", "next", "validate"}:
            ledger = load(path)
            result = report(ledger, args.command)
            result["valid"] = not result["artifact_errors"]
            code = 1 if args.command == "validate" and not result["valid"] else 0
        else:
            with lock(path):
                if args.command == "init":
                    require(not path.exists(), "state already exists; init never overwrites")
                    data = {"id": "root", "parent": None, "kind": "outcome", "outcome": args.goal,
                            "criteria": args.criterion, "constraints": args.constraint, "depends": [],
                            "optional": False, "uncertainty": "mission acceptance", "risk": 1, "cost": 1, "information": 1}
                    event = {"seq": 1, "at": utc(), "type": "init", "data": data, "previous": ""}
                    event["hash"] = hashlib.sha256(encoded(event)).hexdigest()
                    candidate = {"schema": 1, "events": [event]}
                else:
                    ledger = load(path)
                    data = {"node": args.node} if hasattr(args, "node") else {}
                    if args.command == "add":
                        data = {"id": args.id, "parent": args.parent, "kind": args.kind, "outcome": args.outcome,
                                "criteria": args.criterion, "constraints": args.constraint, "depends": args.depends,
                                "optional": args.optional, "uncertainty": args.uncertainty, "risk": args.risk,
                                "cost": args.cost, "information": args.information}
                        data["updates"] = ledger.updates(ledger.affected(args.parent, integration_only=True))
                    elif args.command == "evidence":
                        data.update(id=f"e{len(ledger.document['events']) + 1}", revision=current(ledger.node(args.node))["revision"],
                                    criterion=args.criterion, source=locator(args.source), observation=args.observation, verdict=args.verdict)
                        data["updates"] = ledger.updates(set(ledger.affected(args.node, integration_only=True)) - {args.node})
                        if args.artifact:
                            data["artifact"] = fingerprint(args.artifact)
                    elif args.command == "decide":
                        node = ledger.node(args.node)
                        if args.action in {"complete", "retain"}:
                            require(not blockers(ledger, args.node), "; ".join(blockers(ledger, args.node)))
                            reasons = ledger.closure_reasons(args.node)
                            require(not reasons, "; ".join(reasons))
                        if args.action == "reject" and node["kind"] == "hypothesis":
                            require(any(e["verdict"] == "contradicts" and not ledger.artifact_error(e)
                                        for e in ledger.fresh(args.node)), "hypothesis rejection requires fresh contrary evidence")
                        data.update(action=args.action, reason=args.reason, revision=current(node)["revision"])
                    elif args.command == "resolve":
                        data.update(evidence=args.evidence, basis=args.basis, reason=args.reason)
                        basis = next((e for e in ledger.evidence if e["id"] == args.basis), None)
                        require(basis and not ledger.artifact_error(basis), "resolution basis missing or artifact invalid")
                    elif args.command == "replan":
                        updates = ledger.updates(set(ledger.affected(args.node)) - {args.node})
                        data.update(replacement=args.replacement, reason=args.reason, updates=updates)
                    elif args.command == "revise":
                        updates = ledger.updates(ledger.affected(args.node))
                        updates[args.node].update(outcome=args.outcome, criteria=args.criterion,
                                                  constraints=args.constraint or current(ledger.node(args.node))["constraints"])
                        if args.depends is not None or args.clear_depends:
                            updates[args.node]["depends"] = args.depends or []
                            for dependency in updates[args.node]["depends"]:
                                require(ledger.active(dependency), "new dependency is superseded")
                        data.update(updates=updates, reason=args.reason)
                    candidate = ledger.append(args.command, data)
                ledger = Ledger(candidate)
                save(path, candidate, new=args.command == "init")
                result = {"recorded": args.command, "event": candidate["events"][-1], "mission_verified": ledger.verified("root")}
                code = 0
        if args.summary:
            print(f"Mission verified: {result['mission_verified']}")
            for row in result.get("recommended", result.get("nodes", [])):
                print(f"{row['id']}: {row['status']} — {row['outcome']}")
                if row["blocked_by"]:
                    print("  " + "; ".join(row["blocked_by"]))
            if args.command == "next":
                for row in result.get("blocked", []):
                    print(f"{row['id']}: " + "; ".join(row["blocked_by"]))
            for error in result.get("artifact_errors", []):
                print(error)
            if "event" in result:
                print(f"Recorded {result['recorded']} event {result['event']['seq']}")
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return code
    except (Invalid, OSError, KeyError, TypeError, ValueError, RecursionError) as error:
        print(f"odrd: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
