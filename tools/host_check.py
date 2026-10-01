#!/usr/bin/env python3
"""Read-only plugin/skill discovery through the host's generated JSON-RPC API.

No threads or model turns are created. Only this plugin's metadata is reported.
"""
import argparse
import datetime
import json
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time

PLUGIN = "outcome-driven-recursive-decomposition"
SKILL = "outcome-decomposition"


class RPC:
    def __init__(self, command, timeout):
        self.timeout = timeout
        self.messages = queue.Queue()
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                        text=True, bufsize=1)
        self.counter = 0
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.process.stdout:
            try:
                self.messages.put(json.loads(line))
            except json.JSONDecodeError:
                continue
        self.messages.put(None)

    def send(self, method, params=None, ident=None):
        message = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        if ident is not None:
            message["id"] = ident
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()

    def request(self, method, params):
        self.counter += 1
        ident = self.counter
        self.send(method, params, ident)
        deadline = time.monotonic() + self.timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Timed out waiting for " + method)
            try:
                reply = self.messages.get(timeout=remaining)
            except queue.Empty:
                raise TimeoutError("Timed out waiting for " + method) from None
            if reply is None:
                raise RuntimeError("Host exited while waiting for " + method)
            if reply.get("id") != ident:
                continue
            if "error" in reply:
                raise RuntimeError(method + ": " + json.dumps(reply["error"]))
            return reply.get("result", {})

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)


def check(args):
    command = [args.codex, "app-server"]
    rpc = RPC(command, args.timeout)
    try:
        host = rpc.request("initialize", {"clientInfo": {"name": "odrd_host_check",
                           "version": "1.0.0"}, "capabilities": {"experimentalApi": True}})
        rpc.send("initialized")
        entries = rpc.request("skills/list", {"cwds": [str(Path(args.cwd).resolve())],
                                                "forceReload": True})
        skills = [s for entry in entries.get("data", []) for s in entry.get("skills", [])
                  if s.get("name") == SKILL or s.get("name", "").endswith(":" + SKILL)]
        catalog = rpc.request("plugin/list", {"cwds": [str(Path(args.cwd).resolve())],
                                              "marketplaceKinds": ["local"], "forceRefetch": False})
        plugins = [p for m in catalog.get("marketplaces", []) for p in m.get("plugins", [])
                   if p.get("name") == PLUGIN]
        result = {"observedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  "transport": "stdio", "host": host,
                  "plugins": [{k: p.get(k) for k in ("id", "name", "enabled", "installed",
                                "version", "localVersion")} for p in plugins],
                  "skills": [{k: s.get(k) for k in ("name", "enabled", "path", "pluginId",
                                                    "scope", "interface")} for s in skills]}
        result["ok"] = bool(any(p.get("installed") and p.get("enabled") for p in plugins)
                            and any(s.get("enabled") for s in skills))
        result["proves"] = "Installed/enabled plugin and discoverable skill; not model activation or task quality."
        if args.models:
            models = rpc.request("model/list", {"limit": 100, "includeHidden": False})
            result["models"] = [{k: m.get(k) for k in ("model", "supportedReasoningEfforts",
                              "defaultReasoningEffort")} for m in models.get("data", [])
                              if m.get("model") in ("gpt-6.1-sol", "gpt-6-astra", "gpt-6-luna")]
        return result
    finally:
        rpc.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", default=".")
    parser.add_argument("--codex", default="codex")
    parser.add_argument("--timeout", type=float, default=40)
    parser.add_argument("--models", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = check(args)
        if args.output:
            args.output.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
        return 0 if result["ok"] else 1
    except (OSError, RuntimeError, TimeoutError, queue.Empty) as error:
        print(json.dumps({"ok": False, "error": str(error)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
