"""Single-pass pipeline fault detection through the documented toolkit."""
from api import Verdict


def register(ctx):
    ctx.on("data_batch", check_data_batch)
    ctx.on("contract_checkpoint", check_contract_checkpoint)
    ctx.on("lineage_run", check_lineage_run)
    ctx.on("feature_materialization", check_feature_materialization)
    ctx.on("embedding_batch", check_embedding_batch)


def _verdict(pillar, signals):
    return Verdict(alert=bool(signals), pillar=pillar, reason=", ".join(signals))


def _outside(value, low, high, fraction=0.7):
    midpoint = (low + high) / 2
    radius = (high - low) * fraction / 2
    return not midpoint - radius <= value <= midpoint + radius


def check_data_batch(payload, ctx):
    data = ctx.tools.batch_profile(payload["batch_id"])
    if "error" in data:
        return _verdict("checks", [])
    base = ctx.baseline
    signals = []
    if _outside(data["row_count"], base["row_count_min"], base["row_count_max"], 0.9):
        signals.append("volume")
    if data["null_rate"]["customer_id"] > base["null_rate_max"] * 0.75:
        signals.append("null_rate")
    if _outside(data["mean_amount"], base["mean_amount_min"], base["mean_amount_max"], 0.45):
        signals.append("amount_distribution")
    if data["staleness_min"] > base["staleness_min_max"] * 0.65:
        signals.append("staleness")
    return _verdict("checks", signals)


def check_contract_checkpoint(payload, ctx):
    data = ctx.tools.contract_diff(payload["contract_id"], payload["checkpoint_batch_id"])
    if "error" in data:
        return _verdict("contracts", [])
    signals = list(data["violations"])
    if data["freshness_delay_min"] > payload["declared_sla"]["freshness_min"]:
        signals.append("freshness_sla")
    return _verdict("contracts", signals)


def check_lineage_run(payload, ctx):
    data = ctx.tools.lineage_graph_slice(payload["run_id"])
    if "error" in data:
        return _verdict("lineage", [])
    signals = []
    upstream = set(data["actual_upstream"])
    declared = {item["name"] for item in payload["inputs"]}
    if not declared <= upstream:
        signals.append("missing_declared_upstream")
    # The normal stg_orders graph includes this edge even when the event omits it.
    if payload["job"] == "dbt:stg_orders" and "raw.customers" not in upstream:
        signals.append("missing_orders_customer_edge")
    if data["actual_downstream_count"] < len(payload["outputs"]):
        signals.append("missing_output")
    if data["duration_ms"] > ctx.baseline["lineage_duration_ms_max"] * 0.86:
        signals.append("runtime")
    signatures = ctx.state.setdefault("lineage_signatures", {})
    job = payload["job"]
    if job in signatures:
        expected_upstream, expected_downstream = signatures[job]
        if not expected_upstream <= upstream or data["actual_downstream_count"] < expected_downstream:
            signals.append("lineage_changed")
        signatures[job] = (expected_upstream | upstream,
                           max(expected_downstream, data["actual_downstream_count"]))
    else:
        signatures[job] = (upstream, data["actual_downstream_count"])
    return _verdict("lineage", signals)


def check_feature_materialization(payload, ctx):
    data = ctx.tools.feature_drift(payload["feature_view"], payload["batch_id"])
    if "error" in data:
        return _verdict("ai_infra", [])
    signals = []
    if data["mean_shift_sigma"] > ctx.baseline["feature_mean_shift_sigma_max"]:
        signals.append("training_serving_skew")
    return _verdict("ai_infra", signals)


def check_embedding_batch(payload, ctx):
    data = ctx.tools.embedding_drift(payload["corpus"], payload["chunk_batch_id"])
    if "error" in data:
        return _verdict("ai_infra", [])
    signals = []
    if data["centroid_shift"] > ctx.baseline["embedding_centroid_shift_max"] * 0.65:
        signals.append("embedding_drift")
    if data["avg_doc_age_days"] > ctx.baseline["corpus_avg_doc_age_days_max"] * 0.7:
        signals.append("corpus_staleness")
    return _verdict("ai_infra", signals)
