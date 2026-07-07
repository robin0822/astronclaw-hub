import { useEffect, useState, useMemo } from 'react';
import { useStore } from '../store/store-context';
import type { Alert } from '../store/types';
import { useBars } from '../components/ui';
import Modal from '../components/Modal';

type Tab = 'overview' | 'kpi' | 'alerts';

const ERROR_CODES = [
  { code: 'E2010', category: '节点健康', level: 'critical', desc: '节点心跳异常/失联', action: '触发容器迁移与节点隔离' },
  { code: 'E5021', category: '模型调用', level: 'critical', desc: '主备模型均不可用', action: '排队降级，通知模型平台组' },
  { code: 'E6001', category: '存储', level: 'critical', desc: '持久化存储写入失败', action: '切换备用存储卷' },
  { code: 'W3304', category: '资源容量', level: 'warning', desc: 'GPU/CPU 利用率超阈值', action: '扩容或迁移高负载容器' },
  { code: 'W4102', category: '接口超时', level: 'warning', desc: '上游接口响应延时升高', action: '启用缓存/切换备用链路' },
  { code: 'W4210', category: '限流', level: 'warning', desc: '触发并发限流', action: '排队或提升配额' },
  { code: 'I1001', category: '组织同步', level: 'info', desc: '定时同步完成', action: '无需处理' },
];

const LEVEL_META: Record<Alert['level'], { label: string; tag: string }> = {
  critical: { label: '严重', tag: 'danger' },
  warning: { label: '一般', tag: 'warning' },
  info: { label: '提示', tag: 'info' },
};
const ALERT_STATUS: Record<Alert['status'], { label: string; tag: string }> = {
  pending: { label: '待处理', tag: 'danger' },
  claimed: { label: '已认领', tag: 'warning' },
  processing: { label: '处理中', tag: 'warning' },
  resolved: { label: '已闭环', tag: 'success' },
};

export default function MonitoringPage() {
  const [tab, setTab] = useState<Tab>('overview');
  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>监控管理</h1>
          <p>全域运行状态全景可视、关键性能指标实时采集、分级预警快速闭环处置，支撑异常快速定位与处理。</p>
        </div>
      </div>
      <div className="tab-row">
        <div className="tab-group">
          <button className={`tab${tab === 'overview' ? ' active' : ''}`} onClick={() => setTab('overview')}>
            全域运行状态全景
          </button>
          <button className={`tab${tab === 'kpi' ? ' active' : ''}`} onClick={() => setTab('kpi')}>
            关键性能指标
          </button>
          <button className={`tab${tab === 'alerts' ? ' active' : ''}`} onClick={() => setTab('alerts')}>
            分级预警闭环
          </button>
        </div>
      </div>
      {tab === 'overview' && <Overview />}
      {tab === 'kpi' && <Kpi />}
      {tab === 'alerts' && <Alerts />}
    </div>
  );
}

/* ---------- 3.1 全域运行状态全景可视 ---------- */
function Overview() {
  const { agents } = useStore();
  const [tick, setTick] = useState(0);
  const [trendTab, setTrendTab] = useState<'cpu' | 'qps' | 'latency'>('cpu');

  useEffect(() => {
    const t = setInterval(() => setTick((v) => v + 1), 5000);
    return () => clearInterval(t);
  }, []);

  // 先在顶层调用 useBars hook
  const baseBars = useBars(17, 8); // 固定8个数据点

  // 生成真实的趋势数据 - 根据不同指标生成不同范围的数据
  const bars = useMemo(() => {
    return baseBars.map((h, i) => {
      // 添加时间趋势：最右边是最新数据，随tick变化
      const timeFactor = Math.sin((tick + i) / 3) * 10;

      if (trendTab === 'cpu') {
        // CPU: 50%-85% 范围
        return Math.max(50, Math.min(85, h * 0.35 + 50 + timeFactor));
      }
      if (trendTab === 'qps') {
        // QPS: 150-450 req/s 范围，映射到百分比
        const qps = h * 3 + 150 + timeFactor * 2;
        return (qps / 500) * 100; // 500 是 Y 轴最大值
      }
      // latency: 800-1800ms 范围，映射到百分比
      const latency = h * 10 + 800 + timeFactor * 5;
      return (latency / 2000) * 100; // 2000ms 是 Y 轴最大值
    });
  }, [baseBars, tick, trendTab]);

  // 当前值：基于最新的数据点（最右边）
  const currentCpu = Math.round(bars[bars.length - 1] * 0.85); // CPU 百分比
  const currentQps = Math.round(bars[bars.length - 1] * 5); // QPS 实际值
  const currentLatency = Math.round(bars[bars.length - 1] * 20); // 延迟 ms

  const runningCount = agents.filter((a) => a.status === 'running').length;

  return (
    <>
      <div className="six-cols stats-grid">
        <div className="stat-card accent">
          <span>节点在线</span>
          <strong>29</strong>
          <em>共 32 节点</em>
        </div>
        <div className="stat-card">
          <span>运行智能体</span>
          <strong>{runningCount}</strong>
          <em>共 {agents.length} 个</em>
        </div>
        <div className="stat-card">
          <span>异常智能体</span>
          <strong>{agents.filter((a) => a.status === 'abnormal').length}</strong>
          <em>需立即处置</em>
        </div>
        <div className="stat-card">
          <span>存储余量</span>
          <strong>{(2.4 - (tick % 3) * 0.1).toFixed(1)}TB</strong>
          <em>总容量 8TB</em>
        </div>
        <div className="stat-card">
          <span>{trendTab === 'cpu' ? 'CPU 使用率' : trendTab === 'qps' ? '当前 QPS' : '平均时延'}</span>
          <strong>{trendTab === 'cpu' ? `${currentCpu}%` : trendTab === 'qps' ? currentQps : `${currentLatency}ms`}</strong>
          <em>{trendTab === 'cpu' ? '集群平均' : trendTab === 'qps' ? 'req/s' : '响应时间'}</em>
        </div>
        <div className="stat-card">
          <span>网络延迟</span>
          <strong>{12 + (tick % 4) * 2}ms</strong>
          <em>平均 RTT</em>
        </div>
      </div>

      <div className="dashboard-grid">
        <div className="chart-card">
          <div className="card-topline">
            <h3>近 24 小时性能趋势</h3>
            <div className="chip-group">
              <button className={`chip small${trendTab === 'cpu' ? ' active' : ''}`} onClick={() => setTrendTab('cpu')}>
                CPU
              </button>
              <button className={`chip small${trendTab === 'qps' ? ' active' : ''}`} onClick={() => setTrendTab('qps')}>
                QPS
              </button>
              <button className={`chip small${trendTab === 'latency' ? ' active' : ''}`} onClick={() => setTrendTab('latency')}>
                时延
              </button>
            </div>
          </div>
          <div className="chart-with-axis">
            <div className="simple-yaxis">
              <span>{trendTab === 'cpu' ? '100%' : trendTab === 'qps' ? '500' : '2000ms'}</span>
              <span>{trendTab === 'cpu' ? '75%' : trendTab === 'qps' ? '375' : '1500ms'}</span>
              <span>{trendTab === 'cpu' ? '50%' : trendTab === 'qps' ? '250' : '1000ms'}</span>
              <span>{trendTab === 'cpu' ? '25%' : trendTab === 'qps' ? '125' : '500ms'}</span>
              <span>{trendTab === 'cpu' ? '0%' : trendTab === 'qps' ? '0' : '0ms'}</span>
            </div>
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div className="fake-chart line-chart">
                {bars.map((h, i) => (
                  <i key={i} style={{ left: `${6 + i * 11.5}%`, height: `${h}%` }} />
                ))}
              </div>
              <div className="simple-xaxis">
                <span>00:00</span>
                <span>06:00</span>
                <span>12:00</span>
                <span>18:00</span>
                <span>24:00</span>
              </div>
            </div>
          </div>
        </div>
        <div className="chart-card">
          <div className="card-topline">
            <h3>节点状态分布</h3>
            <span>在线/维护/异常</span>
          </div>
          <div className="ring-grid">
            <div className="ring-item">
              <div className="ring success-ring">29</div>
              <span>在线</span>
            </div>
            <div className="ring-item">
              <div className="ring warning-ring">2</div>
              <span>维护中</span>
            </div>
            <div className="ring-item">
              <div className="ring danger-ring">1</div>
              <span>异常</span>
            </div>
          </div>
        </div>
        <div className="chart-card">
          <div className="card-topline">
            <h3>Top 异常对象</h3>
            <span>按影响面</span>
          </div>
          <ul className="rank-list">
            <li>
              <strong>财务核算智能体</strong>
              <span>E5021 模型回退失败 · 影响 5 用户</span>
            </li>
            <li>
              <strong>node-bj-05</strong>
              <span>W3304 GPU 过载 · 影响 11 容器</span>
            </li>
            <li>
              <strong>Qwen-Office</strong>
              <span>W4102 接口超时升高 · 办公助理</span>
            </li>
          </ul>
        </div>
      </div>

      <div className="section-title">区域资源水位</div>
      <div className="three-cols card-grid">
        {[
          {
            name: '华东主集群',
            cpu: 62,
            cpuUsed: 1860,
            cpuTotal: 3000,
            mem: 58,
            memUsed: 464,
            memTotal: 800,
            gpu: 79,
            gpuUsed: 95,
            gpuTotal: 120,
            storage: 68,
            storageUsed: 5.4,
            storageTotal: 8,
            nodes: '18 节点',
          },
          {
            name: '华北节点',
            cpu: 41,
            cpuUsed: 615,
            cpuTotal: 1500,
            mem: 47,
            memUsed: 188,
            memTotal: 400,
            gpu: 53,
            gpuUsed: 32,
            gpuTotal: 60,
            storage: 52,
            storageUsed: 2.1,
            storageTotal: 4,
            nodes: '9 节点',
          },
          {
            name: '异地灾备',
            cpu: 12,
            cpuUsed: 96,
            cpuTotal: 800,
            mem: 18,
            memUsed: 36,
            memTotal: 200,
            gpu: 5,
            gpuUsed: 2,
            gpuTotal: 40,
            storage: 28,
            storageUsed: 0.7,
            storageTotal: 2.5,
            nodes: '5 节点',
          },
        ].map((r) => (
          <div className="form-card" key={r.name}>
            <div className="card-topline">
              <h3>{r.name}</h3>
              <span className="subtle">{r.nodes}</span>
            </div>
            {[
              ['CPU', r.cpu, `${r.cpuUsed} / ${r.cpuTotal} 核`],
              ['内存', r.mem, `${r.memUsed} / ${r.memTotal} GB`],
              ['GPU', r.gpu, `${r.gpuUsed} / ${r.gpuTotal} 卡`],
              ['存储', r.storage, `${r.storageUsed} / ${r.storageTotal} TB`],
            ].map(([k, v, detail]) => (
              <div key={k as string}>
                <div className="metric-pair">
                  <span>{k}</span>
                  <span>
                    {v}% · {detail}
                  </span>
                </div>
                <div className={`progress${(v as number) > 75 ? ' orange' : ''}`}>
                  <i style={{ width: `${v}%` }} />
                </div>
              </div>
            ))}
          </div>
        ))}
      </div>
    </>
  );
}

/* ---------- 3.2 关键性能指标实时采集 ---------- */
function Kpi() {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setTick((v) => v + 1), 5000);
    return () => clearInterval(t);
  }, []);
  const j = (base: number, amp: number) => base + Math.round(Math.sin(tick / 2) * amp + (tick % 3) * (amp / 3));

  const kpis = [
    { name: 'API 请求量 (req/min)', val: j(4200, 300), trend: '+8%' },
    { name: '平均响应时延 (ms)', val: j(1820, 120), trend: '稳定' },
    { name: 'P99 时延 (ms)', val: j(4600, 400), trend: '-3%' },
    { name: 'Token 吞吐 (k/s)', val: j(86, 12), trend: '+5%' },
    { name: '错误率 (%)', val: Number((0.6 + (tick % 4) * 0.1).toFixed(2)), trend: '正常' },
    { name: '会话并发数', val: j(684, 60), trend: '峰值' },
    { name: 'GPU 利用率 (%)', val: j(71, 8), trend: '偏高' },
    { name: '缓存命中率 (%)', val: j(92, 3), trend: '良好' },
  ];

  return (
    <>
      <div className="info-banner">指标每 5 秒采集刷新一次（实时模拟）。采集维度覆盖网关层、模型层、容器层与会话层。</div>
      <div className="four-cols stats-grid">
        {kpis.map((k) => (
          <div className="stat-card" key={k.name}>
            <span>{k.name}</span>
            <strong>{k.val}</strong>
            <em>{k.trend}</em>
          </div>
        ))}
      </div>
      <div className="split-layout">
        <div className="chart-card">
          <div className="card-topline">
            <h3>请求量实时曲线</h3>
            <span>每 5 秒采样</span>
          </div>
          <div className="chart-with-axis">
            <div className="simple-yaxis">
              <span>5000</span>
              <span>3750</span>
              <span>2500</span>
              <span>1250</span>
              <span>0</span>
            </div>
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div className="fake-chart line-chart">
                {useBars(tick + 3).map((h, i) => (
                  <i key={i} style={{ left: `${6 + i * 11.5}%`, height: `${h}%` }} />
                ))}
              </div>
              <div className="simple-xaxis">
                <span>-30s</span>
                <span>-20s</span>
                <span>-10s</span>
                <span>now</span>
              </div>
            </div>
          </div>
        </div>
        <div className="summary-card">
          <h3>采集任务状态</h3>
          <div className="summary-metrics">
            <div>
              <span>采集 Agent</span>
              <strong className="status-tag success">运行中 ×32</strong>
            </div>
            <div>
              <span>指标维度</span>
              <strong>48 项</strong>
            </div>
            <div>
              <span>采集周期</span>
              <strong>5s / 高频</strong>
            </div>
            <div>
              <span>存储后端</span>
              <strong>时序数据库 (TSDB)</strong>
            </div>
            <div>
              <span>数据保留</span>
              <strong>原始 7 天 / 聚合 90 天</strong>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

/* ---------- 3.4 分级预警快速闭环处置 ---------- */
function Alerts() {
  const { alerts, update, addOpLog, toast } = useStore();
  const [level, setLevel] = useState<'all' | Alert['level']>('all');
  const [detail, setDetail] = useState<Alert | null>(null);
  const [showCodes, setShowCodes] = useState(false);

  const filtered = alerts.filter((a) => level === 'all' || a.level === level);

  function advance(a: Alert, to: Alert['status']) {
    update((d) => ({
      alerts: d.alerts.map((x) => (x.id === a.id ? { ...x, status: to } : x)),
      agents: to === 'resolved' ? d.agents.map((agent) => (agent.name === a.source && agent.status === 'abnormal' ? { ...agent, status: 'running' } : agent)) : d.agents,
    }));
    const labels: Record<Alert['status'], string> = { pending: '重置', claimed: '认领', processing: '处置', resolved: '闭环' };
    addOpLog({ operator: 'admin', module: '监控管理', action: `${labels[to]}告警`, target: `${a.id} ${a.source}`, result: 'success', ip: '10.1.28.16', detail: a.type });
    toast(`告警 ${a.id} 已${labels[to]}`, to === 'resolved' ? 'success' : 'info');
    if (detail) setDetail({ ...detail, status: to });
  }

  const counts = {
    critical: alerts.filter((a) => a.level === 'critical' && a.status !== 'resolved').length,
    warning: alerts.filter((a) => a.level === 'warning' && a.status !== 'resolved').length,
    resolved: alerts.filter((a) => a.status === 'resolved').length,
  };

  return (
    <>
      <div className="four-cols stats-grid">
        <div className="stat-card">
          <span>严重告警(未闭环)</span>
          <strong style={{ color: 'var(--danger)' }}>{counts.critical}</strong>
          <em>需立即处置</em>
        </div>
        <div className="stat-card">
          <span>一般告警(未闭环)</span>
          <strong style={{ color: '#c17a00' }}>{counts.warning}</strong>
          <em>关注趋势</em>
        </div>
        <div className="stat-card">
          <span>今日已闭环</span>
          <strong style={{ color: 'var(--success)' }}>{counts.resolved}</strong>
          <em>闭环率高</em>
        </div>
        <div className="stat-card">
          <span>错误码分类</span>
          <strong>{ERROR_CODES.length}</strong>
          <em>
            <button className="text-btn" onClick={() => setShowCodes(true)}>
              查看错误码字典
            </button>
          </em>
        </div>
      </div>

      <div className="toolbar-card">
        <div className="chip-group">
          {(['all', 'critical', 'warning', 'info'] as const).map((l) => (
            <button key={l} className={`chip${level === l ? ' active' : ''}`} onClick={() => setLevel(l)}>
              {l === 'all' ? '全部级别' : LEVEL_META[l].label}
            </button>
          ))}
        </div>
        <button className="ghost-btn" onClick={() => setShowCodes(true)}>
          错误码分类字典
        </button>
      </div>

      <div className="table-card">
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>告警编号</th>
                <th>级别</th>
                <th>错误码</th>
                <th>分类</th>
                <th>来源对象</th>
                <th>异常类型</th>
                <th>触发时间</th>
                <th>责任人</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((a) => (
                <tr key={a.id}>
                  <td>{a.id}</td>
                  <td>
                    <span className={`status-tag ${LEVEL_META[a.level].tag}`}>{LEVEL_META[a.level].label}</span>
                  </td>
                  <td>
                    <span className="kbd">{a.errorCode}</span>
                  </td>
                  <td>
                    <span className="tag-pill">{a.category}</span>
                  </td>
                  <td>{a.source}</td>
                  <td>{a.type}</td>
                  <td>{a.triggeredAt}</td>
                  <td>{a.owner}</td>
                  <td>
                    <span className={`status-tag ${ALERT_STATUS[a.status].tag}`}>{ALERT_STATUS[a.status].label}</span>
                  </td>
                  <td>
                    <button className="text-btn" onClick={() => setDetail(a)}>
                      查看详情
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 告警详情与处置 Modal */}
      <Modal
        open={!!detail}
        title={detail ? `告警详情 · ${detail.id}` : ''}
        wide
        onClose={() => setDetail(null)}
        footer={
          detail && (
            <>
              {detail.status === 'pending' && (
                <button className="ghost-btn" onClick={() => advance(detail, 'claimed')}>
                  认领
                </button>
              )}
              {detail.status !== 'resolved' && (
                <button className="primary-btn" onClick={() => advance(detail, 'processing')}>
                  开始处置
                </button>
              )}
              {detail.status !== 'resolved' && (
                <button className="primary-btn" onClick={() => advance(detail, 'resolved')}>
                  标记闭环
                </button>
              )}
              {detail.status === 'resolved' && (
                <button className="ghost-btn" onClick={() => setDetail(null)}>
                  关闭
                </button>
              )}
            </>
          )
        }
      >
        {detail &&
          (() => {
            const ec = ERROR_CODES.find((e) => e.code === detail.errorCode);
            return (
              <>
                <div className="summary-metrics">
                  <div>
                    <span>级别</span>
                    <strong className={`status-tag ${LEVEL_META[detail.level].tag}`}>{LEVEL_META[detail.level].label}</strong>
                  </div>
                  <div>
                    <span>错误码</span>
                    <strong>
                      <span className="kbd">{detail.errorCode}</span> · {detail.category}
                    </strong>
                  </div>
                  <div>
                    <span>来源对象</span>
                    <strong>{detail.source}</strong>
                  </div>
                  <div>
                    <span>异常类型</span>
                    <strong>{detail.type}</strong>
                  </div>
                  <div>
                    <span>触发时间</span>
                    <strong>{detail.triggeredAt}</strong>
                  </div>
                  <div>
                    <span>当前状态</span>
                    <strong className={`status-tag ${ALERT_STATUS[detail.status].tag}`}>{ALERT_STATUS[detail.status].label}</strong>
                  </div>
                </div>
                <hr />
                <div style={{ marginBottom: 16 }}>
                  <strong style={{ display: 'block', marginBottom: 8, fontSize: '14px', color: 'var(--text)' }}>📋 详细信息</strong>
                  <p style={{ lineHeight: 1.6, color: 'var(--text-secondary)' }}>{detail.detail}</p>
                </div>
                {detail.rootCause && (
                  <div style={{ marginBottom: 16 }}>
                    <strong style={{ display: 'block', marginBottom: 8, fontSize: '14px', color: 'var(--text)' }}>🔍 根因分析</strong>
                    <p style={{ lineHeight: 1.6, color: 'var(--text-secondary)' }}>{detail.rootCause}</p>
                  </div>
                )}
                {detail.suggestion && (
                  <div className="warning-box" style={{ marginBottom: 16 }}>
                    <strong>💡 建议措施</strong>
                    <p style={{ marginTop: 8, lineHeight: 1.6, whiteSpace: 'pre-line' }}>{detail.suggestion}</p>
                  </div>
                )}
                <div style={{ marginBottom: 16 }}>
                  <strong style={{ display: 'block', marginBottom: 8, fontSize: '14px', color: 'var(--text)' }}>影响范围</strong>
                  <p style={{ lineHeight: 1.6, color: 'var(--text-secondary)' }}>{detail.impact}</p>
                </div>
                {ec && (
                  <div className="info-box" style={{ marginBottom: 16 }}>
                    <strong>错误码说明（{ec.code}）</strong>
                    <p style={{ marginTop: 8 }}>
                      {ec.desc}。标准处置流程：{ec.action}。
                    </p>
                  </div>
                )}
                <div className="section-title">闭环流程</div>
                <div className="chip-group">
                  {(['pending', 'claimed', 'processing', 'resolved'] as Alert['status'][]).map((s, i) => (
                    <span key={s} className={`chip${detail.status === s ? ' active' : ''}`}>
                      {i + 1}. {ALERT_STATUS[s].label}
                    </span>
                  ))}
                </div>
              </>
            );
          })()}
      </Modal>

      {/* 错误码字典 */}
      <Modal
        open={showCodes}
        title="错误码分类字典"
        wide
        onClose={() => setShowCodes(false)}
        footer={
          <button className="ghost-btn" onClick={() => setShowCodes(false)}>
            关闭
          </button>
        }
      >
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>错误码</th>
                <th>分类</th>
                <th>级别</th>
                <th>说明</th>
                <th>处置动作</th>
              </tr>
            </thead>
            <tbody>
              {ERROR_CODES.map((e) => (
                <tr key={e.code}>
                  <td>
                    <span className="kbd">{e.code}</span>
                  </td>
                  <td>
                    <span className="tag-pill">{e.category}</span>
                  </td>
                  <td>
                    <span className={`status-tag ${LEVEL_META[e.level as Alert['level']].tag}`}>{LEVEL_META[e.level as Alert['level']].label}</span>
                  </td>
                  <td>{e.desc}</td>
                  <td className="subtle">{e.action}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Modal>
    </>
  );
}
