"""FR-07 Optimization Planning, FR-08 Filtering & Ranking, FR-09 Prediction.

Knowledge-base driven: technique effects, hardware profiles and compatibility
rules produce ranked candidate plans with predicted trade-offs and explicit
reasons for every recommendation (NFR-10 explainability).
"""
from __future__ import annotations

# ------------------------------------------------------------- knowledge base
TECHNIQUES = {
    "int8": {
        "label": "INT8 Dynamic Quantization", "auto": True, "frameworks": ("pytorch",),
        "size": 0.25, "latency": {"mlp": 0.45, "hybrid": 0.55, "cnn": 0.70, "onnx-graph": 0.70},
        "memory": 0.30, "accuracy": 0.985,
        "why": "Compresses Linear/LSTM weights to 8-bit with per-channel scales: "
               "the standard ~4x size cut for dense layers.",
    },
    "fp16": {
        "label": "FP16 Half Precision", "auto": True, "frameworks": ("pytorch",),
        "size": 0.50, "latency": {"mlp": 0.85, "hybrid": 0.85, "cnn": 0.90, "onnx-graph": 0.90},
        "memory": 0.50, "accuracy": 0.999,
        "why": "Halves every weight; near-lossless accuracy, biggest wins on GPU runtimes.",
    },
    "prune20": {
        "label": "Structured Pruning (20%)", "auto": True, "frameworks": ("pytorch",),
        "size": 0.80, "latency": {"mlp": 0.88, "hybrid": 0.85, "cnn": 0.82, "onnx-graph": 0.85},
        "memory": 0.82, "accuracy": 0.98,
        "why": "Removes low-magnitude (near-zero contribution) channels: actual "
               "compute reduction, not just compression.",
    },
    "prune40": {
        "label": "Aggressive Pruning (40%)", "auto": True, "frameworks": ("pytorch",),
        "size": 0.62, "latency": {"mlp": 0.78, "hybrid": 0.74, "cnn": 0.68, "onnx-graph": 0.72},
        "memory": 0.70, "accuracy": 0.94,
        "why": "Deeper sparsity for heavily over-parameterized models; higher "
               "accuracy risk than the 20% variant.",
    },
    "onnx": {
        "label": "ONNX Export", "auto": True, "frameworks": ("pytorch",),
        "size": 1.00, "latency": {"mlp": 0.90, "hybrid": 0.88, "cnn": 0.85, "onnx-graph": 0.90},
        "memory": 1.00, "accuracy": 1.0,
        "why": "Graph-level operator fusion and constant folding in ONNX Runtime.",
    },
    "tensorrt": {
        "label": "TensorRT Build (guided)", "auto": False, "frameworks": ("pytorch", "onnx"),
        "size": 1.00, "latency": {"mlp": 0.55, "hybrid": 0.50, "cnn": 0.45, "onnx-graph": 0.50},
        "memory": 0.80, "accuracy": 1.0,
        "why": "NVIDIA kernel fusion + mixed precision; requires a GPU machine to build.",
    },
    "distill": {
        "label": "Knowledge Distillation (guided)", "auto": False, "frameworks": ("pytorch",),
        "size": 0.30, "latency": {"mlp": 0.35, "hybrid": 0.35, "cnn": 0.40, "onnx-graph": 0.40},
        "memory": 0.35, "accuracy": 0.97,
        "why": "Train a smaller student against this model: needs training data "
               "and multiple retraining cycles.",
    },
}

HARDWARE_PROFILES = {
    "cpu-server":   {"label": "CPU Server",       "memory_mb": 8192, "precisions": ["fp32", "fp16", "int8"], "runtimes": ["PyTorch", "ONNX Runtime"],            "preferred": ["int8", "onnx"]},
    "gpu-server":   {"label": "GPU Server",       "memory_mb": 16384, "precisions": ["fp32", "fp16", "int8"], "runtimes": ["TensorRT", "ONNX Runtime GPU"],        "preferred": ["fp16", "tensorrt"]},
    "edge-device":  {"label": "Edge Device",      "memory_mb": 2048,  "precisions": ["int8"],               "runtimes": ["ONNX Runtime Mobile", "TFLite"],         "preferred": ["int8", "onnx"]},
    "mobile":       {"label": "Mobile",           "memory_mb": 1024,  "precisions": ["int8"],               "runtimes": ["TFLite", "Core ML", "SNPE"],             "preferred": ["int8", "onnx"]},
    "web-browser":  {"label": "Web Browser",      "memory_mb": 512,   "precisions": ["fp16", "int8"],       "runtimes": ["ONNX Runtime Web", "WebGPU"],            "preferred": ["onnx", "int8"]},
}

GOALS_SCHEMA = {
    "objective": "min_size | min_latency | min_memory | balanced",
    "target_hardware": "cpu-server | gpu-server | edge-device | mobile | web-browser",
    "max_latency_ms": float,
    "max_size_mb": float,
    "min_accuracy_pct": float,
}

OBJECTIVE_WEIGHTS = {
    #              size  latency  memory  accuracy
    "min_size":     (0.55, 0.10,  0.15,  0.20),
    "min_latency":  (0.10, 0.55,  0.15,  0.20),
    "min_memory":   (0.15, 0.10,  0.55,  0.20),
    "balanced":     (0.30, 0.30,  0.20,  0.20),
}

CANDIDATE_COMBOS = [
    ("edge-max",    ["int8", "prune40", "onnx"], "Smallest footprint"),
    ("edge-lite",   ["int8", "onnx"], "Compact + fast"),
    ("speed",       ["prune20", "onnx"], "Latency focused"),
    ("half",        ["fp16", "onnx"], "Precision focused"),
    ("balanced",    ["int8", "prune20"], "Trade-off blend"),
    ("max-speed",   ["fp16", "tensorrt"], "GPU throughput"),
    ("deep-cut",    ["int8", "prune20", "onnx"], "Size + speed"),
    ("distill",     ["distill"], "Smallest via retraining"),
]


# ----------------------------------------------------------------- predictions
def _latency_factor(tech_id: str, arch: str) -> float:
    table = TECHNIQUES[tech_id]["latency"]
    return table.get(arch, table.get("cnn", 0.85))


def predict(analysis: dict, techniques: list[str]) -> dict:
    base_size = analysis.get("param_size_mb") or analysis.get("file_size_mb", 1.0)
    base_latency = analysis.get("benchmark", {}).get("latency_ms", 10.0)
    arch = analysis.get("arch", "hybrid")

    size_f = lat_f = mem_f = acc_f = 1.0
    for t in techniques:
        tech = TECHNIQUES[t]
        size_f *= tech["size"]
        lat_f *= _latency_factor(t, arch)
        mem_f *= tech["memory"]
        acc_f *= tech["accuracy"]

    return {
        "size_mb": round(base_size * size_f, 4),
        "size_saved_pct": round((1 - size_f) * 100, 1),
        "latency_ms": round(base_latency * lat_f, 4),
        "latency_gain_pct": round((1 - lat_f) * 100, 1),
        "memory_mb": round(base_size * mem_f * 1.2, 4),
        "memory_saved_pct": round((1 - mem_f) * 100, 1),
        "accuracy_retention_pct": round(acc_f * 100, 1),
    }


# --------------------------------------------------------- generate + filter
def _compatibility(plan_techniques: list[str], analysis: dict, goals: dict) -> list[str]:
    """FR-08: return reasons this plan is INCOMPATIBLE (empty = valid)."""
    reasons = []
    framework = analysis.get("framework", "pytorch")
    for t in plan_techniques:
        if framework not in TECHNIQUES[t]["frameworks"]:
            reasons.append(f"{TECHNIQUES[t]['label']} does not apply to {framework} models.")
    hw = HARDWARE_PROFILES.get(goals.get("target_hardware", "cpu-server"), {})
    if "tensorrt" in plan_techniques and "gpu-server" not in goals.get("target_hardware", ""):
        reasons.append("TensorRT requires a GPU server target.")
    if "fp16" in plan_techniques and hw and "fp16" not in hw.get("precisions", []):
        reasons.append(f"{hw['label']} does not reliably support FP16.")
    if "int8" in plan_techniques and hw and "int8" not in hw.get("precisions", []):
        reasons.append(f"{hw['label']} lacks INT8 kernels.")
    return reasons


def _score(prediction: dict, objective: str) -> float:
    w = OBJECTIVE_WEIGHTS.get(objective, OBJECTIVE_WEIGHTS["balanced"])
    return round(
        w[0] * prediction["size_saved_pct"]
        + w[1] * prediction["latency_gain_pct"]
        + w[2] * prediction["memory_saved_pct"]
        + w[3] * prediction["accuracy_retention_pct"],
        2,
    )


def generate_plans(analysis: dict, goals: dict) -> dict:
    """FR-07 + FR-08 + FR-09: candidates -> filter -> rank -> explain.

    Returns {"valid": [...], "rejected": [...]} with each plan carrying
    techniques, predicted trade-offs, score and recommendation reasons.
    """
    objective = goals.get("objective", "balanced")
    min_acc = float(goals.get("min_accuracy_pct", 90))
    hw_key = goals.get("target_hardware", "cpu-server")
    hw = HARDWARE_PROFILES.get(hw_key, HARDWARE_PROFILES["cpu-server"])

    valid, rejected = [], []
    for plan_id, techniques, tagline in CANDIDATE_COMBOS:
        compat_fail = _compatibility(techniques, analysis, goals)
        pred = predict(analysis, techniques)
        auto = all(TECHNIQUES[t]["auto"] for t in techniques)
        reasons = [
            TECHNIQUES[t]["why"] for t in techniques
            if t in ("int8", "fp16", "prune20", "prune40", "onnx", "tensorrt", "distill")
        ]
        base = {
            "plan_id": plan_id, "tagline": tagline, "techniques": techniques,
            "technique_labels": [TECHNIQUES[t]["label"] for t in techniques],
            "auto_executable": auto,
            "predicted": pred, "reasons": reasons,
        }
        if compat_fail:
            rejected.append(base | {"rejected_because": compat_fail})
        elif pred["accuracy_retention_pct"] < min_acc:
            rejected.append(base | {"rejected_because": [
                f"Predicted accuracy retention {pred['accuracy_retention_pct']}% is below "
                f"your {min_acc}% minimum."]})
        else:
            base["score"] = _score(pred, objective)
            hw_note = ("Matches target runtimes " + ", ".join(hw["preferred"])
                       if set(hw.get("preferred", [])) & set(techniques)
                       else f"Runnable on {hw['label']} ({', '.join(hw['runtimes'])})")
            base["reasons"].insert(0, hw_note)
            valid.append(base)

    valid.sort(key=lambda p: p["score"], reverse=True)
    for i, p in enumerate(valid, 1):
        p["rank"] = i
        p["recommended"] = i == 1
    return {"objective": objective, "target_hardware": hw_key,
            "hardware": hw, "valid": valid, "rejected": rejected}


DEFAULT_GOALS = {
    "objective": "balanced",
    "target_hardware": "cpu-server",
    "max_latency_ms": None,
    "max_size_mb": None,
    "min_accuracy_pct": 95.0,
}
