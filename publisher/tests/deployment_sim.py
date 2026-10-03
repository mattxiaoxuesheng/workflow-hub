"""Exercise the real deployment shell in an isolated root container with a fake Docker CLI.
Run: docker run --rm --network none --user 0 --entrypoint python -v "$PWD:/work:ro" IMAGE /work/publisher/tests/deployment_sim.py success|failure
"""

import json, os, pathlib, shutil, sqlite3, subprocess, sys, tempfile

scenario = sys.argv[1]
assert scenario in ("success", "failure")
root = pathlib.Path("/opt/wechat-publisher")
data = root / "data"
data.mkdir(parents=True)
(data / "assets").mkdir()
with sqlite3.connect(data / "publisher.db") as c:
    c.executescript(
        "CREATE TABLE article_assets(sha256 TEXT); CREATE TABLE marker(value TEXT); INSERT INTO marker VALUES('original');"
    )
release = pathlib.Path(tempfile.mkdtemp())
repo = pathlib.Path("/work")
for name in ("pull-publisher.sh", "backup.py", "docker-compose.tencent.yml"):
    shutil.copy(repo / "deploy" / name, release / name)
binpath = pathlib.Path(tempfile.mkdtemp())
log = binpath / "commands.jsonl"
mock = binpath / "docker"
mock.write_text("""#!/usr/local/bin/python
import sys,os,json,sqlite3
from pathlib import Path
args=sys.argv[1:]
with open(os.environ['DEPLOY_COMMAND_LOG'],'a') as f: f.write(json.dumps([os.getenv('PUBLISHER_IMAGE'),args])+'\\n')
if args[0]=='ps': print('old-id')
elif args[0]=='inspect': print('healthy' if 'Health' in args[2] else 'sha256:previous')
elif args[0]=='stop': pass
elif args[0]=='compose':
    if 'ps' in args: print('new-id')
    elif 'up' in args and os.environ['PUBLISHER_IMAGE'].startswith('ghcr.io/'):
        with sqlite3.connect('/opt/wechat-publisher/data/publisher.db') as c: c.execute("UPDATE marker SET value='upgraded'")
        if os.environ['DEPLOY_SCENARIO']=='failure': sys.exit(1)
    elif any(x in args for x in ('config','pull','stop','up')): pass
    else: raise RuntimeError(args)
else: raise RuntimeError(args)
""")
mock.chmod(0o755)
env = {
    **os.environ,
    "PATH": str(binpath) + ":" + os.environ["PATH"],
    "DEPLOY_COMMAND_LOG": str(log),
    "DEPLOY_SCENARIO": scenario,
}
image = "ghcr.io/example/publisher@sha256:" + "a" * 64
result = subprocess.run(
    ["bash", str(release / "pull-publisher.sh"), image],
    env=env,
    capture_output=True,
    text=True,
)
print(result.stdout)
print(result.stderr)
with sqlite3.connect(data / "publisher.db") as c:
    value = c.execute("SELECT value FROM marker").fetchone()[0]
commands = [json.loads(line) for line in log.read_text().splitlines()]
pull = next(i for i, x in enumerate(commands) if "pull" in x[1])
stop = next(i for i, x in enumerate(commands) if x[1][0] == "stop")
assert pull < stop
if scenario == "success":
    assert result.returncode == 0, (result.returncode, result.stderr)
    assert value == "upgraded"
    record = json.loads((root / "current-release.json").read_text())
    assert record["image"] == image
    assert pathlib.Path(record["backup"]).exists()
else:
    assert result.returncode != 0
    assert value == "original", value
    assert any(x[0] == "sha256:previous" and "up" in x[1] for x in commands)
print("Real deployment script:", scenario, "PASS")
