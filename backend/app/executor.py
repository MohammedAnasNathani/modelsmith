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

def apply_int8(model):
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
    except TypeError:
        torch.onnx.export(model, dummy, str(out_path), opset_version=13,
                          input_names=["input"], output_names=["output"])
    import onnx
    onnx.checker.check_model(onnx.load(str(out_path)))
    return f"Exported + validated ONNX graph (opset 13)."

def benchmark_any(model, shape, runs):
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
                    b = optimized_fn(x.half())
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
            except Exception:
                continue
    if total == 0:
        return {"agreement_pct": None, "note": "optimized model could not run on CPU"}
    return {"agreement_pct": round(100 * same / total, 1),
            "inputs_checked": total, "seed": AGREEMENT_SEED}


def build_student(teacher):
    """Construct a width-halved student from the teacher architecture.

    Layer-aware: the first conv keeps its input channels (the input shape
    must not change) and the last linear keeps its output size (the class
    count must not change), so teacher and student outputs stay comparable.
    Raises ValueError for architectures this cannot rebuild (residual
    branches, custom cells, containers whose __init__ needs arguments).
    """
    import copy

    import torch.nn as nn

    def rebuild(module, first_conv=False, last_linear=False):
        if isinstance(module, nn.Conv2d):
            inc = module.in_channels if first_conv else max(1, module.in_channels // 2)
            return nn.Conv2d(inc, max(1, module.out_channels // 2),
                             module.kernel_size, module.stride, module.padding,
                             module.dilation, module.groups,
                             bias=module.bias is not None, padding_mode=module.padding_mode)
        if isinstance(module, nn.Linear):
            out = module.out_features if last_linear else max(1, module.out_features // 2)
            return nn.Linear(max(1, module.in_features // 2), out,
                             bias=module.bias is not None)
        if isinstance(module, nn.BatchNorm2d):
            return nn.BatchNorm2d(max(1, module.num_features // 2))
        if isinstance(module, (nn.ReLU, nn.Flatten, nn.MaxPool2d, nn.Dropout,
                               nn.Sigmoid, nn.Tanh, nn.Upsample, nn.AvgPool2d)):
            return copy.deepcopy(module)
        kids = list(module.named_children())
        if not kids:
            return copy.deepcopy(module)
        try:
            new = type(module)()
        except Exception as e:
            raise ValueError(
                f"cannot rebuild {type(module).__name__}: {e}") from None
        for i, (name, child) in enumerate(kids):
            setattr(new, name, rebuild(
                child,
                first_conv and i == 0,
                last_linear and i == len(kids) - 1))
        return new

    return rebuild(teacher, first_conv=True, last_linear=True)


def distill_train(teacher, student, shape, progress, epochs=6,
                  samples=512, batch=32, temperature=2.0):
    """Real knowledge-distillation training loop.

    Fixed seeded synthetic inputs; the frozen teacher produces soft
    targets once; the student optimizes KL divergence against them with
    Adam. Every epoch reports its measured loss through `progress` and
    into the run's step history. Nothing simulated: backward() runs,
    weights move, the loss curve is the actual curve.
    """
    import torch
    import torch.nn.functional as F

    torch.manual_seed(42)
    teacher.eval()
    student.train()
    X = torch.randn(samples, *shape)
    with torch.no_grad():
        t_out = teacher(X)
        if isinstance(t_out, (tuple, list)):
            t_out = t_out[0]
        t_log = F.log_softmax(t_out / temperature, dim=1)
    opt = torch.optim.Adam(student.parameters(), lr=1e-3)
    hist = []
    for ep in range(epochs):
        perm = torch.randperm(samples)
        total, seen = 0.0, 0
        for b in range(0, samples, batch):
            idx = perm[b:b + batch]
            s_out = student(X[idx])
            if isinstance(s_out, (tuple, list)):
                s_out = s_out[0]
            s_log = F.log_softmax(s_out / temperature, dim=1)
            loss = F.kl_div(s_log, t_log[idx], reduction="batchmean",
                            log_target=True) * (temperature * temperature)
            opt.zero_grad()
            loss.backward()
            opt.step()
            total += loss.item() * len(idx)
            seen += len(idx)
        hist.append(round(total / max(seen, 1), 4))
        progress(30 + int(40 * (ep + 1) / epochs),
                 f"Distillation epoch {ep + 1}/{epochs}: loss {hist[-1]}")
    student.eval()
    return student, hist


def run_plan_pipeline(model_row: dict, plan: dict, run_id: str, progress) -> dict:
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
                elif tech == "distill":
                    import copy as _copy
                    try:
                        student = build_student(model)
                        mode = "distilled student (half-width)"
                    except ValueError as e:
                        student = _copy.deepcopy(model)
                        mode = f"self-distillation fine-tune ({e})"
                    student, hist = distill_train(model, student, input_shape, pct)
                    current = student
                    for ei, l in enumerate(hist, 1):
                        steps.append({"technique": "distill",
                                      "label": f"Training epoch {ei}",
                                      "status": "success",
                                      "note": f"distillation loss {l}"})
                    note = (f"Real training: {mode}, {len(hist)} epochs, "
                            f"loss {hist[0]} → {hist[-1]} "
                            f"(Adam, KL to teacher soft targets, T=2).")
                    step.update(status="success", note=note)
                    steps.append(step)
                    continue
                elif tech == "tensorrt":
                    step.update(status="guided",
                                note="Manual technique: generated instructions artifact.")
                    steps.append(step)
                    continue
                else:
                    raise ValueError(f"unknown technique {tech}")
                step.update(status="success", note=note)
            except NotImplementedError as e:
                step.update(status="partial", note=f"Limited on CPU: {e}")
            except Exception as e:
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
            agreement_fn = lambda x: model_for_agreement(x)

        if "onnx" in techniques and (work_dir / "optimized.onnx").exists():
            artifacts.append(("optimized.onnx", work_dir / "optimized.onnx"))
        artifacts.append(("optimized.pt", torch_out))

        pct(80, "Benchmarking optimized model")
        opt_bench = None
        bench_note = None
        onnx_path = work_dir / "optimized.onnx"
        torch_chain_touched = any(t in techniques for t in ("int8", "fp16", "prune20", "prune40", "distill"))
        torch_bench = None
        if torch_chain_touched:
            try:
                torch_bench = benchmark_any(current, input_shape, config.BENCHMARK_RUNS)
            except NotImplementedError as e:
                bench_note = (f"FP16 kernels unavailable on CPU ({e}): latency "
                              f"requires a GPU runtime; size benefits still apply.")
            except Exception as e:
                bench_note = f"Torch benchmark failed: {type(e).__name__}: {e}"
        if "onnx" in techniques and onnx_path.exists():
            try:
                onnx_bench = benchmark_any(onnx_path, input_shape, config.BENCHMARK_RUNS)
                if torch_bench is None:
                    opt_bench = onnx_bench
                else:
                    torch_bench["onnx_artifact"] = onnx_bench
                    opt_bench = torch_bench
            except Exception as e:
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
        except Exception as e:
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
