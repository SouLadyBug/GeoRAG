"""Run generated analysis code in a restricted child process.

Defence in depth, because the code comes from a language model:

1. **Static check** — the script is parsed and rejected if it imports anything outside a small
   allow-list, calls ``exec``/``eval``/``__import__``, touches dunder attributes, or opens a path
   that is absolute or climbs out of the run folder.
2. **Process limits** — a separate interpreter in isolated mode (``python -I``) with a wall-clock
   timeout, CPU-time, address-space and file-size limits, and an environment that carries no
   secrets.
3. **Audit hooks** — inside the child, a :pep:`578` audit hook blocks process creation, writes
   outside the run folder and name resolution of hosts that are not on the network allow-list.
4. **URL allow-list** — every remote read in :mod:`georag.geo.eo` is checked again before GDAL
   or httpx opens it.

For stronger isolation (no shared kernel namespaces at all) the same runner can be pointed at
``docker run --network=...`` — see ``docker/sandbox.Dockerfile``.
"""

from __future__ import annotations

import ast
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ALLOWED_IMPORTS = {"json", "math", "numpy", "datetime", "georag.geo", "georag.geo.eo", "statistics"}
FORBIDDEN_CALLS = {
    "exec",
    "eval",
    "compile",
    "__import__",
    "globals",
    "locals",
    "vars",
    "breakpoint",
    "input",
    "getattr",
    "setattr",
    "delattr",
}

_BOOTSTRAP = r"""
import fnmatch, os, sys
RUN_DIR = os.path.realpath(os.getcwd())
ALLOWED = [h for h in os.environ.get("GEORAG_ALLOWED_HOSTS", "").split(",") if h]
PROXY_HOSTS = set()
for var in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
    v = os.environ.get(var)
    if v:
        from urllib.parse import urlparse
        h = urlparse(v).hostname
        if h:
            PROXY_HOSTS.add(h)
BLOCKED_EVENTS = ("subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen", "os.kill", "shutil.rmtree", "os.remove", "os.rmdir")

def _host_ok(host):
    if host is None:
        return True
    if isinstance(host, bytes):
        host = host.decode()
    host = str(host)
    if host in PROXY_HOSTS or host in ("localhost",):
        return True
    return any(fnmatch.fnmatch(host, pat) for pat in ALLOWED)

def hook(event, args):
    if event.startswith(BLOCKED_EVENTS):
        raise PermissionError(f"sandbox: {event} is not allowed")
    if event == "open" and args and isinstance(args[0], (str, bytes, os.PathLike)):
        mode = args[1] if len(args) > 1 and isinstance(args[1], str) else "r"
        flags = args[2] if len(args) > 2 and isinstance(args[2], int) else 0
        writing = any(c in mode for c in "wax+") or flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT)
        if writing:
            path = os.path.realpath(os.fsdecode(args[0]))
            if not (path == RUN_DIR or path.startswith(RUN_DIR + os.sep) or path.startswith("/tmp/") or path.startswith("/dev/")):
                raise PermissionError(f"sandbox: write outside the run folder: {path}")
    if event == "socket.getaddrinfo" and args and not _host_ok(args[0]):
        raise PermissionError(f"sandbox: host not on the allow-list: {args[0]}")

sys.addaudithook(hook)
script = sys.argv[1]
sys.argv = sys.argv[1:]
code = compile(open(script).read(), script, "exec")
exec(code, {"__name__": "__main__", "__file__": script})
"""


class StaticCheckError(ValueError):
    pass


def static_check(code: str) -> None:
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in ALLOWED_IMPORTS:
                    raise StaticCheckError(f"import of '{alias.name}' is not allowed")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            full = [f"{mod}.{a.name}" for a in node.names]
            if mod not in ALLOWED_IMPORTS and not all(f in ALLOWED_IMPORTS for f in full):
                raise StaticCheckError(f"import from '{mod}' is not allowed")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in FORBIDDEN_CALLS:
                raise StaticCheckError(f"call to '{node.func.id}' is not allowed")
            if node.func.id == "open" and node.args:
                target = node.args[0]
                if isinstance(target, ast.Constant) and isinstance(target.value, str):
                    if target.value.startswith(("/", "~")) or ".." in target.value:
                        raise StaticCheckError("open() may only use paths inside the run folder")
                elif not isinstance(target, ast.JoinedStr):
                    raise StaticCheckError("open() needs a literal relative path")
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise StaticCheckError(f"access to '{node.attr}' is not allowed")


@dataclass
class SandboxResult:
    ok: bool
    returncode: int
    stdout: str
    stderr: str
    seconds: float
    timed_out: bool = False

    @property
    def error(self) -> str | None:
        if self.ok:
            return None
        if self.timed_out:
            return "timeout"
        lines = [ln for ln in self.stderr.strip().splitlines() if ln.strip()]
        return lines[-1] if lines else f"exit code {self.returncode}"


def _limits(memory_mb: int, cpu_s: int, fsize_mb: int):
    def apply() -> None:
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (memory_mb * 2**20, memory_mb * 2**20))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s + 5))
        resource.setrlimit(resource.RLIMIT_FSIZE, (fsize_mb * 2**20, fsize_mb * 2**20))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        os.setsid()

    return apply


def run_script(
    code: str,
    run_dir: Path,
    timeout_s: int = 300,
    memory_mb: int = 4096,
    allowed_hosts: list[str] | None = None,
    filename: str = "analysis.py",
) -> SandboxResult:
    static_check(code)
    run_dir.mkdir(parents=True, exist_ok=True)
    script = run_dir / filename
    script.write_text(code)
    (run_dir / ".bootstrap.py").write_text(_BOOTSTRAP)

    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(run_dir),
        "LANG": "C.UTF-8",
        "MPLBACKEND": "Agg",
        "MPLCONFIGDIR": str(run_dir / ".mpl"),
        "GEORAG_ALLOWED_HOSTS": ",".join(allowed_hosts or []),
        "OMP_NUM_THREADS": "2",
        "GDAL_NUM_THREADS": "2",
    }
    # Network plumbing only: proxies and CA bundles. Nothing from .env is passed through.
    for var in (
        "HTTPS_PROXY",
        "https_proxy",
        "HTTP_PROXY",
        "http_proxy",
        "NO_PROXY",
        "no_proxy",
        "SSL_CERT_FILE",
        "REQUESTS_CA_BUNDLE",
        "CURL_CA_BUNDLE",
    ):
        if var in os.environ:
            env[var] = os.environ[var]

    t0 = time.perf_counter()
    try:
        proc = subprocess.run(
            [sys.executable, "-I", ".bootstrap.py", filename],
            cwd=run_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            preexec_fn=_limits(memory_mb, timeout_s, 512),
        )
        # SIGXCPU means the CPU-time limit fired before the wall-clock timeout: same outcome.
        cpu_limit = proc.returncode in (-signal.SIGXCPU, -signal.SIGKILL)
        res = SandboxResult(
            proc.returncode == 0,
            proc.returncode,
            proc.stdout[-20000:],
            proc.stderr[-20000:],
            time.perf_counter() - t0,
            timed_out=cpu_limit,
        )
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        err = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        res = SandboxResult(False, -9, out[-20000:], err[-20000:], time.perf_counter() - t0, timed_out=True)
    (run_dir / ".bootstrap.py").unlink(missing_ok=True)
    (run_dir / "stdout.log").write_text(res.stdout)
    (run_dir / "stderr.log").write_text(res.stderr)
    return res
