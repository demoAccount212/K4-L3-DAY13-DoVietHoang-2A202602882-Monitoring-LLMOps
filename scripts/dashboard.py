"""Day 13 monitoring dashboard — 6 panel đọc từ data/logs.jsonl theo config/dashboard.yaml.

Chạy (venv riêng, KHÔNG cài chung với API):
    streamlit run scripts/dashboard.py --server.port 8501

Mỗi panel có: tên (từ YAML), đơn vị, time range 60 phút, refresh 30 giây
(st.fragment run_every) và đường threshold (đường đứt đỏ) theo config/dashboard.yaml.
"""
from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "dashboard.yaml"
LOGS_PATH = ROOT / "data" / "logs.jsonl"

st.set_page_config(
    page_title="Day 13 Monitoring Dashboard",
    layout="wide",
    page_icon="📊",
)


def load_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


@st.cache_data(ttl=20, show_spinner=False)
def load_logs(window_minutes: int, now_minute: int) -> pd.DataFrame:
    """Đọc logs.jsonl và lọc về cửa sổ time range."""
    if not LOGS_PATH.exists():
        return pd.DataFrame()
    rows = [
        json.loads(line)
        for line in LOGS_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["ts"] = pd.to_datetime(df["ts"], format="ISO8601", utc=True)
    cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(minutes=window_minutes)
    df = df[df["ts"] >= cutoff].copy()
    # epoch phút hiện tại để cache key đổi sau mỗi phút (dữ liệu luôn mới khi rerun)
    _ = now_minute
    df["minute"] = df["ts"].dt.floor("min")
    return df.sort_values("ts")


def threshold_rule(value: float, color: str = "#d62728") -> alt.Chart:
    """Đường threshold đứt đỏ vẽ chồng lên panel."""
    return (
        alt.Chart(pd.DataFrame({"threshold": [value]}))
        .mark_rule(color=color, strokeDash=[6, 4], size=2)
        .encode(y="threshold:Q")
    )


def minute_index(df: pd.DataFrame) -> pd.DatetimeIndex:
    """Toàn bộ phút trong cửa sổ hiện tại (để các phút 0 request vẫn hiển thị)."""
    if df.empty:
        return pd.DatetimeIndex([])
    start = df["minute"].min().floor("min")
    end = pd.Timestamp.now(tz="UTC").floor("min")
    return pd.date_range(start, end, freq="min")


def time_chart(
    data: pd.DataFrame,
    y: str,
    y_title: str,
    color: str | None = None,
    mark: str = "line",
    tooltip_extra: list | None = None,
) -> alt.Chart:
    enc = {
        "x": alt.X("minute:T", title="time (UTC)", axis=alt.Axis(format="%H:%M")),
        "y": alt.Y(f"{y}:Q", title=y_title),
        "tooltip": [
            alt.Tooltip("minute:T", format="%H:%M"),
            alt.Tooltip(f"{y}:Q", format=",.4f"),
        ],
    }
    if color:
        enc["color"] = alt.Color(f"{color}:N", title="series")
        enc["detail"] = alt.Detail(f"{color}:N")
        enc["tooltip"].append(alt.Tooltip(f"{color}:N"))
    if tooltip_extra:
        enc["tooltip"].extend(tooltip_extra)
    chart_builder = getattr(alt.Chart(data), f"mark_{mark}")  # mark_line / mark_bar
    chart = chart_builder(size=12) if mark == "bar" else chart_builder()
    return chart.encode(**enc)


# ---------------------------------------------------------------- render ----
cfg = load_config()
dash = cfg["dashboard"]
window = int(dash["time_range_minutes"])
refresh = int(dash["refresh_seconds"])
panels = {p["id"]: p for p in dash["panels"]}

st.title(f"📊 {dash['title']}")
st.caption(
    f"Source: `data/logs.jsonl` · contract: `config/dashboard.yaml` · "
    f"time range: last **{window} minutes** (UTC) · auto-refresh: every **{refresh}s** · "
    f"red dashed line = threshold"
)

g_guard = yaml.safe_load((ROOT / "config" / "slo.yaml").read_text(encoding="utf-8"))["guardrails"]


@st.fragment(run_every=timedelta(seconds=refresh))
def render_dashboard() -> None:
    import time as _time

    df = load_logs(window, int(_time.time() // 60))
    if df.empty:
        st.info(f"Chưa có log nào trong {window} phút gần nhất — hãy chạy `python scripts/load_test.py`.")
        return
    # Đảm bảo các cột optional luôn tồn tại (request_failed có thể thiếu tool_success...)
    for extra in ("tool_success", "error_type", "quality_score", "ttft_ms", "cost_usd", "tokens_in", "tokens_out"):
        if extra not in df.columns:
            df[extra] = pd.NA

    lat_p = panels["latency"]
    tra_p = panels["traffic"]
    err_p = panels["errors"]
    cost_p = panels["cost"]
    tok_p = panels["tokens"]
    qua_p = panels["quality"]

    # ------------------------------------------------ 1) Latency ----------
    with st.container(border=True):
        st.subheader(f"{lat_p['title']}  |  unit: {lat_p['unit']}")
        rs = df[(df["event"] == "response_sent") & df["latency_ms"].notna()]
        if rs.empty:
            st.info("No response_sent data in window.")
        else:
            p50, p95, p99 = (rs["latency_ms"].quantile(q) for q in (0.5, 0.95, 0.99))
            ttft_p95 = rs["ttft_ms"].quantile(0.95)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("P50", f"{p50:,.0f} ms")
            c2.metric("P95", f"{p95:,.0f} ms", delta=None if p95 <= 3000 else "over SLO!", delta_color="inverse")
            c3.metric("P99", f"{p99:,.0f} ms")
            c4.metric("TTFT P95", f"{ttft_p95:,.0f} ms")
            per = (
                rs.groupby("minute")
                .agg(p50=("latency_ms", "median"), p95=("latency_ms", lambda s: s.quantile(0.95)))
                .reindex(minute_index(rs))
                .rename_axis("minute")  # reindex() làm mất index name trên pandas 3.x
                .reset_index()
                .melt(id_vars="minute", var_name="series", value_name="ms")
            )
            chart = time_chart(per, "ms", "ms", color="series") + threshold_rule(
                lat_p["threshold"]["value"]
            )
            st.altair_chart(chart, use_container_width=True)
            st.caption(f"query: `{lat_p['query']}` — threshold: {lat_p['threshold']['aggregation']} ≤ {lat_p['threshold']['value']} ms (SLO)")

    # ------------------------------------------------ 2) Traffic ----------
    with st.container(border=True):
        st.subheader(f"{tra_p['title']}  |  unit: {tra_p['unit']}")
        recv = df[df["event"] == "request_received"]
        counts = recv.groupby("minute").size().reindex(minute_index(recv), fill_value=0)
        per = counts.reset_index()
        per.columns = ["minute", "requests_per_minute"]
        c1, c2, c3 = st.columns(3)
        c1.metric("Total requests (60m)", int(counts.sum()))
        c2.metric("Avg req/min", f"{counts.mean():.2f}" if len(counts) else "0.00")
        c3.metric("Peak req/min", int(counts.max()) if len(counts) else 0)
        chart = time_chart(per, "requests_per_minute", "requests/min", mark="bar") + threshold_rule(
            tra_p["threshold"]["value"], color="#ff7f0e"
        )
        st.altair_chart(chart, use_container_width=True)
        st.caption(f"query: `{tra_p['query']}` — threshold: rate ≥ {tra_p['threshold']['value']} req/min")

    # ------------------------------------------------ 3) Errors ----------
    with st.container(border=True):
        st.subheader(f"{err_p['title']}  |  unit: {err_p['unit']}")
        n_recv = int((df["event"] == "request_received").sum())
        n_fail = int((df["event"] == "request_failed").sum())
        error_rate = 100.0 * n_fail / max(n_recv, 1)
        tool = df[df["tool_success"].notna()]
        retr_rate = 100.0 * tool["tool_success"].sum() / len(tool) if len(tool) else float("nan")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Error rate", f"{error_rate:.2f} %", delta=None if error_rate <= 2 else "over guardrail!", delta_color="inverse")
        c2.metric("Retrieval success", f"{retr_rate:.1f} %", delta=None if retr_rate >= 90 else "under guardrail!", delta_color="normal")
        c3.metric("request_failed", n_fail)
        c4.metric("request_received", n_recv)
        idx = minute_index(df)
        fail_pm = df[df["event"] == "request_failed"].groupby("minute").size().reindex(idx, fill_value=0)
        recv_pm = df[df["event"] == "request_received"].groupby("minute").size().reindex(idx, fill_value=0)
        err_pm = (100.0 * fail_pm / recv_pm.where(recv_pm > 0)).fillna(0.0)
        retr_pm = (
            df[df["tool_success"].notna()]
            .assign(ok=lambda d: d["tool_success"].astype(float))
            .groupby("minute")["ok"]
            .mean()
            .mul(100)
            .reindex(idx)
            .ffill()
        )
        per = pd.concat(
            [
                pd.DataFrame(
                    {"minute": idx, "series": "error_rate_pct", "value": err_pm.to_numpy(dtype=float)}
                ),
                pd.DataFrame(
                    {
                        "minute": idx,
                        "series": "retrieval_success_pct",
                        "value": retr_pm.to_numpy(dtype=float),
                    }
                ),
            ],
            ignore_index=True,
        )
        per["value"] = per["value"].astype(float)
        chart = time_chart(per, "value", "percent", color="series") + threshold_rule(
            err_p["threshold"]["value"]
        )
        st.altair_chart(chart, use_container_width=True)
        if n_fail:
            by_err = df[df["event"] == "request_failed"]["error_type"].value_counts()
            st.caption("error_type counts: " + ", ".join(f"`{k}`={v}" for k, v in by_err.items()))
        st.caption(f"query: `{err_p['query']}` — threshold: error_rate ≤ {err_p['threshold']['value']}% · retrieval guardrail ≥ {g_guard['retrieval_success_rate_pct_min']}%")

    # ------------------------------------------------ 4) Cost ------------
    with st.container(border=True):
        st.subheader(f"{cost_p['title']}  |  unit: {cost_p['unit']}")
        rs = df[df["event"] == "response_sent"]
        total = float(rs["cost_usd"].fillna(0).sum())
        per_min = rs.groupby("minute")["cost_usd"].sum().reindex(minute_index(rs), fill_value=0.0)
        c1, c2, c3 = st.columns(3)
        c1.metric("Total cost (60m)", f"${total:.4f}", delta=f"budget ${cost_p['threshold']['value']}/day")
        c2.metric("Projected 24h", f"${total / window * 1440:.2f}", delta=None if total / window * 1440 <= 2.5 else "over budget!", delta_color="inverse")
        c3.metric("Avg cost/req", f"${total / max(len(rs), 1):.5f}")
        cum = per_min.cumsum().reset_index()
        cum.columns = ["minute", "cumulative_usd"]
        chart = time_chart(cum, "cumulative_usd", "USD (cumulative)") + threshold_rule(
            cost_p["threshold"]["value"]
        )
        st.altair_chart(chart, use_container_width=True)
        st.caption(f"query: `{cost_p['query']}` — threshold: total ≤ ${cost_p['threshold']['value']} (daily, guardrail `daily_cost_usd_max`)")

    # ------------------------------------------------ 5) Tokens ----------
    with st.container(border=True):
        st.subheader(f"{tok_p['title']}  |  unit: {tok_p['unit']}")
        rs = df[df["event"] == "response_sent"]
        tin = int(rs["tokens_in"].fillna(0).sum())
        tout = int(rs["tokens_out"].fillna(0).sum())
        c1, c2, c3 = st.columns(3)
        c1.metric("Total input tokens", f"{tin:,}")
        c2.metric("Total output tokens", f"{tout:,}")
        c3.metric("Avg in/out per req", f"{tin / max(len(rs), 1):.0f} / {tout / max(len(rs), 1):.0f}")
        # Vẽ cumulative để threshold sum_by_field = 50000 có nghĩa
        cum = (
            rs.sort_values("ts")
            .groupby("minute")[["tokens_in", "tokens_out"]]
            .sum()
            .reindex(minute_index(rs), fill_value=0)
            .cumsum()
            .rename_axis("minute")  # reindex() làm mất index name trên pandas 3.x
            .reset_index()
            .melt(id_vars="minute", var_name="series", value_name="tokens")
        )
        cum["series"] = cum["series"].map({"tokens_in": "cumulative_input", "tokens_out": "cumulative_output"})
        chart = time_chart(cum, "tokens", "tokens (cumulative)", color="series") + threshold_rule(
            tok_p["threshold"]["value"]
        )
        st.altair_chart(chart, use_container_width=True)
        st.caption(f"query: `{tok_p['query']}` — threshold: total ≤ {tok_p['threshold']['value']:,} tokens")

    # ------------------------------------------------ 6) Quality ---------
    with st.container(border=True):
        st.subheader(f"{qua_p['title']}  |  unit: {qua_p['unit']}")
        rs = df[(df["event"] == "response_sent") & df["quality_score"].notna()]
        mean_q = float(rs["quality_score"].mean()) if len(rs) else float("nan")
        c1, c2, c3 = st.columns(3)
        c1.metric("Mean quality (60m)", f"{mean_q:.3f}", delta=None if mean_q >= 0.75 else "under guardrail!", delta_color="normal")
        c2.metric("Min", f"{rs['quality_score'].min():.3f}" if len(rs) else "-")
        c3.metric("Guardrail", f"≥ {qua_p['threshold']['value']}")
        per = (
            rs.groupby("minute")["quality_score"]
            .mean()
            .reindex(minute_index(rs))
            .reset_index()
        )
        per.columns = ["minute", "quality_score"]
        per["quality_score"] = per["quality_score"].ffill()
        chart = time_chart(per, "quality_score", "score (0-1)") + threshold_rule(
            qua_p["threshold"]["value"], color="#2ca02c"
        )
        st.altair_chart(chart, use_container_width=True)
        st.caption(f"query: `{qua_p['query']}` — threshold: mean ≥ {qua_p['threshold']['value']} (guardrail `quality_score_avg_min`)")


render_dashboard()
