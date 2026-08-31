"""FR-04 Model Analysis + FR-05 Profiling.

Framework adapters (NFR-11):
- PyTorch: full serialized module (.pt/.pth produced by torch.save(model)),
  or a demo-architecture export {"state_dict", "config"} rebuilt from the
  built-in architecture registry.
- ONNX: graph inspection + onnxruntime benchmarking.

Produces the analysis record consumed by the planner: layer/operator table,
parameter counts, FLOPs estimate, memory estimates, measured latency profile
and bottleneck notes.
"""
from __future__ import annotations

import hashlib
import platform
import time
from pathlib import Path

import numpy as np

# ------------------------------------------------------------------ registry
TORCH_ARCH_REGISTRY: dict[str, type] = {}


def _register_arch(cls):
    TORCH_ARCH_REGISTRY[cls.__name__.lower()] = cls
    return cls


try:
    import torch
    import torch.nn as nn
except ImportError:            # allows auth/admin endpoints to run torch-less
    torch = None
    nn = object

if torch is not None:
    import torch.nn as _nn
    import torchvision

    @_register_arch
    class MnistCnn(_nn.Module):
        def __init__(self):
            super().__init__()
            self.net = _nn.Sequential(
                _nn.Conv2d(1, 10, 5), _nn.ReLU(), _nn.MaxPool2d(2),
                _nn.Conv2d(10, 20, 5), _nn.ReLU(), _nn.MaxPool2d(2),
                _nn.Flatten(), _nn.Linear(320, 50), _nn.ReLU(), _nn.Linear(50, 10),
            )

        def forward(self, x):
            return self.net(x)

    @_register_arch
    class CifarCnn(_nn.Module):
        def __init__(self):
            super().__init__()
            self.net = _nn.Sequential(
                _nn.Conv2d(3, 32, 3, padding=1), _nn.BatchNorm2d(32), _nn.ReLU(),
                _nn.Conv2d(32, 48, 3, padding=1), _nn.BatchNorm2d(48), _nn.ReLU(),
                _nn.MaxPool2d(2),
                _nn.Conv2d(48, 64, 3, padding=1), _nn.BatchNorm2d(64), _nn.ReLU(),
                _nn.MaxPool2d(2),
                _nn.Flatten(), _nn.Linear(64 * 8 * 8, 128), _nn.ReLU(),
                _nn.Linear(128, 10),
            )

        def forward(self, x):
            return self.net(x)

    @_register_arch
    class ResNet18Stub(torchvision.models.resnet.ResNet):
        """ResNet-18 skeleton with random weights: same architecture, no
        pretrained checkpoint, so the demo needs no network download."""

    def _build_resnet18():
        m = ResNet18Stub(torchvision.models.resnet.BasicBlock, [2, 2, 2, 2])
        m.eval()
        return m

    ARCH_BUILDERS = {
        "mnistcnn": MnistCnn,
        "cifarcnn": CifarCnn,
        "resnet18stub": _build_resnet18,
    }
else:
    ARCH_BUILDERS = {}


# ------------------------------------------------------------------- torch io
def load_torch_model(path: Path, input_shape: tuple | None):
    """Load a torch artifact; returns (model, input_shape)."""
    if torch is None:
        raise RuntimeError("PyTorch is not installed in this environment")
    obj = torch.load(str(path), map_location="cpu", weights_only=False)
    if isinstance(obj, dict) and "state_dict" in obj and "config" in obj:
        arch = str(obj.get("config", {}).get("arch", "")).lower()
        builder = ARCH_BUILDERS.get(arch)
        if builder is None:
            raise ValueError(
                "state_dict upload needs a known 'config.arch'. "
                f"Known: {sorted(ARCH_BUILDERS)}. Otherwise save the full module."
            )
        model = builder()
        model.load_state_dict(obj["state_dict"])
    else:
        model = obj
    if not hasattr(model, "forward"):
        raise ValueError("File does not contain a serializable nn.Module")
    model.eval()
    shape = tuple(input_shape) if input_shape else infer_input_shape(model)
    return model, shape


def infer_input_shape(model) -> tuple:
    """Infer a representative input shape from the first feature layer."""
    import torch.nn as nn

    default_spatial = {1: 28, 3: 32}
    for m in model.modules():
        if isinstance(m, nn.Conv2d):
            c = m.in_channels
            s = default_spatial.get(c, 64)
            return (c, s, s)
        if isinstance(m, nn.Conv1d):
            return (m.in_channels, 128)
        if isinstance(m, nn.Linear):
            return (m.in_features,)
    return (3, 32, 32)


def safe_input(shape: tuple):
    return torch.randn(1, *shape)


# ------------------------------------------------------------------ profiling
def _param_elems(m) -> int:
    return sum(p.numel() for p in m.parameters(recurse=False))


def benchmark_torch(model, shape: tuple, runs: int = 30) -> dict:
    x = safe_input(shape)
    with torch.no_grad():
        for _ in range(5):                    # warmup
            model(x)
        times = []
        for _ in range(runs):
            t0 = time.perf_counter()
            model(x)
            times.append((time.perf_counter() - t0) * 1000)
    arr = np.array(times)
    latency = float(np.mean(arr))
    return {
        "latency_ms": round(latency, 4),
        "p95_ms": round(float(np.percentile(arr, 95)), 4),
        "throughput_fps": round(1000.0 / latency, 1) if latency > 0 else None,
        "runs": runs,
        "runtime": "pytorch-cpu",
    }


def _flops_and_layers(model, shape: tuple) -> tuple[list[dict], float, int]:
    """Layer table + total FLOPs via forward hooks (multiply-adds x2)."""
    layers: list[dict] = []
    flops = [0.0]

    def elem_count(t):
        if isinstance(t, torch.Tensor):
            return t.numel()
        return 0

    def hook(name, module):
        def fn(_m, _inp, out):
            out_elems = sum(elem_count(t) for t in (out if isinstance(out, (tuple, list)) else [out]))
            f = 0.0
            if isinstance(module, torch.nn.Conv2d):
                k = module.kernel_size[0] * module.kernel_size[1]
                f = out_elems * (module.in_channels / module.groups) * k * 2
            elif isinstance(module, torch.nn.Linear):
                f = module.in_features * module.out_features * 2
            elif isinstance(module, (torch.nn.BatchNorm2d, torch.nn.BatchNorm1d,
                                     torch.nn.LayerNorm, torch.nn.GroupNorm)):
                f = out_elems * 2
            elif isinstance(module, (torch.nn.ReLU, torch.nn.MaxPool2d, torch.nn.AvgPool2d,
                                     torch.nn.Flatten, torch.nn.Dropout,
                                     torch.nn.Sigmoid, torch.nn.Tanh,
                                     torch.nn.Upsample, torch.nn.ZeroPad2d)):
                f = out_elems
            elif isinstance(module, (torch.nn.RNN, torch.nn.LSTM, torch.nn.GRU)):
                f = sum(4 * (module.input_size + module.hidden_size) * module.hidden_size
                        for _ in range(2)) * module.num_layers
            flops[0] += f
            params = _param_elems(module)
            if params or f:
                layers.append({
                    "name": name, "type": type(module).__name__,
                    "params": params,
                    "size_bytes": sum(p.numel() * p.element_size() for p in module.parameters(recurse=False)),
                    "dtype": next((str(p.dtype).replace("torch.", "") for p in module.parameters()), None),
                    "flops": round(f),
                })
        return fn

    handles = []
    for name, module in model.named_modules():
        if len(list(module.children())) == 0 and not isinstance(module, torch.nn.Sequential):
            handles.append(module.register_forward_hook(hook(name, module)))
    try:
        with torch.no_grad():
            model(safe_input(shape))
    finally:
        for h in handles:
            h.remove()

    layers.sort(key=lambda l: l["params"], reverse=True)
    return layers, flops[0], len(layers)


def analyze_torch(path: Path, input_shape: tuple | None, runs: int) -> dict:
    model, shape = load_torch_model(path, input_shape)
    layers, flops, layer_count = _flops_and_layers(model, shape)
    total_params = sum(p.numel() for p in model.parameters())
    param_bytes = sum(p.numel() * p.element_size() for p in model.parameters())
    bench = benchmark_torch(model, shape, runs)

    conv_params = sum(l["params"] for l in layers if l["type"] == "Conv2d")
    lin_params = sum(l["params"] for l in layers if l["type"] == "Linear")
    if conv_params == 0:
        arch = "mlp"
    elif lin_params == 0:
        arch = "cnn"
    else:
        arch = "cnn" if conv_params > lin_params * 2 else "hybrid"

    return _finalize_analysis({
        "framework": "pytorch",
        "input_shape": list(shape),
        "total_params": total_params,
        "param_size_mb": round(param_bytes / 1e6, 4),
        "file_size_mb": round(path.stat().st_size / 1e6, 4),
        "total_flops": round(flops),
        "layer_count": layer_count,
        "layers": layers[:40],
        "benchmark": bench,
        "arch": arch,
        "conv_param_share_pct": round(100 * conv_params / max(total_params, 1), 1),
    })


# ---------------------------------------------------------------------- onnx
def analyze_onnx(path: Path, runs: int) -> dict:
    import onnx
    import onnxruntime as ort

    m = onnx.load(str(path))
    onnx.checker.check_model(m)

    inits = m.graph.initializer
    param_bytes = sum(onnx.helper.tensor_dtype_to_np_dtype(i.data_type).itemsize *
                      int(np.prod(i.dims)) if i.dims else
                      onnx.helper.tensor_dtype_to_np_dtype(i.data_type).itemsize
                      for i in inits)
    total_params = sum(int(np.prod(i.dims)) if i.dims else 1 for i in inits)

    ops: dict[str, int] = {}
    flops = 0.0
    for node in m.graph.node:
        ops[node.op_type] = ops.get(node.op_type, 0) + 1
        attrs = {a.name: a for a in node.attribute}
        if node.op_type == "Conv":
            g = attrs.get("group", None)
            group = g.i if g else 1
            for init in inits:
                if init.name == node.input[1]:
                    oc, ic = list(init.dims)[0], list(init.dims)[1]
                    kh, kw = (list(init.dims)[2], list(init.dims)[3]) if len(init.dims) > 3 else (1, 1)
                    spatial = 1
                    for out in m.graph.value_info:
                        if out.name == node.output[0]:
                            dd = [d.dim_value for d in out.type.tensor_type.shape.dim]
                            spatial = int(np.prod(dd[2:])) if len(dd) > 2 else 1
                    flops += oc * (ic / group) * kh * kw * spatial * 2
                    break
        elif node.op_type in ("Gemm", "MatMul"):
            for init in inits:
                if init.name in node.input:
                    flops += int(np.prod(init.dims)) * 2
                    break
        elif node.op_type in ("Relu", "Sigmoid", "Tanh", "MaxPool", "AveragePool",
                              "Softmax", "Dropout"):
            flops += 10_000  # small elementwise/pooling allowance

    input_shape = []
    if m.graph.input:
        dims = m.graph.input[0].type.tensor_type.shape.dim
        input_shape = [d.dim_value or 1 for d in dims]

    sess = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    x = np.random.rand(1, *input_shape).astype(np.float32)
    sess.run(None, {sess.get_inputs()[0].name: x})
    times = []
    for _ in range(runs):
        t0 = time.perf_counter()
        sess.run(None, {sess.get_inputs()[0].name: x})
        times.append((time.perf_counter() - t0) * 1000)
    arr = np.array(times)
    latency = float(np.mean(arr))

    layers = [{"name": f"onnx:{op}", "type": op, "count": c, "params": 0,
               "size_bytes": 0, "dtype": None, "flops": 0} for op, c in sorted(ops.items())]
    return _finalize_analysis({
        "framework": "onnx",
        "input_shape": input_shape,
        "total_params": total_params,
        "param_size_mb": round(param_bytes / 1e6, 4),
        "file_size_mb": round(path.stat().st_size / 1e6, 4),
        "total_flops": round(flops),
        "layer_count": sum(ops.values()),
        "layers": layers,
        "benchmark": {
            "latency_ms": round(latency, 4),
            "p95_ms": round(float(np.percentile(arr, 95)), 4),
            "throughput_fps": round(1000.0 / latency, 1) if latency > 0 else None,
            "runs": runs,
            "runtime": f"onnxruntime-{ort.__version__}",
        },
        "arch": "onnx-graph",
        "conv_param_share_pct": 0.0,
    })


# -------------------------------------------------------------- bottlenecks
def _finalize_analysis(analysis: dict) -> dict:
    """FR-05: bottleneck / hotspot detection with human-readable notes."""
    layers = [l for l in analysis["layers"] if l.get("params")]
    top = layers[:3]
    param_conc = 0.0
    if layers and analysis["total_params"]:
        param_conc = round(100 * sum(l["params"] for l in top) / analysis["total_params"], 1)

    notes = []
    for l in top:
        share = round(100 * l["params"] / max(analysis["total_params"], 1), 1)
        notes.append(f"{l['type']} layer '{l['name']}' holds {share}% of parameters "
                     f"({l['params']:,}): primary target for quantization/pruning.")
    if analysis.get("arch") == "mlp":
        notes.append("Linear layers dominate: dynamic INT8 quantization typically cuts "
                     "size ~4x with minimal accuracy impact on this shape.")
    elif analysis.get("arch") == "cnn":
        notes.append("Convolution-heavy: structured pruning + ONNX/TensorRT graph "
                     "optimization usually give the largest latency gains.")
    notes.append("All weights stored in FP32: precision reduction directly halves "
                 "memory footprint per conversion step.")

    analysis["bottlenecks"] = {
        "top_layers": top,
        "param_concentration_pct": param_conc,
        "notes": notes,
    }
    analysis["memory_estimate_mb"] = round(
        analysis["param_size_mb"] + analysis["total_flops"] * 1e-6, 4)
    analysis["environment"] = {
        "python": platform.python_version(),
        "machine": platform.machine(),
        "system": platform.system(),
    }
    return analysis


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
