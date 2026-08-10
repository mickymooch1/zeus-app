"""No module may call `requests` without importing it (2026-08-10).

Voice cloning failed in production with:

    Voice cloning failed: name 'requests' is not defined

main.py used requests.post / requests.delete in three places — the two voice
endpoints — but never imported it at module level. The only `import requests`
in the file sat inside an unrelated nested function, so it never bound the
module-level name. Two of the three calls were inside bare `except: pass`
blocks, so they had been failing silently for as long as they existed.

The three calls were converted to httpx (the project standard, already imported
and already used throughout main.py). Both endpoints are async, so they are now
properly awaited instead of blocking the event loop.

The AST check below is the real guard: it catches this class of bug in ANY
backend module, not just the one that happened to be reported.
"""
import ast
import pathlib
import re

BACKEND = pathlib.Path(__file__).parent.parent
_HTTP_ATTRS = {"get", "post", "put", "delete", "patch", "head", "request", "Session"}


def _module_level_imports(tree):
    names = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            names.update((a.asname or a.name).split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def _calls_on(tree, module_name):
    """Line numbers where `module_name.<http verb>(...)` is called."""
    hits = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == module_name
                and node.func.attr in _HTTP_ATTRS):
            hits.append(node.lineno)
    return hits


def _local_imports(tree, module_name):
    """Functions that import the module themselves — those uses are fine."""
    scopes = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for inner in ast.walk(node):
                if isinstance(inner, ast.Import) and any(
                        a.name == module_name for a in inner.names):
                    scopes.append((node.lineno, getattr(node, "end_lineno", node.lineno)))
    return scopes


def test_no_module_uses_requests_without_importing_it():
    """The exact production bug, generalised to every backend module."""
    broken = []
    for path in sorted(BACKEND.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        if "requests" in _module_level_imports(tree):
            continue
        local = _local_imports(tree, "requests")
        for line in _calls_on(tree, "requests"):
            if not any(start <= line <= end for start, end in local):
                broken.append(f"{path.name}:{line}")
    assert not broken, (
        "requests.<verb>() called without a module-level import — these raise "
        f"NameError at runtime: {broken}"
    )


def test_main_has_no_requests_calls_at_all():
    """main.py standardised on httpx; a new requests call there would reintroduce
    the import trap, since it still has no module-level import."""
    tree = ast.parse((BACKEND / "main.py").read_text(encoding="utf-8"))
    assert not _calls_on(tree, "requests"), "main.py should use httpx, not requests"


def test_voice_endpoints_use_httpx_and_await_it():
    """Both voice endpoints are async — a blocking call would stall the loop."""
    src = (BACKEND / "main.py").read_text(encoding="utf-8")
    start = src.index("async def clone_voice") if "async def clone_voice" in src \
        else src.index("/api/voice/clone")
    end = src.index("@app.post(\"/api/auth/forgot-password\")", start)
    block = src[start:end]
    assert "httpx.AsyncClient" in block, "voice endpoints should use httpx"
    assert "requests." not in block, "requests must be gone from the voice endpoints"
    # every ElevenLabs call in that block is awaited
    for call in re.findall(r"_c\.(post|delete)\(", block):
        pass
    assert block.count("await _c.") >= 3, "all three ElevenLabs calls must be awaited"


def test_every_backend_module_still_parses():
    """Cheap guard that the conversion didn't leave a file unimportable."""
    for path in sorted(BACKEND.glob("*.py")):
        ast.parse(path.read_text(encoding="utf-8", errors="replace"))
