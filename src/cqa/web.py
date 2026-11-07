"""Loopback-only MVP: existing engine API plus the independent human viewer.

Run from the source checkout: PYTHONPATH=src python3 -m cqa.web
No scoring, rubric or provider behavior is reimplemented here.
"""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import re
import threading
from urllib.parse import unquote, urlsplit

from pydantic import ValidationError

from .engine import CheckBlocked, EvaluationRejected, evaluate
from .io import load_checklist, parse_json
from .loader import ROOT, SHARED, load_conversation, read_dataset, require_approved_synthetic
from .providers import MockProvider, OpenAIProvider, ProviderError
from .schemas import Contract, EvaluationConfig
from typing import Literal, Optional


class EvaluationRequest(Contract):
    conversation_id: str
    provider: Literal["mock", "openai"] = "mock"
    model: Optional[str] = None


def load_env_file(path):
    """Read only two supported settings. No shell expansion or secret logging."""
    values = {}
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or key not in ("OPENAI_API_KEY", "CQA_MODEL"):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if value:
            values[key] = value
    return values


class Application:
    def __init__(self, *, checklist=None, model=None, allow_external=False,
                 api_key=None, provider_factory=None, output_dir=None, config=None, live_call_limit=None):
        self.checklist = checklist or load_checklist()
        self.model = model or os.environ.get("CQA_MODEL", "")
        self.api_key = os.environ.get("OPENAI_API_KEY", "") if api_key is None else api_key
        self.allow_external = allow_external
        self.evaluation_config = config or EvaluationConfig(quote_policy="normalize_formatting")
        self.live_call_limit = live_call_limit
        self.live_calls = 0
        self.provider_factory = provider_factory or self._provider
        self.output_dir = Path(output_dir) if output_dir else ROOT / "outputs/app"
        if (ROOT / "outputs").resolve() not in self.output_dir.resolve().parents:
            raise ValueError("Application output must remain under ignored outputs/")
        self.lock = threading.Lock()
        data, _ = read_dataset(SHARED)
        self.records = data["records"]
        # Fail startup if the shared source was replaced with unreviewed material.
        require_approved_synthetic(load_conversation(SHARED, self.records[0]["conversation_id"]), True)
        self.ids = {r["conversation_id"] for r in self.records}

    def _provider(self, name, model):
        return MockProvider() if name == "mock" else OpenAIProvider(model, api_key=self.api_key)

    def config(self):
        return {"default_provider": "mock", "model": self.model,
                "openai_key_present": bool(self.api_key.strip()),
                "external_synthetic_allowed": self.allow_external,
                "live_calls_remaining": None if self.live_call_limit is None else max(0, self.live_call_limit - self.live_calls),
                "checklist": self.checklist.model_dump(mode="json")}

    def conversation(self, conversation_id):
        if conversation_id not in self.ids:
            raise LookupError("Conversation not found in synthetic DEV")
        return load_conversation(SHARED, conversation_id)

    def run(self, request):
        conversation = self.conversation(request.conversation_id)
        model = request.model or self.model
        if request.provider == "openai":
            if not self.allow_external:
                raise ValueError("External evaluation disabled. Restart with --allow-external-synthetic.")
            if not self.api_key.strip():
                raise ValueError("OPENAI_API_KEY is not configured; no request sent.")
            if not model or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}", model):
                raise ValueError("Choose an explicit supported OpenAI model.")
        if not self.lock.acquire(blocking=False):
            raise BlockingIOError("An evaluation is running; wait before submitting another.")
        try:
            if request.provider == "openai":
                if self.live_call_limit is not None and self.live_calls >= self.live_call_limit:
                    raise ValueError("Live call limit reached; no request sent.")
                self.live_calls += 1  # Reserve before transport; failed calls are never automatically retried.
            result = evaluate(conversation, self.checklist, self.provider_factory(request.provider, model),
                              self.evaluation_config.model_copy(update={"external_synthetic_allowed": self.allow_external}))
            self.output_dir.mkdir(parents=True, exist_ok=True)
            with (self.output_dir / (result.evaluation_id + ".json")).open("x", encoding="utf-8") as handle:
                handle.write(result.model_dump_json(indent=2) + "\n")
            return result
        except EvaluationRejected as error:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            target = self.output_dir / ("rejected-" + error.diagnostic["diagnostic_id"] + ".json")
            with target.open("x", encoding="utf-8") as handle:
                json.dump(error.diagnostic, handle, ensure_ascii=False, indent=2)
            raise
        finally:
            self.lock.release()


def build_human_viewer():
    path = ROOT / "tools/dev_review/build.py"
    spec = importlib.util.spec_from_file_location("cqa_independent_viewer_build", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    target = ROOT / "outputs/dev_review/index.html"
    module.build(target)
    return target


def create_server(port=8765, application=None):
    app = application or Application()
    human_page = build_human_viewer()
    assets = {"/": (ROOT / "web/index.html", "text/html; charset=utf-8"),
              "/app.js": (ROOT / "web/app.js", "text/javascript; charset=utf-8"),
              "/app.css": (ROOT / "web/app.css", "text/css; charset=utf-8"),
              "/transcript.js": (ROOT / "tools/dev_review/transcript.js", "text/javascript; charset=utf-8"),
              "/human-review/": (human_page, "text/html; charset=utf-8")}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass  # Do not log request bodies, conversation IDs or private errors.

        def send_body(self, status, body, content_type="application/json; charset=utf-8"):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            # The offline viewer has its own stricter inline-script CSP.
            if urlsplit(self.path).path != "/human-review/":
                self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; "
                                 "style-src 'self'; connect-src 'self'; base-uri 'none'; "
                                 "frame-ancestors 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(body)

        def reply(self, status, value):
            self.send_body(status, json.dumps(value, ensure_ascii=False).encode("utf-8"))

        def valid_host(self):
            return self.headers.get("Host") in {f"127.0.0.1:{self.server.server_port}",
                                                f"localhost:{self.server.server_port}"}

        def do_GET(self):
            if not self.valid_host():
                return self.reply(403, {"error": "Local host required"})
            path = urlsplit(self.path).path
            try:
                if path in assets:
                    target, mime = assets[path]
                    return self.send_body(200, target.read_bytes(), mime)
                if path == "/api/config":
                    return self.reply(200, app.config())
                if path == "/api/conversations":
                    return self.reply(200, [{k: r[k] for k in ("conversation_id", "channel", "language")}
                                            for r in app.records])
                if path.startswith("/api/diagnostics/"):
                    identifier = path[len("/api/diagnostics/"):]
                    if not re.fullmatch(r"[0-9a-f-]{36}", identifier):
                        return self.reply(404, {"error": "Diagnostic not found"})
                    target = app.output_dir / ("rejected-" + identifier + ".json")
                    if not target.is_file():
                        return self.reply(404, {"error": "Diagnostic not found"})
                    diagnostic = parse_json(target.read_bytes())
                    if diagnostic.get("conversation", {}).get("conversation_id") not in app.ids:
                        return self.reply(404, {"error": "Diagnostic outside synthetic DEV"})
                    return self.reply(200, diagnostic)
                if path.startswith("/api/conversations/"):
                    conversation = app.conversation(unquote(path[len("/api/conversations/"):]))
                    return self.reply(200, conversation.model_dump(mode="json"))
                return self.reply(404, {"error": "Not found"})
            except LookupError:
                return self.reply(404, {"error": "Conversation not found in synthetic DEV"})
            except Exception:
                return self.reply(500, {"error": "Local input unavailable or invalid; inspect configuration"})

        def do_POST(self):
            if not self.valid_host() or self.headers.get("Origin") != "http://" + self.headers.get("Host", ""):
                return self.reply(403, {"error": "Same-origin local request required"})
            if self.path != "/api/evaluations":
                return self.reply(404, {"error": "Not found"})
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                return self.reply(415, {"error": "JSON required"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 4096:
                    return self.reply(413, {"error": "Invalid request size"})
                request = EvaluationRequest.model_validate(parse_json(self.rfile.read(length)))
                result = app.run(request)
                return self.reply(200, result.model_dump(mode="json"))
            except LookupError:
                return self.reply(404, {"error": "Conversation not found in synthetic DEV"})
            except BlockingIOError:
                return self.reply(409, {"error": "An evaluation is already running"})
            except ValidationError:
                return self.reply(422, {"error": "Request or model output failed schema validation; no score returned"})
            except CheckBlocked:
                return self.reply(422, {"error": "Evaluation blocked by a quality check; no score returned"})
            except EvaluationRejected as error:
                return self.reply(422, {"error": str(error), "diagnostic_id": error.diagnostic["diagnostic_id"],
                                        "issues": error.diagnostic["issues"]})
            except ProviderError as error:
                return self.reply(502, {"error": str(error)})
            except ValueError as error:
                return self.reply(422, {"error": str(error)})
            except Exception:
                return self.reply(500, {"error": "Evaluation failed; private details withheld"})

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--model", help="Explicit OpenAI model; also configurable in the browser")
    parser.add_argument("--checklist", type=Path)
    parser.add_argument("--env-file", type=Path, help="Ignored local env file; never served or logged")
    parser.add_argument("--allow-external-synthetic", action="store_true")
    parser.add_argument("--max-output-tokens", type=int, default=8000)
    parser.add_argument("--timeout-seconds", type=int, default=90)
    parser.add_argument("--live-call-limit", type=int, help="Optional hard per-process cap, including failed attempts")
    args = parser.parse_args(argv)
    try:
        settings = load_env_file(args.env_file) if args.env_file else {}
        app = Application(checklist=load_checklist(args.checklist), model=args.model or settings.get("CQA_MODEL"),
                          api_key=settings.get("OPENAI_API_KEY"), allow_external=args.allow_external_synthetic,
                          config=EvaluationConfig(quote_policy="normalize_formatting", max_output_tokens=args.max_output_tokens,
                                                  timeout_seconds=args.timeout_seconds), live_call_limit=args.live_call_limit)
        server = create_server(args.port, app)
    except (OSError, ValueError):
        print("Cannot start local app: check port, dataset, checklist and local configuration.")
        return 1
    print(f"CQA local app: http://127.0.0.1:{server.server_port}/", flush=True)
    print("Default mode: MOCK fixture. Human labels stay separate at /human-review/.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
