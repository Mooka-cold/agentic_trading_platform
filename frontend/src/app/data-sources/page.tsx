"use client";

import { SideNav } from "@/components/layout/SideNav";
import { useCallback, useEffect, useMemo, useState } from "react";
import { BarChart3, Database, Play, RefreshCw } from "lucide-react";

type CalibrationMetrics = {
  symbol: string;
  window_days: number;
  parameters?: Record<string, any>;
  before: Record<string, any>;
  after: Record<string, any>;
  delta: Record<string, any>;
  decision?: { passed: boolean; rules: string[] };
};

type CalibrationReport = {
  run_date: string;
  symbol: string;
  window_days: number;
  methodology: string[];
  execution_process: string[];
  metrics: CalibrationMetrics;
  created_at: string;
};

type CalibrationHistoryItem = {
  run_date: string;
  created_at: string;
  symbol: string;
  window_days: number;
  before: Record<string, any>;
  after: Record<string, any>;
  delta: Record<string, any>;
};

type CandidateResponse = {
  baseline: Record<string, any>;
  candidates: Record<string, any>[];
};

type ActiveParamsResponse = {
  config_key: string;
  applied_params: Record<string, any>;
  source?: string;
  updated_at?: string;
  description?: string;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:3201";
const PARAM_LABELS: Record<string, string> = {
  quality_confidence_floor: "质量置信门槛",
  min_magnitude: "最小影响强度",
  major_event_confidence_floor: "重大事件置信门槛",
  exclude_insufficient_evidence: "排除证据不足样本",
  exclude_low_severity: "排除低严重度样本",
  cluster_match: "簇直接匹配权重",
  impact_cluster_match: "影响簇匹配权重",
  symbol_match: "币种直接命中权重",
  symbol_cluster_match: "币种同簇匹配权重",
  unknown_general: "信息缺失默认权重",
  macro_only: "纯宏观新闻权重",
  other_related: "弱相关兜底权重"
};

export default function DataSourcesPage() {
  const [symbol, setSymbol] = useState("ETH/USDT");
  const [windowDays, setWindowDays] = useState(14);
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<CalibrationReport | null>(null);
  const [history, setHistory] = useState<CalibrationHistoryItem[]>([]);
  const [error, setError] = useState("");
  const [applyMessage, setApplyMessage] = useState("");
  const [applying, setApplying] = useState(false);
  const [rollingBack, setRollingBack] = useState(false);
  const [candidates, setCandidates] = useState<Record<string, any>[]>([]);
  const [selectedCandidateLabel, setSelectedCandidateLabel] = useState("baseline");
  const [activeParams, setActiveParams] = useState<Record<string, any> | null>(null);
  const [activeUpdatedAt, setActiveUpdatedAt] = useState<string>("");
  const [tuningParams, setTuningParams] = useState<Record<string, any>>({
    quality_confidence_floor: 0.35,
    exclude_insufficient_evidence: true,
    exclude_low_severity: true,
    min_magnitude: 0.35,
    major_event_confidence_floor: 0.55,
    relevance_weights: {
      cluster_match: 1.0,
      impact_cluster_match: 0.9,
      symbol_match: 0.95,
      macro_only: 0.75,
      unknown_general: 0.6,
      other_related: 0.4
    }
  });

  const loadData = useCallback(async () => {
    setError("");
    try {
      const [latestRes, historyRes, candidateRes, activeRes] = await Promise.all([
        fetch(`${API_URL}/api/v1/calibration/latest?symbol=${encodeURIComponent(symbol)}`),
        fetch(`${API_URL}/api/v1/calibration/history?symbol=${encodeURIComponent(symbol)}&limit=20`),
        fetch(`${API_URL}/api/v1/calibration/candidates`),
        fetch(`${API_URL}/api/v1/calibration/active`)
      ]);
      if (latestRes.ok) {
        const latestData = await latestRes.json();
        setReport(latestData);
      } else {
        setReport(null);
      }
      if (historyRes.ok) {
        const historyData = await historyRes.json();
        setHistory(historyData.items || []);
      } else {
        setHistory([]);
      }
      if (candidateRes.ok) {
        const candidateData: CandidateResponse = await candidateRes.json();
        setCandidates(candidateData.candidates || []);
        if (candidateData.baseline) {
          setTuningParams(candidateData.baseline);
          setSelectedCandidateLabel("baseline");
        }
      } else {
        setCandidates([]);
      }
      if (activeRes.ok) {
        const activeData: ActiveParamsResponse = await activeRes.json();
        setActiveParams(activeData.applied_params || null);
        setActiveUpdatedAt(activeData.updated_at || "");
      } else {
        setActiveParams(null);
        setActiveUpdatedAt("");
      }
    } catch (e) {
      setError("加载校准数据失败");
    }
  }, [symbol]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const runCalibration = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(
        `${API_URL}/api/v1/calibration/run`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            symbol,
            window_days: windowDays,
            tuning_params: tuningParams
          })
        }
      );
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text);
      }
      const data = await res.json();
      setReport(data);
      await loadData();
    } catch (e: any) {
      setError(e?.message || "执行校准失败");
    } finally {
      setLoading(false);
    }
  };

  const applyTuningParams = async () => {
    setApplying(true);
    setApplyMessage("");
    setError("");
    try {
      const res = await fetch(`${API_URL}/api/v1/calibration/apply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tuning_params: tuningParams,
          description: "Applied from calibration page"
        })
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text);
      }
      const data = await res.json();
      setApplyMessage(`已应用参数并触发生效（${new Date().toLocaleTimeString()}）`);
      setActiveParams(data.applied_params || tuningParams);
      setActiveUpdatedAt(data.updated_at || "");
      await loadData();
    } catch (e: any) {
      setError(e?.message || "应用参数失败");
    } finally {
      setApplying(false);
    }
  };

  const rollbackToLatestCalibration = async () => {
    setRollingBack(true);
    setApplyMessage("");
    setError("");
    try {
      const res = await fetch(`${API_URL}/api/v1/calibration/rollback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol,
          description: "Rollback from calibration page"
        })
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text);
      }
      const data = await res.json();
      setApplyMessage(`已回滚到最近校准参数并生效（${new Date().toLocaleTimeString()}）`);
      setActiveParams(data.applied_params || null);
      setActiveUpdatedAt(data.updated_at || "");
      await loadData();
    } catch (e: any) {
      setError(e?.message || "回滚参数失败");
    } finally {
      setRollingBack(false);
    }
  };

  const confidenceRows = useMemo(() => {
    const before = report?.metrics?.before?.confidence_distribution || {};
    const after = report?.metrics?.after?.confidence_distribution || {};
    const keys = ["0-0.4", "0.4-0.6", "0.6-0.8", "0.8-1.0"];
    return keys.map((k) => ({
      bucket: k,
      before: Number(before[k] || 0),
      after: Number(after[k] || 0)
    }));
  }, [report]);

  return (
    <div className="flex h-screen bg-[#020617] text-slate-200 overflow-hidden font-sans">
      <div className="w-[80px] min-w-[80px] border-r border-slate-800 bg-slate-900 flex flex-col items-center py-5 z-20">
        <SideNav />
      </div>
      <main className="flex-1 p-8 overflow-y-auto">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold flex items-center gap-3 text-white">
            <Database size={28} className="text-blue-500" />
            数据源 - LLM 每日校准
          </h1>
          <div className="flex items-center gap-3">
            <select
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm"
            >
              <option value="ETH/USDT">ETH/USDT</option>
              <option value="BTC/USDT">BTC/USDT</option>
            </select>
            <select
              value={windowDays}
              onChange={(e) => setWindowDays(Number(e.target.value))}
              className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm"
            >
              <option value={7}>7天</option>
              <option value={14}>14天</option>
              <option value={21}>21天</option>
              <option value={30}>30天</option>
            </select>
            <button
              onClick={loadData}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-sm"
            >
              <RefreshCw size={16} />
              刷新
            </button>
            <button
              onClick={runCalibration}
              disabled={loading}
              className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold ${loading ? "bg-slate-700 text-slate-400" : "bg-blue-600 hover:bg-blue-700 text-white"}`}
            >
              <Play size={16} />
              {loading ? "执行中..." : "立即执行每日校准"}
            </button>
            <button
              onClick={applyTuningParams}
              disabled={applying}
              className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold ${applying ? "bg-slate-700 text-slate-400" : "bg-emerald-600 hover:bg-emerald-700 text-white"}`}
            >
              <Play size={16} />
              {applying ? "应用中..." : "一键应用参数并生效"}
            </button>
            <button
              onClick={rollbackToLatestCalibration}
              disabled={rollingBack}
              className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold ${rollingBack ? "bg-slate-700 text-slate-400" : "bg-amber-600 hover:bg-amber-700 text-white"}`}
            >
              <RefreshCw size={16} />
              {rollingBack ? "回滚中..." : "回滚到最近校准参数"}
            </button>
          </div>
        </div>

        <section className="bg-slate-900 rounded-2xl border border-slate-800 p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">参数控制与策略候选</h2>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
            <div>
              <label className="text-xs text-slate-400">候选策略</label>
              <select
                value={selectedCandidateLabel}
                onChange={(e) => {
                  const label = e.target.value;
                  setSelectedCandidateLabel(label);
                  const target = candidates.find((x) => x.label === label) || (label === "baseline" ? tuningParams : null);
                  if (target) {
                    const cloned = JSON.parse(JSON.stringify(target));
                    delete cloned.label;
                    setTuningParams(cloned);
                  }
                }}
                className="mt-1 w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm"
              >
                <option value="baseline">baseline</option>
                {candidates.map((c, idx) => (
                  <option key={`${c.label || "candidate"}-${idx}`} value={String(c.label || `candidate_${idx}`)}>
                    {String(c.label || `candidate_${idx}`)}
                  </option>
                ))}
              </select>
            </div>
            <NumberParamInput
              label={PARAM_LABELS.quality_confidence_floor}
              value={Number(tuningParams.quality_confidence_floor ?? 0.35)}
              onChange={(v) => setTuningParams((p) => ({ ...p, quality_confidence_floor: v }))}
            />
            <NumberParamInput
              label={PARAM_LABELS.min_magnitude}
              value={Number(tuningParams.min_magnitude ?? 0.35)}
              onChange={(v) => setTuningParams((p) => ({ ...p, min_magnitude: v }))}
            />
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
            <NumberParamInput
              label={PARAM_LABELS.major_event_confidence_floor}
              value={Number(tuningParams.major_event_confidence_floor ?? 0.55)}
              onChange={(v) => setTuningParams((p) => ({ ...p, major_event_confidence_floor: v }))}
            />
            <BoolParamInput
              label={PARAM_LABELS.exclude_insufficient_evidence}
              value={Boolean(tuningParams.exclude_insufficient_evidence)}
              onChange={(v) => setTuningParams((p) => ({ ...p, exclude_insufficient_evidence: v }))}
            />
            <BoolParamInput
              label={PARAM_LABELS.exclude_low_severity}
              value={Boolean(tuningParams.exclude_low_severity)}
              onChange={(v) => setTuningParams((p) => ({ ...p, exclude_low_severity: v }))}
            />
          </div>
          <div className="text-xs text-slate-400 mb-2">相关性权重</div>
          <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
            {Object.entries(tuningParams.relevance_weights || {}).map(([k, v]) => (
              <NumberParamInput
                key={k}
                label={PARAM_LABELS[k] || k}
                value={Number(v)}
                onChange={(nv) =>
                  setTuningParams((p) => ({
                    ...p,
                    relevance_weights: {
                      ...(p.relevance_weights || {}),
                      [k]: nv
                    }
                  }))
                }
              />
            ))}
          </div>
        </section>

        {error && <div className="mb-4 p-3 rounded-lg bg-red-950/60 border border-red-800 text-red-300">{error}</div>}
        {applyMessage && <div className="mb-4 p-3 rounded-lg bg-emerald-950/60 border border-emerald-800 text-emerald-300">{applyMessage}</div>}

        <section className="bg-slate-900 rounded-2xl border border-slate-800 p-6 mb-6">
          <h2 className="text-lg font-semibold mb-3">当前生效参数</h2>
          <div className="text-xs text-slate-400 mb-2">
            更新时间: {activeUpdatedAt ? new Date(activeUpdatedAt).toLocaleString() : "暂无"}
          </div>
          <ParamSummaryList params={activeParams || {}} />
          <pre className="text-xs bg-slate-950 border border-slate-800 rounded-lg p-3 overflow-x-auto text-slate-300">
            {JSON.stringify(activeParams || {}, null, 2)}
          </pre>
        </section>

        <section className="bg-slate-900 rounded-2xl border border-slate-800 p-6 mb-6">
          <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
            <BarChart3 size={18} className="text-blue-400" />
            思路与执行过程
          </h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div>
              <h3 className="text-sm font-semibold text-slate-300 mb-2">校准思路</h3>
              <ul className="space-y-2 text-sm text-slate-400">
                {(report?.methodology || []).map((item, idx) => (
                  <li key={idx} className="bg-slate-950/60 border border-slate-800 rounded-lg px-3 py-2">{item}</li>
                ))}
              </ul>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-slate-300 mb-2">执行过程</h3>
              <ul className="space-y-2 text-sm text-slate-400">
                {(report?.execution_process || []).map((item, idx) => (
                  <li key={idx} className="bg-slate-950/60 border border-slate-800 rounded-lg px-3 py-2">{item}</li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        <section className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
          <MetricCard title="1H 命中率 Δ" value={formatDelta(report?.metrics?.delta?.hit_rate_1h)} />
          <MetricCard title="4H 命中率 Δ" value={formatDelta(report?.metrics?.delta?.hit_rate_4h)} />
          <MetricCard title="总体冲突率 Δ" value={formatDelta(report?.metrics?.delta?.overall_conflict_ratio)} />
          <MetricCard title="小时冲突率 Δ" value={formatDelta(report?.metrics?.delta?.hour_conflict_rate)} />
        </section>

        <section className="bg-slate-900 rounded-2xl border border-slate-800 p-6 mb-6">
          <h2 className="text-lg font-semibold mb-3">校准判定</h2>
          <div className={`inline-flex px-3 py-1 rounded text-sm font-semibold ${report?.metrics?.decision?.passed ? "bg-emerald-900/40 text-emerald-300 border border-emerald-700" : "bg-amber-900/40 text-amber-300 border border-amber-700"}`}>
            {report?.metrics?.decision?.passed ? "参数通过" : "参数未通过"}
          </div>
          <ul className="mt-3 space-y-2 text-sm text-slate-400">
            {(report?.metrics?.decision?.rules || []).map((rule, idx) => (
              <li key={idx} className="bg-slate-950/60 border border-slate-800 rounded-lg px-3 py-2">
                {rule}
              </li>
            ))}
          </ul>
        </section>

        <section className="bg-slate-900 rounded-2xl border border-slate-800 p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">本次参数快照</h2>
          <ParamSummaryList params={(report?.metrics?.parameters || tuningParams) as Record<string, any>} />
          <pre className="text-xs bg-slate-950 border border-slate-800 rounded-lg p-3 overflow-x-auto text-slate-300">
            {JSON.stringify(report?.metrics?.parameters || tuningParams, null, 2)}
          </pre>
        </section>

        <section className="bg-slate-900 rounded-2xl border border-slate-800 p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">结果对比</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-slate-400 border-b border-slate-800">
                  <th className="text-left py-2">指标</th>
                  <th className="text-right py-2">改造前</th>
                  <th className="text-right py-2">改造后</th>
                </tr>
              </thead>
              <tbody>
                <MetricRow label="样本数" before={report?.metrics?.before?.selected_samples} after={report?.metrics?.after?.selected_samples} />
                <MetricRow label="1H命中率" before={report?.metrics?.before?.hit_rate_1h} after={report?.metrics?.after?.hit_rate_1h} />
                <MetricRow label="4H命中率" before={report?.metrics?.before?.hit_rate_4h} after={report?.metrics?.after?.hit_rate_4h} />
                <MetricRow label="总体冲突率" before={report?.metrics?.before?.overall_conflict_ratio} after={report?.metrics?.after?.overall_conflict_ratio} />
                <MetricRow label="小时冲突率" before={report?.metrics?.before?.hour_conflict_rate} after={report?.metrics?.after?.hour_conflict_rate} />
              </tbody>
            </table>
          </div>
        </section>

        <section className="bg-slate-900 rounded-2xl border border-slate-800 p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">置信度分布</h2>
          <div className="space-y-3">
            {confidenceRows.map((row) => (
              <div key={row.bucket} className="grid grid-cols-[90px_1fr_70px_1fr_70px] items-center gap-3 text-sm">
                <span className="text-slate-300">{row.bucket}</span>
                <div className="w-full h-2 bg-slate-800 rounded-full">
                  <div className="h-2 bg-violet-500 rounded-full" style={{ width: `${Math.min(100, row.before)}%` }} />
                </div>
                <span className="text-right text-violet-300">{row.before}</span>
                <div className="w-full h-2 bg-slate-800 rounded-full">
                  <div className="h-2 bg-emerald-500 rounded-full" style={{ width: `${Math.min(100, row.after)}%` }} />
                </div>
                <span className="text-right text-emerald-300">{row.after}</span>
              </div>
            ))}
          </div>
        </section>

        <section className="bg-slate-900 rounded-2xl border border-slate-800 p-6">
          <h2 className="text-lg font-semibold mb-4">历史执行记录</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-slate-400 border-b border-slate-800">
                  <th className="text-left py-2">日期</th>
                  <th className="text-right py-2">窗口</th>
                  <th className="text-right py-2">1H命中率Δ</th>
                  <th className="text-right py-2">4H命中率Δ</th>
                  <th className="text-right py-2">冲突率Δ</th>
                </tr>
              </thead>
              <tbody>
                {history.map((item, idx) => (
                  <tr key={`${item.run_date}-${idx}`} className="border-b border-slate-850">
                    <td className="py-2 text-slate-300">{item.run_date}</td>
                    <td className="py-2 text-right text-slate-300">{item.window_days}d</td>
                    <td className="py-2 text-right">{formatDelta(item.delta?.hit_rate_1h)}</td>
                    <td className="py-2 text-right">{formatDelta(item.delta?.hit_rate_4h)}</td>
                    <td className="py-2 text-right">{formatDelta(item.delta?.overall_conflict_ratio)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </div>
  );
}

const MetricCard = ({ title, value }: { title: string; value: string }) => (
  <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
    <div className="text-xs text-slate-400 mb-2">{title}</div>
    <div className="text-xl font-semibold text-white">{value}</div>
  </div>
);

const NumberParamInput = ({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) => (
  <div>
    <label className="text-xs text-slate-400">{label}</label>
    <input
      type="number"
      step="0.01"
      value={Number.isFinite(value) ? value : 0}
      onChange={(e) => onChange(Number(e.target.value))}
      className="mt-1 w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm"
    />
  </div>
);

const BoolParamInput = ({ label, value, onChange }: { label: string; value: boolean; onChange: (v: boolean) => void }) => (
  <div>
    <label className="text-xs text-slate-400">{label}</label>
    <select
      value={value ? "true" : "false"}
      onChange={(e) => onChange(e.target.value === "true")}
      className="mt-1 w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm"
    >
      <option value="true">true</option>
      <option value="false">false</option>
    </select>
  </div>
);

const ParamSummaryList = ({ params }: { params: Record<string, any> }) => {
  const rows: Array<{ key: string; label: string; value: any }> = [];
  for (const [k, v] of Object.entries(params || {})) {
    if (k === "relevance_weights" && typeof v === "object" && v !== null) {
      for (const [rk, rv] of Object.entries(v)) {
        rows.push({ key: `relevance_weights.${rk}`, label: PARAM_LABELS[rk] || rk, value: rv });
      }
      continue;
    }
    rows.push({ key: k, label: PARAM_LABELS[k] || k, value: v });
  }
  return (
    <div className="mb-3 grid grid-cols-1 md:grid-cols-2 gap-2">
      {rows.map((row) => (
        <div key={row.key} className="text-xs bg-slate-950/70 border border-slate-800 rounded px-2 py-1 flex justify-between gap-2">
          <span className="text-slate-400">{row.label}</span>
          <span className="text-slate-200">{String(row.value)}</span>
        </div>
      ))}
    </div>
  );
};

const MetricRow = ({ label, before, after }: { label: string; before: any; after: any }) => (
  <tr className="border-b border-slate-850">
    <td className="py-2 text-slate-300">{label}</td>
    <td className="py-2 text-right text-violet-300">{formatValue(before)}</td>
    <td className="py-2 text-right text-emerald-300">{formatValue(after)}</td>
  </tr>
);

const formatValue = (value: any) => {
  if (value === null || value === undefined) return "-";
  if (typeof value === "number") return value.toFixed(4);
  return String(value);
};

const formatDelta = (value: any) => {
  if (value === null || value === undefined) return "-";
  const num = Number(value);
  if (Number.isNaN(num)) return "-";
  if (num > 0) return `+${num.toFixed(4)}`;
  return num.toFixed(4);
};
