import { useState } from 'react';
import { useStore } from '../store/store-context';
import type { InspectionItem } from '../store/types';
import Modal from '../components/Modal';

const RESULT_META: Record<InspectionItem['result'], { label: string; tag: string }> = {
  pass: { label: '通过', tag: 'success' },
  warn: { label: '告警', tag: 'warning' },
  fail: { label: '失败', tag: 'danger' },
};

const AUTO_TASKS = [
  { name: '全域健康巡检', cron: '每日 06:30', last: '2026-06-25 06:30', status: '正常', desc: '节点 / 容器 / 实例 / 模型全量健康检查' },
  { name: 'GPU 资源水位巡检', cron: '每小时', last: '2026-06-25 10:00', status: '正常', desc: 'GPU/显存利用率采集与超阈值预警' },
  { name: '异常容器自愈', cron: '事件触发', last: '2026-06-25 08:48', status: '已触发', desc: '检测到异常容器自动迁移至健康节点' },
  { name: '模型探针检测', cron: '每 5 分钟', last: '2026-06-25 10:05', status: '告警', desc: 'Qwen-Office 探针超时率升高' },
  { name: '证书到期巡检', cron: '每日 02:00', last: '2026-06-25 02:00', status: '正常', desc: 'TLS 证书有效期检查与自动续期' },
  { name: '配置与数据备份', cron: '每日 01:00', last: '2026-06-25 01:00', status: '正常', desc: '全量配置与数据备份' },
];

export default function OpsPage() {
  const { inspection, agents, update, addOpLog, toast } = useStore();
  const [running, setRunning] = useState(false);
  const [detail, setDetail] = useState<InspectionItem | null>(null);
  const [cat, setCat] = useState('全部');

  const cats = ['全部', ...Array.from(new Set(inspection.items.map((i) => i.category)))];
  const items = inspection.items.filter((i) => cat === '全部' || i.category === cat);

  // 根据巡检项列表重新统计 通过/告警/失败 数量
  function recount(list: InspectionItem[]) {
    return {
      total: list.length,
      pass: list.filter((i) => i.result === 'pass').length,
      warn: list.filter((i) => i.result === 'warn').length,
      fail: list.filter((i) => i.result === 'fail').length,
    };
  }

  // 一键处置：将巡检项标记为通过，并尽量同步关联实体状态。
  function handleItem(it: InspectionItem) {
    update((d) => {
      const nextItems = d.inspection.items.map((x) => (x.id === it.id ? { ...x, result: 'pass' as const, detail: `${x.detail}（已处置）` } : x));
      return {
        inspection: { ...d.inspection, items: nextItems, ...recount(nextItems) },
        agents:
          it.category === '实例状态' ? d.agents.map((agent) => (agent.status === 'abnormal' ? { ...agent, status: 'running', qps: Math.max(agent.qps, 10) } : agent)) : d.agents,
        channels: it.category === '渠道' ? d.channels.map((channel) => (channel.status === 'error' ? { ...channel, status: 'connected' } : channel)) : d.channels,
        models:
          it.category === '模型服务'
            ? d.models.map((model) =>
                model.status !== 'available' || model.errorRate > 1
                  ? { ...model, status: 'available', errorRate: Math.min(model.errorRate, 0.8), avgLatency: Math.min(model.avgLatency, 1800) }
                  : model,
              )
            : d.models,
        alerts: ['实例状态', '渠道', '模型服务'].includes(it.category)
          ? d.alerts.map((alert) => (alert.status !== 'resolved' ? { ...alert, status: 'resolved' } : alert))
          : d.alerts,
      };
    });
    addOpLog({ operator: 'admin', module: '运维管理', action: '处置巡检项', target: it.name, result: 'success', ip: '10.1.28.16', detail: it.suggestion });
    toast(`已对「${it.name}」执行处置`, 'success');
    if (detail?.id === it.id) setDetail(null);
  }

  function runInspection() {
    setRunning(true);
    addOpLog({ operator: 'admin', module: '运维管理', action: '执行巡检', target: '全域（手动触发）', result: 'success', ip: '10.1.28.16', detail: '运维自动化一键巡检' });
    toast('巡检任务已下发，正在执行…', 'info');
    setTimeout(() => {
      const now = new Date();
      const ts = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;
      update((d) => {
        const abnormalAgents = d.agents.filter((agent) => agent.status === 'abnormal').length;
        const errorChannels = d.channels.filter((channel) => channel.status === 'error').length;
        const unhealthyModels = d.models.filter((model) => model.status !== 'available' || model.errorRate > 1 || model.avgLatency > 3000).length;

        const nextItems = d.inspection.items.map((it) => {
          if (it.category === '实例状态') {
            return {
              ...it,
              result: abnormalAgents > 0 ? ('warn' as const) : ('pass' as const),
              detail: abnormalAgents > 0 ? `${abnormalAgents} 个实例处于异常状态` : '全部实例状态正常',
            };
          }
          if (it.category === '渠道') {
            return {
              ...it,
              result: errorChannels > 0 ? ('warn' as const) : ('pass' as const),
              detail:
                errorChannels > 0
                  ? `${d.channels.length - errorChannels}/${d.channels.length} 渠道在线，${errorChannels} 个异常`
                  : `${d.channels.length}/${d.channels.length} 渠道在线`,
            };
          }
          if (it.category === '模型服务') {
            return {
              ...it,
              result: unhealthyModels > 0 ? ('fail' as const) : ('pass' as const),
              detail: unhealthyModels > 0 ? `${unhealthyModels} 个模型处于维护、离线或指标异常` : '全部模型探针正常',
            };
          }
          return it;
        });
        return {
          inspection: {
            ...d.inspection,
            ts,
            scope: `全域 · ${d.agents.length} 个实例`,
            items: nextItems,
            ...recount(nextItems),
          },
        };
      });
      setRunning(false);
      toast('巡检完成，生成最新报告', 'success');
    }, 2200);
  }

  const inspectedAgentCount = agents.length;
  const passRate = inspection.total ? Math.round((inspection.pass / inspection.total) * 100) : 0;

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  function exportReport() {
    const resultLabel: Record<InspectionItem['result'], string> = { pass: '通过', warn: '告警', fail: '失败' };
    const resultColor: Record<InspectionItem['result'], string> = { pass: '#22a65b', warn: '#c17a00', fail: '#f05252' };
    const rows = inspection.items
      .map(
        (it, i) => `<tr>
          <td>${i + 1}</td>
          <td>${it.category}</td>
          <td>${it.name}</td>
          <td><span style="color:${resultColor[it.result]};font-weight:700">${resultLabel[it.result]}</span></td>
          <td>${it.detail}</td>
          <td>${it.suggestion}</td>
        </tr>`,
      )
      .join('');
    const tasks = AUTO_TASKS.map((t) => `<tr><td>${t.name}</td><td>${t.cron}</td><td>${t.last}</td><td>${t.status}</td><td>${t.desc}</td></tr>`).join('');
    const html = `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
      <title>${inspection.id} 全域巡检报告</title>
      <style>
        body{font-family:"Microsoft YaHei","PingFang SC",sans-serif;color:#1f2937;margin:40px;}
        h1{font-size:24px;margin:0 0 4px;} .sub{color:#6b7280;margin:0 0 24px;}
        .meta{display:flex;flex-wrap:wrap;gap:24px;margin-bottom:20px;font-size:14px;}
        .meta div span{color:#6b7280;} .meta div strong{margin-left:6px;}
        .kpi{display:flex;gap:16px;margin:20px 0;}
        .kpi div{flex:1;border:1px solid #e4eaf4;border-radius:12px;padding:14px;text-align:center;}
        .kpi strong{display:block;font-size:26px;margin-top:6px;}
        h2{font-size:17px;border-left:4px solid #246bff;padding-left:10px;margin:26px 0 12px;}
        table{width:100%;border-collapse:collapse;font-size:13px;}
        th,td{border:1px solid #e4eaf4;padding:8px 10px;text-align:left;}
        th{background:#f8fbff;color:#64748b;}
        .foot{margin-top:30px;color:#94a3b8;font-size:12px;border-top:1px solid #e4eaf4;padding-top:12px;}
        @media print{body{margin:16mm;} .noprint{display:none;}}
      </style></head><body>
      <h1>讯飞 AstronClaw 全域巡检报告</h1>
      <p class="sub">报告编号：${inspection.id} · 巡检范围：${inspection.scope}</p>
      <div class="meta">
        <div><span>巡检时间</span><strong>${inspection.ts}</strong></div>
        <div><span>巡检模式</span><strong>自动化 + 手动</strong></div>
        <div><span>整体通过率</span><strong>${passRate}%</strong></div>
      </div>
      <div class="kpi">
        <div><span>覆盖实例数</span><strong>${inspectedAgentCount}</strong></div>
        <div><span>巡检项总数</span><strong>${inspection.total}</strong></div>
        <div><span style="color:#22a65b">通过</span><strong style="color:#22a65b">${inspection.pass}</strong></div>
        <div><span style="color:#c17a00">告警</span><strong style="color:#c17a00">${inspection.warn}</strong></div>
        <div><span style="color:#f05252">失败</span><strong style="color:#f05252">${inspection.fail}</strong></div>
      </div>
      <h2>巡检结果明细</h2>
      <table><thead><tr><th>#</th><th>类别</th><th>巡检项</th><th>结果</th><th>检测详情</th><th>处置建议</th></tr></thead><tbody>${rows}</tbody></table>
      <h2>自动化运维任务</h2>
      <table><thead><tr><th>任务名称</th><th>调度</th><th>最近执行</th><th>状态</th><th>说明</th></tr></thead><tbody>${tasks}</tbody></table>
      <p class="foot">本报告由 AstronClaw 私有化智能体管理平台自动生成 · 用浏览器打开后可打印或另存为 PDF 归档。</p>
      </body></html>`;
    const blob = new Blob(['﻿' + html], { type: 'text/html;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    const d = new Date();
    const p = (n: number) => String(n).padStart(2, '0');
    a.href = url;
    a.download = `巡检报告_${inspection.id}_${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}.html`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    addOpLog({ operator: 'admin', module: '运维管理', action: '导出报告', target: inspection.id, result: 'success', ip: '10.1.28.16', detail: '导出全域巡检报告（HTML）' });
    toast('巡检报告已下载', 'success');
  }

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>运维自动化</h1>
          <p>面向私有化集群的自动化巡检、自愈与运维编排。下方展示最新一次全域巡检结果与自动化任务运行情况。</p>
        </div>
        <div className="head-actions">
          <button className="ghost-btn" onClick={exportReport}>
            导出报告
          </button>
          <button className="primary-btn" disabled={running} onClick={runInspection}>
            {running ? '巡检执行中…' : '一键巡检'}
          </button>
        </div>
      </div>

      <div className="six-cols stats-grid">
        <div className="stat-card accent">
          <span>覆盖实例数</span>
          <strong>{inspectedAgentCount}</strong>
          <em>{inspection.scope}</em>
        </div>
        <div className="stat-card">
          <span>巡检项总数</span>
          <strong>{inspection.total}</strong>
          <em>检查规则数量</em>
        </div>
        <div className="stat-card">
          <span>通过</span>
          <strong style={{ color: 'var(--success)' }}>{inspection.pass}</strong>
          <em>通过率 {passRate}%</em>
        </div>
        <div className="stat-card">
          <span>告警</span>
          <strong style={{ color: '#c17a00' }}>{inspection.warn}</strong>
          <em>需关注</em>
        </div>
        <div className="stat-card">
          <span>失败</span>
          <strong style={{ color: 'var(--danger)' }}>{inspection.fail}</strong>
          <em>需处置</em>
        </div>
        <div className="stat-card">
          <span>巡检时间</span>
          <strong style={{ fontSize: 18 }}>{inspection.ts.slice(11)}</strong>
          <em>{inspection.ts.slice(0, 10)}</em>
        </div>
      </div>

      <div className="split-layout" style={{ marginBottom: 20 }}>
        <div className="summary-card" style={{ flex: '0 0 280px' }}>
          <h3>巡检健康度</h3>
          <div className="ring-grid">
            <div className="ring-item">
              <div className={`ring ${passRate >= 80 ? 'success-ring' : 'warning-ring'}`}>{passRate}%</div>
              <span>整体通过率</span>
            </div>
          </div>
          <div className="summary-metrics">
            <div>
              <span>报告编号</span>
              <strong>{inspection.id}</strong>
            </div>
            <div>
              <span>巡检范围</span>
              <strong>{inspection.scope}</strong>
            </div>
            <div>
              <span>覆盖实例</span>
              <strong>{inspectedAgentCount} 个</strong>
            </div>
            <div>
              <span>巡检模式</span>
              <strong>自动化 + 手动</strong>
            </div>
          </div>
        </div>
        <div className="chart-card">
          <div className="card-topline">
            <h3>自动化运维任务</h3>
            <span>调度与自愈</span>
          </div>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>任务名称</th>
                  <th>调度</th>
                  <th>最近执行</th>
                  <th>状态</th>
                </tr>
              </thead>
              <tbody>
                {AUTO_TASKS.map((t) => (
                  <tr key={t.name}>
                    <td>
                      <strong>{t.name}</strong>
                      <div className="subtle">{t.desc}</div>
                    </td>
                    <td>{t.cron}</td>
                    <td>{t.last}</td>
                    <td>
                      <span className={`status-tag ${t.status === '正常' ? 'success' : t.status === '告警' ? 'warning' : 'info'}`}>{t.status}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className="section-title">巡检结果明细</div>
      <div className="toolbar-card">
        <div className="chip-group">
          {cats.map((c) => (
            <button key={c} className={`chip${cat === c ? ' active' : ''}`} onClick={() => setCat(c)}>
              {c}
            </button>
          ))}
        </div>
        <div className="subtle">共 {items.length} 项</div>
      </div>

      <div className="card-grid three-cols">
        {items.map((it) => (
          <div className="form-card" key={it.id}>
            <div className="card-topline">
              <h3 style={{ fontSize: 17 }}>{it.name}</h3>
              <span className={`status-tag ${RESULT_META[it.result].tag}`}>{RESULT_META[it.result].label}</span>
            </div>
            <p className="meta-tags" style={{ marginBottom: 12 }}>
              <span>{it.category}</span>
            </p>
            <p className="subtle" style={{ marginTop: 0 }}>
              {it.detail}
            </p>
            {it.result !== 'pass' && (
              <div className={it.result === 'fail' ? 'warning-box' : 'warning-box'} style={{ marginTop: 12 }}>
                建议：{it.suggestion}
              </div>
            )}
            <div className="card-actions">
              <button className="ghost-btn small" onClick={() => setDetail(it)}>
                查看详情
              </button>
              {it.result !== 'pass' && (
                <button className="primary-btn small" onClick={() => handleItem(it)}>
                  一键处置
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      <Modal
        open={!!detail}
        title={detail ? `巡检详情 · ${detail.name}` : ''}
        onClose={() => setDetail(null)}
        footer={
          <>
            <button className="ghost-btn" onClick={() => setDetail(null)}>
              关闭
            </button>
            {detail && detail.result !== 'pass' && (
              <button className="primary-btn" onClick={() => handleItem(detail)}>
                一键处置
              </button>
            )}
          </>
        }
      >
        {detail && (
          <div className="summary-metrics">
            <div>
              <span>巡检类别</span>
              <strong>{detail.category}</strong>
            </div>
            <div>
              <span>巡检结果</span>
              <strong className={`status-tag ${RESULT_META[detail.result].tag}`}>{RESULT_META[detail.result].label}</strong>
            </div>
            <div>
              <span>检测详情</span>
              <strong style={{ maxWidth: 320 }}>{detail.detail}</strong>
            </div>
            <div>
              <span>处置建议</span>
              <strong style={{ maxWidth: 320 }}>{detail.suggestion}</strong>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
