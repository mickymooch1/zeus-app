"""get_anthropic_client() returns AsyncAnthropic — every .messages.create() on it
must be awaited.

This bug has now shipped three separate times:

  eee5753     music_search
  2026-08-02  songs_generate — whose fix comment notes the "identical bug was fixed
              in music_search ... but missed here"
  2026-08-23  parse_scheduled_task — missed by both of the above

It is unusually hard to spot in review and in production. Forgetting the await is
valid Python: `create(...)` returns a coroutine, and the AttributeError only fires
later, at `.content[0]`. In parse_scheduled_task that raise landed inside a
try/except that converts anything into a 400 "Could not parse schedule — try
again", so a total server-side failure was reported to users as their own phrasing
being unparseable, and the endpoint never once succeeded.

Two greps would each miss it — the call site and the failure site are different
lines, often different blocks — so this walks the AST instead. A fourth instance
should fail here rather than in front of a user.
"""
import ast
import pathlib

BACKEND = pathlib.Path(__file__).parent.parent

# Modules whose Anthropic client is the ASYNC one.
_ASYNC_CLIENT_FACTORY = "get_anthropic_client"


def _is_async_client_create(call: ast.Call, local_async_names: set) -> bool:
    """Is this `<async client>.messages.create(...)`?"""
    fn = call.func
    if not (isinstance(fn, ast.Attribute) and fn.attr == "create"):
        return False
    messages = fn.value
    if not (isinstance(messages, ast.Attribute) and messages.attr == "messages"):
        return False
    root = messages.value
    if isinstance(root, ast.Call) and isinstance(root.func, ast.Name):
        return root.func.id == _ASYNC_CLIENT_FACTORY      # get_anthropic_client().messages.create
    if isinstance(root, ast.Name):
        return root.id in local_async_names                # c = get_anthropic_client(); c.messages...
    return False


def _scan_scope(scope, awaited: set) -> list:
    """Un-awaited async-client create() calls directly inside one function scope.

    Everything is scoped PER FUNCTION. A file-wide name set produced a false positive
    on the first run: main.py binds `client = get_anthropic_client()` in the telegram
    webhook and `client = Anthropic()` — the SYNCHRONOUS client, where no await is
    correct — in ai_generate_playlist. File-wide tracking flags the second because of
    the first, and a guard that cries wolf gets deleted rather than heeded.
    """
    local: set = set()
    for node in ast.walk(scope):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            fn = node.value.func
            if isinstance(fn, ast.Name) and fn.id == _ASYNC_CLIENT_FACTORY:
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        local.add(t.id)

    out = []
    for node in ast.walk(scope):
        if isinstance(node, ast.Call) and id(node) not in awaited:
            if _is_async_client_create(node, local):
                out.append(node.lineno)
    return out


def _async_create_calls_missing_await(path: pathlib.Path) -> list[str]:
    """Return 'file:line' for every un-awaited get_anthropic_client() create call."""
    tree = ast.parse(path.read_text(encoding="utf-8"))

    awaited: set = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Await) and isinstance(node.value, ast.Call):
            awaited.add(id(node.value))

    lines: set = set()
    for scope in ast.walk(tree):
        if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
            lines.update(_scan_scope(scope, awaited))
    return [f"{path.name}:{n}" for n in sorted(lines)]


def test_every_async_anthropic_create_is_awaited():
    offenders: list[str] = []
    for path in sorted(BACKEND.glob("*.py")):
        offenders += _async_create_calls_missing_await(path)

    assert not offenders, (
        "get_anthropic_client() is AsyncAnthropic; these .messages.create() calls are "
        "not awaited, so .content will raise AttributeError on a coroutine at runtime: "
        + ", ".join(offenders)
    )


def test_the_detector_actually_detects():
    """A guard that cannot fail is not a guard. This is the exact shape of the bug."""
    src = (
        "async def f():\n"
        "    msg = get_anthropic_client().messages.create(model='m')\n"
        "    return msg.content[0].text\n"
    )
    tmp = BACKEND / "tests" / "_await_probe.py"
    tmp.write_text(src, encoding="utf-8")
    try:
        assert _async_create_calls_missing_await(tmp), "detector missed an un-awaited call"
    finally:
        tmp.unlink()


def test_the_detector_accepts_the_correct_form():
    src = (
        "async def f():\n"
        "    msg = await get_anthropic_client().messages.create(model='m')\n"
        "    return msg.content[0].text\n"
    )
    tmp = BACKEND / "tests" / "_await_probe_ok.py"
    tmp.write_text(src, encoding="utf-8")
    try:
        assert not _async_create_calls_missing_await(tmp), "detector flagged a correct call"
    finally:
        tmp.unlink()


def test_the_detector_catches_the_via_variable_form():
    """`client = get_anthropic_client()` then `client.messages.create(...)` — the
    shape parse_scheduled_task actually had."""
    src = (
        "async def f():\n"
        "    client = get_anthropic_client()\n"
        "    msg = client.messages.create(model='m')\n"
        "    return msg.content[0].text\n"
    )
    tmp = BACKEND / "tests" / "_await_probe_var.py"
    tmp.write_text(src, encoding="utf-8")
    try:
        assert _async_create_calls_missing_await(tmp), "detector missed the variable form"
    finally:
        tmp.unlink()
