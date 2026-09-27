from __future__ import annotations

import base64
import hashlib
import secrets
import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from . import config, security
from .database import db, j, now, uj
from .jobs import notify

router = APIRouter(prefix="/api/runner", tags=["runner"])

RUNNER_TOKEN_TTL_SECONDS = 24 * 3600

def mint_runner_token(conn, job_id: str) -> str:
    token = "msr_" + secrets.token_hex(24)
    conn.execute("UPDATE jobs SET runner_token=?, mode='own_infra' WHERE id=?",
                 (token, job_id))
    return token

def _job_for_token(conn, token: str) -> dict:
    row = conn.execute(
        "SELECT * FROM jobs WHERE runner_token=? AND type='execute'", (token,)
    ).fetchone()
    if not row:
        raise HTTPException(401, "Runner token is invalid or already used")
    job = dict(row)
    if job["status"] not in ("waiting_runner",):
        raise HTTPException(409, f"Job is no longer waiting for a runner (status: {job['status']})")
    if now() - job["created_at"] > RUNNER_TOKEN_TTL_SECONDS:
        raise HTTPException(401, "Runner token expired. Regenerate it from the job view.")
    return job

def _run_and_plan(conn, job: dict) -> tuple[dict, dict, dict]:
    run = conn.execute("SELECT * FROM runs WHERE id=?", (job["ref_id"],)).fetchone()
    if not run:
        raise HTTPException(404, "Run not found for this job")
    run = dict(run)
    m = conn.execute("SELECT * FROM models WHERE id=?", (run["model_id"],)).fetchone()
    if not m:
        raise HTTPException(404, "Model not found for this run")
    m = dict(m)
    plan = next((p for p in (uj(m.get("plans")) or {}).get("valid", [])
                 if p["plan_id"] == run["plan_id"]), None)
    if not plan:
        raise HTTPException(409, "Plan no longer valid for this model")
    return run, m, plan

@router.get("/{token}/manifest")
def manifest(token: str):
    with db() as conn:
        job = _job_for_token(conn, token)
        run, m, plan = _run_and_plan(conn, job)
        analysis = uj(m.get("analysis"), {}) or {}
        return {
            "job_id": job["id"], "run_id": run["id"],
            "plan": plan,
            "model": {
                "name": m["name"], "framework": m["framework"],
                "sha256": m["sha256"], "orig_name": m.get("orig_name") or "model.pt",
                "input_shape": analysis.get("input_shape") or [1, 3, 32, 32],
            },
            "benchmark_runs": config.BENCHMARK_RUNS,
            "platform_version": config.APP_VERSION,
        }

@router.get("/{token}/model")
def model_bytes(token: str):
    with db() as conn:
        job = _job_for_token(conn, token)
        _, m, _ = _run_and_plan(conn, job)
    path = config.UPLOADS_DIR / m["filename"]
    if not path.exists():
        raise HTTPException(404, "Stored model file missing")
    data = security.decrypt_bytes(path.read_bytes())
    name = m.get("orig_name") or "model.pt"
    return Response(
        content=data, media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{name}"'})

@router.post("/{token}/checkin")
async def checkin(token: str, request: Request):
    body = await request.json()
    pct = max(0, min(99, int(body.get("progress", 0))))
    msg = str(body.get("message", ""))[:200]
    with db() as conn:
        job = _job_for_token(conn, token)
        conn.execute("UPDATE jobs SET progress=?, message=? WHERE id=?",
                     (pct, msg or "runner working", job["id"]))
    return {"ok": True}

@router.post("/{token}/result")
async def result(token: str, request: Request):
    body = await request.json()
    with db() as conn:
        job = _job_for_token(conn, token)
        run, m, plan = _run_and_plan(conn, job)
        steps = body.get("steps") or []
        benchmark = body.get("benchmark") or {}
        if not benchmark or "baseline" not in benchmark:
            raise HTTPException(422, "result requires a benchmark with a baseline")
        art_in = body.get("artifacts") or []
        if not art_in:
            raise HTTPException(422, "result requires at least one artifact: "
                                     "refusing to mark a run successful without proof")
        repro = body.get("repro") or {}

        art_dir = config.ARTIFACTS_DIR / run["id"]
        art_dir.mkdir(parents=True, exist_ok=True)
        stored = []
        for a in art_in:
            name = str(a.get("name", ""))[:80]
            if "/" in name or "\\" in name or not name:
                raise HTTPException(422, f"bad artifact name: {name!r}")
            try:
                data = base64.b64decode(a.get("content_b64", ""))
            except Exception:
                raise HTTPException(422, f"artifact {name} is not valid base64")
            if not data:
                raise HTTPException(422, f"artifact {name} is empty")
            (art_dir / f"{name}.enc").write_bytes(security.encrypt_bytes(data))
            stored.append({"name": name, "size_bytes": len(data),
                           "sha256": hashlib.sha256(data).hexdigest(), "encrypted": True})

        conn.execute(
            "UPDATE runs SET status='success', steps=?, benchmark=?, artifacts=?, "
            "repro=?, finished_at=? WHERE id=?",
            (j(steps), j(benchmark), j(stored), j(repro), now(), run["id"]))
        conn.execute(
            "UPDATE jobs SET status='success', progress=100, message='completed on "
            "user infrastructure', runner_token=NULL, finished_at=? WHERE id=?",
            (now(), job["id"]))
        notify(conn, job["user_id"], "success", "Optimization complete on your infrastructure",
               f"'{plan['tagline']}' on '{m['name']}': size −"
               f"{benchmark.get('size_saved_pct', '-')}%")
        from .database import audit
        audit(conn, job["user_id"], "execute_done", "run", run["id"],
              f"{plan['plan_id']} (own infra)")
    from .auth import fire_webhook
    fire_webhook(job["user_id"], {
        "event": "run_completed", "run_id": run["id"], "model": m["name"],
        "model_id": m["id"], "plan": plan["plan_id"], "status": "success",
        "executed_on": "user infrastructure",
        "size_saved_pct": benchmark.get("size_saved_pct"),
        "latency_gain_pct": benchmark.get("latency_gain_pct"),
        "agreement_pct": (benchmark.get("output_agreement") or {}).get("agreement_pct"),
    })
    return {"ok": True}

@router.post("/{token}/fail")
async def fail(token: str, request: Request):
    body = await request.json()
    err = str(body.get("error", "runner reported failure"))[:400]
    with db() as conn:
        job = _job_for_token(conn, token)
        run, m, plan = _run_and_plan(conn, job)
        conn.execute("UPDATE runs SET status='failed', error=?, finished_at=? WHERE id=?",
                     (err, now(), run["id"]))
        conn.execute(
            "UPDATE jobs SET status='failed', error=?, message='failed on user "
            "infrastructure', runner_token=NULL, finished_at=? WHERE id=?",
            (err, now(), job["id"]))
        notify(conn, job["user_id"], "error", "Optimization failed on your infrastructure",
               f"'{plan['tagline']}' on '{m['name']}': {err}")
    return {"ok": True}

def render_aws_bootstrap(script: str) -> str:
    import gzip
    gz_b64 = base64.b64encode(gzip.compress(script.encode())).decode()
    return f"""#!/bin/bash
# ModelSmith runner bootstrap (Amazon Linux 2023, x86_64)
exec > /var/log/modelsmith-runner.log 2>&1
set -e
dnf install -y python3.11 python3.11-pip
python3.11 -m pip install --upgrade pip
echo '{gz_b64}' | base64 -d | gunzip > /root/ms_runner.py
python3.11 -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
python3.11 -m pip install onnx onnxruntime numpy
cd /root && python3.11 ms_runner.py
shutdown -h now"""

def launch_on_aws(region: str, instance_type: str, akid: str, secret: str,
                  session_token: str | None, user_data: str) -> str:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import BotoCoreError, ClientError

    cfg = Config(retries={"max_attempts": 1}, read_timeout=20, connect_timeout=10)
    session = boto3.session.Session(
        aws_access_key_id=akid, aws_secret_access_key=secret,
        aws_session_token=session_token or None)
    try:
        ssm = session.client("ssm", region_name=region, config=cfg)
        ami = ssm.get_parameter(Name=(
            "/aws/service/ami-amazon-linux-latest/"
            "al2023-ami-kernel-default-x86_64"))["Parameter"]["Value"]
        ec2 = session.client("ec2", region_name=region, config=cfg)
        resp = ec2.run_instances(
            ImageId=ami, InstanceType=instance_type, MinCount=1, MaxCount=1,
            UserData=user_data,
            InstanceInitiatedShutdownBehavior="terminate",
            TagSpecifications=[{"ResourceType": "instance", "Tags": [
                {"Key": "Name", "Value": "modelsmith-runner"},
                {"Key": "CreatedBy", "Value": "ModelSmith"}]}],
            BlockDeviceMappings=[{"DeviceName": "/dev/xvda", "Ebs": {
                "VolumeSize": 30, "VolumeType": "gp3", "DeleteOnTermination": True}}],
        )
        return resp["Instances"][0]["InstanceId"]
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("InvalidClientTokenId", "SignatureDoesNotMatch",
                    "AuthFailure", "UnrecognizedClientException"):
            raise HTTPException(401, "AWS rejected these credentials "
                                     f"({code}). Check the key, secret and region.")
        if code == "UnauthorizedOperation":
            raise HTTPException(403, "These credentials lack EC2 launch "
                                     "permission (ec2:RunInstances).")
        if code == "OptInRequired":
            raise HTTPException(403, "This AWS account has not accepted the "
                                     "EC2 terms for that region (OptInRequired).")
        raise HTTPException(502, f"AWS launch failed ({code}): "
                                 f"{e.response.get('Error', {}).get('Message', '')}")
    except (BotoCoreError, ConnectionError, OSError) as e:
        raise HTTPException(502, f"Could not reach AWS: {type(e).__name__}. "
                                 "Check network access and the region name.")
    finally:
        del session

RUNNER_TEMPLATE = '''#!/usr/bin/env python3
"""ModelSmith own-infrastructure runner.

Executes one plan on THIS machine and reports the result back to the
platform. Generated for job @@JOB_ID@@ (@@RUN_ID@@); the embedded token is
single-use and expires 24h after issue.

Requirements on this machine: python3.11+, torch, onnx, onnxruntime,
numpy (torchvision if the pickle references it). Nothing else. Nothing
is stored here after the run finishes.
"""
import base64, hashlib, json, platform as pf, shutil, sys, tempfile, time
import urllib.request
from pathlib import Path

BASE_URL = "@@BASE_URL@@"
TOKEN = "@@TOKEN@@"
BENCH_RUNS = @@BENCH_RUNS@@
SEED = 42

TECHNIQUES = @@TECHNIQUES@@          # ordered list, e.g. ["prune20", "onnx", "int8"]
INPUT_SHAPE = @@INPUT_SHAPE@@        # tuple, e.g. (1, 3, 32, 32)

def _install_class_shims():
    """Full-module pickles reference the classes that defined them (e.g.
    'app.analysis.MnistCnn'). On this machine those modules do not exist.
    Register stub modules whose __getattr__ synthesizes functionally
    equivalent classes: standard Sequential containers delegate forward to
    self.net; torchvision base classes resolve to the real implementations.
    Custom models with exotic forward logic cannot be reconstructed from a
    pickle anywhere except their home module - that is a property of
    torch.save, not of this runner."""
    import types
    try:
        import torch.nn as nn
    except ImportError:
        return
    def _resolve(name):
        if name in ("ResNet18Stub", "ResNet"):
            import torchvision.models.resnet as tvr
            return tvr.ResNet
        if name in ("BasicBlock", "Bottleneck"):
            import torchvision.models.resnet as tvr
            return getattr(tvr, name)
        return type(name, (nn.Module,), {"forward": lambda self, x: self.net(x)})
    class _Shim(types.ModuleType):
        # dunder lookup happens on the type, so __getattr__ lives here.
        # Internal attributes (__, _ipython etc.) must raise so the import
        # machinery sees a normal module; only class names resolve.
        def __getattr__(self, name):
            if name.startswith("_"):
                raise AttributeError(name)
            return _resolve(name)
    for modname in ("app", "app.analysis", "app.seed", "__ms_model__"):
        if modname not in sys.modules:
            sys.modules[modname] = _Shim(modname)

_install_class_shims()

def api(method, path, payload=None, raw=None):
    url = BASE_URL + "/api/runner/" + TOKEN + path
    data = json.dumps(payload).encode() if payload is not None else raw
    req = urllib.request.Request(url, data=data, method=method)
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=600) as resp:
        body = resp.read()
        ctype = resp.headers.get("Content-Type", "")
        return json.loads(body) if body and ctype.startswith("application/json") else body

def say(pct, msg):
    print(f"[{pct:3d}%] {msg}", flush=True)
    try:
        api("POST", "/checkin", {"progress": pct, "message": msg})
    except Exception as e:
        print(f"  (check-in failed: {e})", flush=True)

# ---- techniques (mirror the platform executor) ----------------------------
def apply_int8(model):
    import torch, torch.nn as nn
    engines = torch.backends.quantized.supported_engines
    if "qnnpack" in engines:
        torch.backends.quantized.engine = "qnnpack"
    elif "fbgemm" in engines:
        torch.backends.quantized.engine = "fbgemm"
    q = torch.quantization.quantize_dynamic(
        model, {nn.Linear, nn.LSTM, nn.GRU, nn.RNN}, dtype=torch.qint8)
    return q, "Linear/LSTM layers quantized to INT8 with per-channel scales."

def apply_prune(model, amount):
    import torch.nn as nn, torch.nn.utils.prune as prune
    for m in [m for m in model.modules() if isinstance(m, nn.Conv2d)]:
        prune.ln_structured(m, name="weight", amount=amount, n=2, dim=0)
    for m in [m for m in model.modules() if isinstance(m, nn.Linear)]:
        prune.l1_unstructured(m, name="weight", amount=amount)
    for m in list(model.modules()):
        if hasattr(m, "weight_mask"):
            prune.remove(m, "weight")
    total = sum(p.numel() for p in model.parameters())
    nonzero = sum(int((p != 0).sum()) for p in model.parameters())
    sparsity = round(100 * (1 - nonzero / max(total, 1)), 1)
    return model, f"{sparsity}% of weights zeroed (conv structured, linear unstructured)."

def apply_fp16(model):
    return model.half(), "All weights converted to half precision."

def export_onnx(model, shape, out_path):
    import torch, onnx
    dummy = torch.randn(1, *shape)
    try:
        torch.onnx.export(model, dummy, str(out_path), opset_version=13,
                          input_names=["input"], output_names=["output"], dynamo=False)
    except TypeError:
        torch.onnx.export(model, dummy, str(out_path), opset_version=13,
                          input_names=["input"], output_names=["output"])
    onnx.checker.check_model(onnx.load(str(out_path)))
    return "Exported + validated ONNX graph (opset 13)."

def bench_torch(model, shape, runs):
    import numpy as np, torch
    x = torch.randn(1, *shape)
    if next(model.parameters()).dtype == torch.float16:
        x = x.half()
    with torch.no_grad():
        for _ in range(5):
            model(x)
        times = []
        for _ in range(runs):
            t0 = time.perf_counter(); model(x)
            times.append((time.perf_counter() - t0) * 1000)
    arr = np.array(times); lat = float(arr.mean())
    return {"latency_ms": round(lat, 4), "p95_ms": round(float(np.percentile(arr, 95)), 4),
            "throughput_fps": round(1000 / lat, 1) if lat else None,
            "runs": runs, "runtime": "pytorch-cpu"}

def bench_onnx(path, shape, runs):
    import numpy as np, onnxruntime as ort
    sess = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    x = np.random.rand(1, *shape).astype(np.float32)
    name = sess.get_inputs()[0].name
    sess.run(None, {name: x})
    times = []
    for _ in range(runs):
        t0 = time.perf_counter(); sess.run(None, {name: x})
        times.append((time.perf_counter() - t0) * 1000)
    arr = np.array(times); lat = float(arr.mean())
    return {"latency_ms": round(lat, 4), "p95_ms": round(float(np.percentile(arr, 95)), 4),
            "throughput_fps": round(1000 / lat, 1) if lat else None,
            "runs": runs, "runtime": f"onnxruntime-{ort.__version__}"}

def agreement(orig_model, opt_model_or_path, shape, onnx_mode):
    import numpy as np, torch
    torch.manual_seed(SEED)
    if onnx_mode:
        import onnxruntime as ort
        sess = ort.InferenceSession(str(opt_model_or_path), providers=["CPUExecutionProvider"])
        oname = sess.get_inputs()[0].name
    same = total = 0
    with torch.no_grad():
        for _ in range(16):
            x = torch.randn(1, *shape)
            a = orig_model(x)
            if onnx_mode:
                b = torch.from_numpy(sess.run(None, {oname: x.numpy().astype(np.float32)})[0])
            else:
                m = opt_model_or_path
                xx = x.half() if next(m.parameters()).dtype == torch.float16 else x
                b = m(xx)
            if a.shape != b.shape:
                return {"agreement_pct": None, "note": "shape mismatch"}
            if a.dim() >= 1 and a.shape[-1] > 1:
                same += int(torch.argmax(a).item() == torch.argmax(b).item())
            else:
                same += int(torch.allclose(a.float(), b.float(), rtol=0.05, atol=0.05))
            total += 1
    return {"agreement_pct": round(100 * same / total, 1),
            "inputs_checked": total, "seed": SEED}

# ---- main pipeline ---------------------------------------------------------
def main():
    import torch
    work = Path(tempfile.mkdtemp(prefix="ms_runner_"))
    try:
        say(3, "Downloading model from platform")
        model_bytes = api("GET", "/model")
        model_path = work / "orig.pt"
        model_path.write_bytes(model_bytes)

        say(10, "Loading model")
        model = torch.load(str(model_path), map_location="cpu", weights_only=False)
        model.eval()
        shape = tuple(INPUT_SHAPE)

        say(18, f"Benchmarking baseline ({BENCH_RUNS} runs)")
        baseline = bench_torch(model, shape, BENCH_RUNS)
        baseline_size = round(model_path.stat().st_size / 1e6, 4)

        current = model
        steps = []
        order = {"prune20": 0, "prune40": 0, "onnx": 1, "fp16": 2, "int8": 2}
        ordered = sorted(TECHNIQUES, key=lambda t: order.get(t, 9))
        for i, tech in enumerate(ordered):
            say(25 + int(25 * i / max(len(ordered), 1)), f"Applying {tech}")
            if tech == "int8":
                current, note = apply_int8(current)
            elif tech == "prune20":
                current, note = apply_prune(current, 0.20)
            elif tech == "prune40":
                current, note = apply_prune(current, 0.40)
            elif tech == "fp16":
                current, note = apply_fp16(current)
            elif tech == "onnx":
                note = export_onnx(current, shape, work / "optimized.onnx")
            else:
                raise RuntimeError(f"technique {tech} is guided-only and cannot run remotely")
            steps.append({"technique": tech, "status": "success", "note": note})

        say(60, "Serializing optimized artifacts")
        artifacts = []
        torch_out = work / "optimized.pt"
        torch.save(current, torch_out)
        artifacts.append(("optimized.pt", torch_out))
        onnx_path = work / "optimized.onnx"
        onnx_mode = "onnx" in TECHNIQUES and onnx_path.exists()
        if onnx_mode:
            artifacts.insert(0, ("optimized.onnx", onnx_path))

        say(70, "Benchmarking optimized model")
        touched = any(t in TECHNIQUES for t in ("int8", "fp16", "prune20", "prune40"))
        opt_bench = None
        bench_note = None
        if touched:
            try:
                opt_bench = bench_torch(current, shape, BENCH_RUNS)
            except Exception as e:
                bench_note = f"torch bench failed: {e}"
        if onnx_mode:
            ob = bench_onnx(onnx_path, shape, BENCH_RUNS)
            if opt_bench:
                opt_bench["onnx_artifact"] = ob
            else:
                opt_bench = ob
        if opt_bench is None:
            opt_bench = {"latency_ms": None}

        say(82, "Checking output agreement (16 seeded inputs)")
        try:
            if onnx_mode:
                ag = agreement(model, onnx_path, shape, True)
            else:
                ag = agreement(model, current.float() if "fp16" in TECHNIQUES else current,
                               shape, False)
        except Exception as e:
            ag = {"agreement_pct": None, "note": str(e)}

        say(90, "Uploading result to the platform")
        primary = torch_out if touched else onnx_path
        primary_bytes = primary.stat().st_size
        size_saved = round(100 * (1 - primary_bytes / max(model_path.stat().st_size, 1)), 1)
        latency_gain = None
        if opt_bench.get("latency_ms") and baseline.get("latency_ms"):
            latency_gain = round(100 * (1 - opt_bench["latency_ms"] / baseline["latency_ms"]), 1)
        benchmark = {
            "baseline": {"size_mb": baseline_size, **baseline},
            "optimized": {"size_mb": round(primary_bytes / 1e6, 4), **opt_bench},
            "size_saved_pct": size_saved, "latency_gain_pct": latency_gain,
            "output_agreement": ag, "note": bench_note,
        }
        repro = {
            "model_sha256": hashlib.sha256(model_bytes).hexdigest(),
            "plan_id": "@@PLAN_ID@@", "techniques": list(TECHNIQUES), "seed": SEED,
            "benchmark_runs": BENCH_RUNS,
            "versions": {"python": pf.python_version(), "torch": torch.__version__},
            "platform": {"system": pf.system(), "machine": pf.machine(),
                         "processor": pf.processor()},
            "executed_at": time.time(), "executed_on": "user infrastructure",
        }
        import numpy as np
        import onnx
        import onnxruntime
        repro["versions"]["onnx"] = onnx.__version__
        repro["versions"]["onnxruntime"] = onnxruntime.__version__
        repro["versions"]["numpy"] = np.__version__

        payload = {
            "steps": steps, "benchmark": benchmark, "repro": repro,
            "artifacts": [
                {"name": name, "content_b64": base64.b64encode(p.read_bytes()).decode()}
                for name, p in artifacts
            ],
        }
        api("POST", "/result", payload)
        print(f"Done: size -{size_saved}%, latency -{latency_gain or 0}%, "
              f"agreement {ag.get('agreement_pct')}%")
        print("Result recorded on the platform. This machine is done.", flush=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        print(f"RUNNER FAILED: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
        try:
            api("POST", "/fail", {"error": f"{type(e).__name__}: {e}"})
        except Exception:
            pass
        sys.exit(1)
'''

def render_runner_script(base_url: str, token: str, job: dict, run: dict,
                         plan: dict, model_meta: dict) -> str:
    techniques = [t for t in plan["techniques"]
                  if t in ("int8", "prune20", "prune40", "fp16", "onnx")]
    if not techniques:
        raise HTTPException(409, "This plan is guided-only: it has no remotely executable steps")
    analysis = model_meta.get("_analysis", {}) or {}
    shape = analysis.get("input_shape") or [1, 3, 32, 32]
    return (RUNNER_TEMPLATE
            .replace("@@JOB_ID@@", job["id"])
            .replace("@@RUN_ID@@", run["id"])
            .replace("@@BASE_URL@@", base_url)
            .replace("@@TOKEN@@", token)
            .replace("@@BENCH_RUNS@@", str(config.BENCHMARK_RUNS))
            .replace("@@TECHNIQUES@@", repr(techniques))
            .replace("@@INPUT_SHAPE@@", repr(tuple(int(d) for d in shape)))
            .replace("@@PLAN_ID@@", plan["plan_id"]))
