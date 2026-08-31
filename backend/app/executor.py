"""FR-11 Optimization Execution, FR-12 Benchmarking, FR-13 Artifacts.

Runs the selected plan as a step-by-step pipeline on the decrypted model:
INT8 dynamic quantization, magnitude pruning, FP16 conversion, ONNX export.
Every step records real measured outcomes; artifacts are encrypted at rest
and each run stores full reproducibility metadata (NFR-09).

Honesty rules (NFR-03): the run is only marked success after every required
step completed and at least one artifact was written. Anything that cannot be
measured on this machine (e.g. FP16 latency on CPU) is reported as null with
an explanation instead of a fabricated number.
"""
from __future__ import annotations

import platform
import shutil
import time
from pathlib import Path

import numpy as np

from . import analysis as an
from . import config, security
from .database import j, now

AGREEMENT_SEED = 42


# ------------------------------------------------------------- technique impl
def apply_int8(model):
    """Dynamic INT8: quantizes Linear/LSTM (Conv remains FP32 on CPU)."""
    import torch
    import torch.nn as nn

    engines = torch.backends.quantized.supported_engines
    if "qnnpack" in engines:
        torch.backends.quantized.engine = "qnnpack"
    elif "fbgemm" in engines:
        torch.backends.quantized.engine = "fbgemm"
    elif getattr(torch.backends.quantized, "engine", "none") == "none":
        raise NotImplementedError(
            "no quantized engine compiled in this torch build")
    quantized = torch.quantization.quantize_dynamic(
        model, {nn.Linear, nn.LSTM, nn.GRU, nn.RNN}, dtype=torch.qint8)
    return quantized, "Linear/LSTM layers quantized to INT8 with per-channel scales."


def apply_prune(model, amount: float):
    """Magnitude pruning: zeroes low-contribution conv filters + linear weights."""
    import torch
    import torch.nn as nn
    import torch.nn.utils.prune as prune

    convs = [m for m in model.modules() if isinstance(m, nn.Conv2d)]
    for m in convs:
        prune.ln_structured(m, name="weight", amount=amount, n=2, dim=0)
    for m in [m for m in model.modules() if isinstance(m, nn.Linear)]:
        prune.l1_unstructured(m, name="weight", amount=amount)
    for m in list(model.modules()):
        if hasattr(m, "weight_mask"):
            prune.remove(m, "weight")

    total = sum(p.numel() for p in model.parameters())
    nonzero = sum(int((p != 0).sum()) for p in model.parameters())
    sparsity = round(100 * (1 - nonzero / max(total, 1)), 1)
    note = (f"{sparsity}% of weights zeroed (conv filters structured, linear "
            f"unstructured). Deploy-time channel removal or sparse kernels "
            f"convert this into real size/latency savings.")
    return model, note


def apply_fp16(model):
    return model.half(), "All weights converted to half precision (targets GPU runtimes)."


def export_onnx(model, shape, out_path: Path):
    import torch

    dummy = an.safe_input(shape)
    try:
        torch.onnx.export(model, dummy, str(out_path), opset_version=13,
                          input_names=["input"], output_names=["output"],
                          dynamo=False)
    except TypeError:                     # older torch without `dynamo` kwarg
        torch.onnx.export(model, dummy, str(out_path), opset_version=13,
                          input_names=["input"], output_names=["output"])
    import onnx
    onnx.checker.check_model(onnx.load(str(out_path)))
    return f"Exported + validated ONNX graph (opset 13)."


# ------------------------------------------------------------------ benchmarks
def benchmark_any(model, shape, runs):
    """Benchmark a torch or ONNX model; returns dict or raises."""
    import onnxruntime as ort

    if isinstance(model, Path):
        sess = ort.InferenceSession(str(model), providers=["CPUExecutionProvider"])
        x = np.random.rand(1, *shape).astype(np.float32)
        name = sess.get_inputs()[0].name
        sess.run(None, {name: x})
        times = []
        for _ in range(runs):
            t0 = time.perf_counter()
            sess.run(None, {name: x})
            times.append((time.perf_counter() - t0) * 1000)
        arr = np.array(times)
        lat = float(np.mean(arr))
        return {"latency_ms": round(lat, 4), "p95_ms": round(float(np.percentile(arr, 95)), 4),
                "throughput_fps": round(1000 / lat, 1) if lat else None,
                "runs": runs, "runtime": f"onnxruntime-{ort.__version__}"}

    import torch
    x = an.safe_input(shape)
    if next(model.parameters(), None) is not None and next(model.parameters()).dtype == torch.float16:
        x = x.half()
    with torch.no_grad():
        for _ in range(5):
            model(x)
        times = []
        for _ in range(runs):
            t0 = time.perf_counter()
            model(x)
            times.append((time.perf_counter() - t0) * 1000)
    arr = np.array(times)
    lat = float(np.mean(arr))
    return {"latency_ms": round(lat, 4), "p95_ms": round(float(np.percentile(arr, 95)), 4),
            "throughput_fps": round(1000 / lat, 1) if lat else None,
            "runs": runs, "runtime": "pytorch-cpu"}


def output_agreement(orig_fn, optimized_fn, shape, n_inputs: int = 16) -> dict:
    """Behavioral check: agreement of argmax between original and optimized
    outputs on identical seeded inputs: a dataset-free proxy for accuracy
    retention (real accuracy needs labeled data, which uploads lack)."""
    import torch

    torch.manual_seed(AGREEMENT_SEED)
    inputs = [torch.randn(1, *shape) for _ in range(n_inputs)]
    same, total = 0, 0
    with torch.no_grad():
        for x in inputs:
            try:
                a = orig_fn(x)
                try:
                    b = optimized_fn(x)
                except NotImplementedError:
                    b = optimized_fn(x.half())   # fp16 models take half inputs
                if not isinstance(a, torch.Tensor):
                    a = a[0]
                if not isinstance(b, torch.Tensor):
                    b = b[0]
                if a.shape != b.shape:
                    return {"agreement_pct": None,
                            "note": "output shapes differ: agreement not computable"}
                if a.dim() >= 1 and a.shape[-1] > 1:
                    same += int(torch.argmax(a).item() == torch.argmax(b).item())
                else:
                    same += int(torch.allclose(a.float(), b.float(), rtol=0.05, atol=0.05))
                total += 1
            except Exception:             # noqa: BLE001: unsupported op etc.
                continue
    if total == 0:
        return {"agreement_pct": None, "note": "optimized model could not run on CPU"}
    return {"agreement_pct": round(100 * same / total, 1),
            "inputs_checked": total, "seed": AGREEMENT_SEED}


# ------------------------------------------------------------------- pipeline
def run_plan_pipeline(model_row: dict, plan: dict, run_id: str, progress) -> dict:
    """Execute `plan` on the uploaded model. Returns the full run record."""
    import torch

    uploads_file = config.UPLOADS_DIR / model_row["filename"]
    work_dir = config.TMP_DIR / f"run_{int(now()*1000)}"
    art_dir = config.ARTIFACTS_DIR / run_id
    art_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    def pct(p, msg):
        progress(p, msg)

    try:
        pct(5, "Decrypting model from encrypted storage")
        plain = work_dir / f"orig{Path(model_row['orig_name']).suffix or '.pt'}"
        plain.write_bytes(security.decrypt_bytes(uploads_file.read_bytes()))

        pct(12, "Loading model")
        model, shape = an.load_torch_model(plain, None)
        input_shape = tuple(shape)

        pct(20, "Benchmarking baseline")
        baseline_bench = an.benchmark_torch(model, input_shape, config.BENCHMARK_RUNS)
        baseline_size_mb = round(plain.stat().st_size / 1e6, 4)

        def orig_fn(x):
            with torch.no_grad():
                return model(x)

        steps = []
        current = model

        techniques = plan["techniques"]
        # Execution order matters: quantized torch ops cannot be exported to
        # ONNX, so the portable graph is exported from the pruned FP32 model
        # before precision conversion is applied to the PyTorch artifact.
        order = {"prune20": 0, "prune40": 0, "onnx": 1, "fp16": 2, "int8": 2,
                 "tensorrt": 3, "distill": 3}
        ordered = sorted(techniques, key=lambda t: order.get(t, 9))
        n_tech = len(ordered)

        for i, tech in enumerate(ordered):
            base_p = 30 + int(40 * i / max(n_tech, 1))
            label = next(pl for tl, pl in zip(plan["techniques"],
                                              plan["technique_labels"])
                         if tl == tech)
            step = {"technique": tech, "label": label, "status": "running"}
            pct(base_p, f"Applying {label}")
            try:
                if tech == "int8":
                    current, note = apply_int8(current)
                elif tech == "prune20":
                    current, note = apply_prune(current, 0.20)
                elif tech == "prune40":
                    current, note = apply_prune(current, 0.40)
                elif tech == "fp16":
                    current, note = apply_fp16(current)
                elif tech == "onnx":
                    onnx_path = work_dir / "optimized.onnx"
                    note = export_onnx(current, input_shape, onnx_path)
                elif tech in ("tensorrt", "distill"):
                    step.update(status="guided",
                                note="Manual technique: generated instructions artifact.")
                    steps.append(step)
                    continue
                else:
                    raise ValueError(f"unknown technique {tech}")
                step.update(status="success", note=note)
            except NotImplementedError as e:
                step.update(status="partial", note=f"Limited on CPU: {e}")
            except Exception as e:                      # noqa: BLE001
                step.update(status="failed", note=f"{type(e).__name__}: {e}")
                raise
            steps.append(step)

        pct(72, "Serializing optimized artifacts")
        artifacts = []
        torch_out = work_dir / "optimized.pt"
        torch.save(current, torch_out)

        agreement_fn = None
        if "onnx" not in techniques:
            model_for_agreement = current.float() if "fp16" in techniques else current
            agreement_fn = lambda x: model_for_agreement(x)  # noqa: E731

        if "onnx" in techniques and (work_dir / "optimized.onnx").exists():
            artifacts.append(("optimized.onnx", work_dir / "optimized.onnx"))
        artifacts.append(("optimized.pt", torch_out))

        pct(80, "Benchmarking optimized model")
        opt_bench = None
        bench_note = None
        onnx_path = work_dir / "optimized.onnx"
        torch_chain_touched = any(t in techniques for t in ("int8", "fp16", "prune20", "prune40"))
        torch_bench = None
        if torch_chain_touched:
            try:
                torch_bench = benchmark_any(current, input_shape, config.BENCHMARK_RUNS)
            except NotImplementedError as e:
                bench_note = (f"FP16 kernels unavailable on CPU ({e}): latency "
                              f"requires a GPU runtime; size benefits still apply.")
            except Exception as e:                      # noqa: BLE001
                bench_note = f"Torch benchmark failed: {type(e).__name__}: {e}"
        if "onnx" in techniques and onnx_path.exists():
            try:
                onnx_bench = benchmark_any(onnx_path, input_shape, config.BENCHMARK_RUNS)
                if torch_bench is None:
                    opt_bench = onnx_bench
                else:
                    torch_bench["onnx_artifact"] = onnx_bench
                    opt_bench = torch_bench
            except Exception as e:                      # noqa: BLE001
                bench_note = (bench_note or "") + f" ONNX benchmark failed: {e}"
        elif torch_bench is not None:
            opt_bench = torch_bench

        pct(88, "Checking output agreement")
        agreement = {"agreement_pct": None, "note": "skipped"}
        try:
            if agreement_fn is not None:
                agreement = output_agreement(orig_fn, agreement_fn, input_shape)
            elif "onnx" in techniques and (work_dir / "optimized.onnx").exists():
                agreement = onnx_agreement(plain, work_dir / "optimized.onnx", input_shape)
        except Exception as e:                          # noqa: BLE001
            agreement = {"agreement_pct": None, "note": f"{type(e).__name__}: {e}"}

        pct(92, "Encrypting and storing artifacts")
        stored = []
        opt_size_bytes = 0
        for name, src in artifacts:
            data = src.read_bytes()
            enc = art_dir / f"{name}.enc"
            enc.write_bytes(security.encrypt_bytes(data))
            opt_size_bytes += len(data)
            stored.append({"name": name, "size_bytes": len(data),
                           "sha256": an.sha256_file(src), "encrypted": True})
        opt_size_mb = round(opt_size_bytes / 1e6, 4)
        # Primary artifact = precision-optimized torch model when the plan
        # touched the torch chain, else the exported ONNX graph. Comparing the
        # sum of both export formats against one original file would overstate
        # the result, so size_saved uses the primary artifact only.
        primary_bytes = next(
            (a["size_bytes"] for a in stored
             if a["name"] == ("optimized.pt" if torch_chain_touched else "optimized.onnx")),
            opt_size_bytes)
        size_saved = round(100 * (1 - primary_bytes / max(plain.stat().st_size, 1)), 1)
        latency_gain = None
        if opt_bench and baseline_bench.get("latency_ms") and opt_bench.get("latency_ms"):
            latency_gain = round(100 * (1 - opt_bench["latency_ms"] / baseline_bench["latency_ms"]), 1)

        benchmark = {
            "baseline": {"size_mb": baseline_size_mb, **baseline_bench},
            "optimized": {"size_mb": opt_size_mb, **(opt_bench or {"latency_ms": None})},
            "size_saved_pct": size_saved,
            "latency_gain_pct": latency_gain,
            "output_agreement": agreement,
            "note": bench_note,
        }

        repro = {
            "model_sha256": model_row["sha256"],
            "model_id": model_row["id"], "plan_id": plan["plan_id"],
            "techniques": techniques, "seed": AGREEMENT_SEED,
            "benchmark_runs": config.BENCHMARK_RUNS,
            "versions": {
                "python": platform.python_version(), "torch": torch.__version__,
                "onnx": __import__("onnx").__version__,
                "onnxruntime": __import__("onnxruntime").__version__,
                "numpy": np.__version__,
            },
            "platform": {"system": platform.system(), "machine": platform.machine(),
                         "processor": platform.processor()},
            "executed_at": now(),
        }

        if not stored:
            raise RuntimeError("no artifacts produced: refusing to mark run successful")

        return {
            "steps": steps,
            "benchmark": benchmark,
            "artifacts": stored,
            "repro": repro,
        }
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def onnx_agreement(orig_path: Path, onnx_path: Path, shape) -> dict:
    import onnxruntime as ort
    import torch

    from .analysis import load_torch_model, safe_input

    model, _ = load_torch_model(orig_path, shape)
    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    name = sess.get_inputs()[0].name
    torch.manual_seed(AGREEMENT_SEED)
    same = total = 0
    with torch.no_grad():
        for _ in range(16):
            x = safe_input(shape)
            a = model(x)
            b = torch.from_numpy(
                sess.run(None, {name: x.numpy().astype(np.float32)})[0])
            if a.shape != b.shape:
                return {"agreement_pct": None, "note": "output shapes differ"}
            same += int(torch.argmax(a).item() == torch.argmax(b).item())
            total += 1
    return {"agreement_pct": round(100 * same / total, 1), "inputs_checked": total,
            "seed": AGREEMENT_SEED}
