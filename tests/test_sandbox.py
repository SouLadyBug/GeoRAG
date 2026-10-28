import pytest

from georag.sandbox import StaticCheckError, run_script, static_check


@pytest.mark.parametrize(
    "code",
    [
        "import os",
        "import subprocess",
        "from os import system",
        "__import__('os')",
        "eval('1+1')",
        "open('/etc/passwd')",
        "open('../x', 'w')",
        "x = ().__class__",
        "import socket",
    ],
)
def test_static_check_rejects(code):
    with pytest.raises(StaticCheckError):
        static_check(code)


def test_static_check_accepts_template_style_code():
    static_check(
        "import json\nimport numpy as np\nfrom georag.geo import eo\njson.dump({}, open('result.json', 'w'))"
    )


def test_runs_and_writes_inside_run_dir(tmp_path):
    res = run_script("import json\njson.dump({'ok': 1}, open('result.json', 'w'))\nprint('done')", tmp_path)
    assert res.ok, res.stderr
    assert (tmp_path / "result.json").exists()
    assert "done" in res.stdout


def test_timeout(tmp_path):
    res = run_script("while True:\n    pass", tmp_path, timeout_s=2)
    assert not res.ok and res.timed_out


def test_runtime_blocks_escape_attempts(tmp_path):
    # Indirect access that the static check cannot see is stopped by the audit hook.
    code = "import json\nm = json.__spec__\n"
    with pytest.raises(StaticCheckError):
        static_check(code)
    res = run_script("import numpy as np\nnp.save('/tmp/../root/x.npy', np.zeros(2))", tmp_path)
    assert not res.ok and "outside the run folder" in res.stderr


def test_memory_limit(tmp_path):
    res = run_script(
        "import numpy as np\nx = np.ones((40000, 40000))\nprint(x.sum())", tmp_path, memory_mb=1024
    )
    assert not res.ok
    assert "MemoryError" in res.stderr or "Unable to allocate" in res.stderr


def test_network_allow_list(tmp_path):
    code = "from georag.geo import eo\neo.check_url('https://example.com/data.tif')"
    res = run_script(code, tmp_path, allowed_hosts=["sentinel-cogs.s3.us-west-2.amazonaws.com"])
    assert not res.ok and "allow-list" in res.stderr
