import { useMemo, useState } from 'react';
import { useStore } from '../store/store-context';
import type { ModelEntry } from '../store/types';
import Modal from '../components/Modal';
import Select from '../components/Select';

type Tab = 'list' | 'traffic' | 'usage' | 'audit';

const STATUS_META: Record<ModelEntry['status'], { label: string; tag: string }> = {
  available: { label: '可用', tag: 'success' },
  maintenance: { label: '维护中', tag: 'warning' },
  offline: { label: '已下线', tag: 'neutral' },
};

const emptyModel = (): Omit<ModelEntry, 'id'> => ({
  name: '',
  model: '',
  apiEndpoint: '',
  apiKey: '',
  description: '',
  status: 'available',
  price: 0.5,
  todayCalls: 0,
  todayTokens: 0,
  errorRate: 0,
  avgLatency: 1500,
  containerCost: 100,
});

function stripModelSecret<T extends ModelEntry | Omit<ModelEntry, 'id'>>(model: T): T {
  return { ...model, apiKey: '' };
}

export default function ModelsPage() {
  const { models, update, addOpLog, toast } = useStore();
  const [tab, setTab] = useState<Tab>('list');
  const [editing, setEditing] = useState<ModelEntry | null>(null);
  const [creating, setCreating] = useState<Omit<ModelEntry, 'id'> | null>(null);
  const [credentialFieldsUnlocked, setCredentialFieldsUnlocked] = useState(false);
  const canManageModels = true;
  const [trafficPolicy, setTrafficPolicy] = useState({
    scope: '全局',
    overloadStrategy: '排队并切换备用模型',
    fallbackModel: 'DeepSeek-R1 企业版',
  });

  const totals = useMemo(() => {
    const calls = models.reduce((s, m) => s + (m.todayCalls || 0), 0);
    const tokens = models.reduce((s, m) => s + (m.todayTokens || 0), 0);
    // Token 成本 = (todayTokens(k) / 1000) * price(元/M) + containerCost(元/天)
    const cost = models.reduce((s, m) => s + ((m.todayTokens || 0) / 1000) * (m.price || 0) + (m.containerCost || 0), 0);
    const available = models.filter((m) => m.status === 'available').length;
    const errs = models.reduce((s, m) => s + Math.round((m.todayCalls || 0) * ((m.errorRate || 0) / 100)), 0);
    // 平均延迟 = 所有模型平均延迟的加权平均（按调用量权重）
    const totalWeightedLatency = models.reduce((s, m) => s + (m.avgLatency || 0) * (m.todayCalls || 0), 0);
    const avgLatency = calls > 0 ? Math.round(totalWeightedLatency / calls) : 0;
    return { calls, tokens, cost, available, errs, avgLatency };
  }, [models]);

  const STATUS_LABEL: Record<ModelEntry['status'], string> = {
    available: '可用',
    maintenance: '维护中',
    offline: '已下线',
  };

  function exportCsv() {
    const headers = ['模型名称', 'Model', '接口地址', '状态', '单价(元/M token)', '今日调用量', '今日消耗(k token)', '错误率(%)', '平均时延(ms)', 'Token成本(元)', '容器成本(元)'];
    const rows = models.map((m) => [
      m.name,
      m.model,
      m.apiEndpoint,
      STATUS_LABEL[m.status],
      m.price.toFixed(2),
      m.todayCalls,
      m.todayTokens,
      m.errorRate,
      m.avgLatency,
      ((m.todayTokens / 1000) * m.price).toFixed(2),
      m.containerCost,
    ]);
    const esc = (v: string | number) => {
      const s = String(v);
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    const csv = [headers, ...rows].map((r) => r.map(esc).join(',')).join('\r\n');
    // BOM 保证 Excel 正确识别 UTF-8 中文
    const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    const d = new Date();
    const p = (n: number) => String(n).padStart(2, '0');
    a.href = url;
    a.download = `模型调用台账_${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    addOpLog({
      operator: 'admin',
      module: '模型网关',
      action: '导出台账',
      target: `${models.length} 个模型`,
      result: 'success',
      ip: '10.1.28.16',
      detail: 'CSV 导出模型调用与成本台账',
    });
    toast(`已导出 ${models.length} 个模型台账 CSV`, 'success');
  }

  function saveModel() {
    if (!canManageModels) {
      toast('当前账号缺少 model.manage 权限，无法变更模型配置', 'danger');
      return;
    }
    if (editing) {
      if (editing.price < 0) {
        toast('价格不能为负数', 'danger');
        return;
      }
      update((d) => ({ models: d.models.map((m) => (m.id === editing.id ? stripModelSecret(editing) : m)) }));
      addOpLog({
        operator: 'admin',
        module: '模型网关',
        action: '编辑模型',
        target: editing.name,
        result: 'success',
        ip: '10.1.28.16',
        detail: `Model: ${editing.model} · 单价 ¥${editing.price}/M · 状态 ${STATUS_META[editing.status].label}`,
      });
      toast('模型已更新', 'success');
      setEditing(null);
    } else if (creating) {
      if (!creating.name) {
        toast('请填写模型名称', 'danger');
        return;
      }
      if (!creating.model) {
        toast('请填写模型 Model', 'danger');
        return;
      }
      if (!creating.apiEndpoint) {
        toast('请填写接口地址', 'danger');
        return;
      }
      if (!creating.apiKey?.trim()) {
        toast('请填写 API 密钥', 'danger');
        return;
      }
      if (creating.price < 0) {
        toast('价格不能为负数', 'danger');
        return;
      }
      const id = `mo-${Date.now().toString().slice(-5)}`;
      update((d) => ({ models: [...d.models, stripModelSecret({ ...creating, id })] }));
      addOpLog({
        operator: 'admin',
        module: '模型网关',
        action: '接入模型',
        target: creating.name,
        result: 'success',
        ip: '10.1.28.16',
        detail: `Model: ${creating.model} · Endpoint: ${creating.apiEndpoint}`,
      });
      toast('模型已接入', 'success');
      setCreating(null);
    }
  }

  function toggleStatus(m: ModelEntry) {
    if (!canManageModels) {
      toast('当前账号缺少 model.manage 权限，无法切换模型状态', 'danger');
      return;
    }
    const next: ModelEntry['status'] = m.status === 'available' ? 'maintenance' : 'available';
    update((d) => ({ models: d.models.map((x) => (x.id === m.id ? { ...x, status: next } : x)) }));
    addOpLog({ operator: 'admin', module: '模型网关', action: '切换模型状态', target: m.name, result: 'success', ip: '10.1.28.16', detail: STATUS_META[next].label });
    toast(`${m.name} 已置为${STATUS_META[next].label}`, 'info');
  }

  const ef = editing || creating;
  const setEF = (p: Partial<ModelEntry>) => {
    if (editing) setEditing({ ...editing, ...p });
    else if (creating) setCreating({ ...creating, ...p });
  };
  const unlockCredentialFields = () => setCredentialFieldsUnlocked(true);

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>模型网关</h1>
          <p>统一接入与治理公有、私有化与行业模型，支撑调用限流、审计追溯与调用用量统计。</p>
        </div>
        <div className="head-actions">
          <button className="ghost-btn" onClick={exportCsv}>
            导出台账
          </button>
          <button
            className="primary-btn"
            disabled={!canManageModels}
            title={canManageModels ? undefined : '缺少 model.manage 权限'}
            onClick={() => {
              setCredentialFieldsUnlocked(false);
              setCreating(emptyModel());
            }}
          >
            + 新增模型
          </button>
        </div>
      </div>

      <div className="five-cols stats-grid">
        <div className="stat-card accent">
          <span>接入模型数</span>
          <strong>{models.length}</strong>
          <em>公有+私有+行业</em>
        </div>
        <div className="stat-card">
          <span>可用模型</span>
          <strong>{totals.available}</strong>
          <em>{models.length - totals.available} 个维护中</em>
        </div>
        <div className="stat-card">
          <span>今日调用量</span>
          <strong>{totals.calls.toLocaleString()}</strong>
          <em>较昨日 +11%</em>
        </div>
        <div className="stat-card">
          <span>异常调用</span>
          <strong>{totals.errs}</strong>
          <em>集中在备用链路</em>
        </div>
        <div className="stat-card">
          <span>今日模型成本</span>
          <strong>¥{Math.round(totals.cost).toLocaleString()}</strong>
          <em>预算使用 61%</em>
        </div>
      </div>

      <div className="toolbar-card">
        <div className="chip-group">
          {(
            [
              ['list', '模型列表'],
              ['traffic', '流量策略'],
              ['usage', '用量统计'],
              ['audit', '调用审计'],
            ] as [Tab, string][]
          ).map(([k, l]) => (
            <button key={k} className={`chip${tab === k ? ' active' : ''}`} onClick={() => setTab(k)}>
              {l}
            </button>
          ))}
        </div>
      </div>

      {tab === 'list' && (
        <div className="table-card">
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>模型名称</th>
                  <th>Model</th>
                  <th>接口地址</th>
                  <th>状态</th>
                  <th>单价(元/M token)</th>
                  <th>容器成本(元/天)</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {models.map((m) => (
                  <tr key={m.id}>
                    <td>
                      <strong>{m.name}</strong>
                      <br />
                      <span style={{ color: 'var(--muted)', fontSize: '12px' }}>{m.description}</span>
                    </td>
                    <td>
                      <code style={{ fontSize: '12px', padding: '2px 6px', background: 'var(--bg-soft)', borderRadius: '4px' }}>{m.model}</code>
                    </td>
                    <td style={{ maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={m.apiEndpoint}>
                      {m.apiEndpoint}
                    </td>
                    <td>
                      <span className={`status-tag ${STATUS_META[m.status].tag}`}>{STATUS_META[m.status].label}</span>
                    </td>
                    <td>¥{m.price.toFixed(2)}</td>
                    <td>¥{m.containerCost}</td>
                    <td>
                      <button
                        className="text-btn"
                        disabled={!canManageModels}
                        onClick={() => {
                          setCredentialFieldsUnlocked(false);
                          setEditing({ ...m, apiKey: '' });
                        }}
                      >
                        编辑
                      </button>
                      {'　'}
                      <button className="text-btn" disabled={!canManageModels} onClick={() => toggleStatus(m)}>
                        {m.status === 'available' ? '停用' : '启用'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'traffic' && (
        <div className="split-layout">
          <div className="form-card">
            <h3>流量治理策略</h3>
            <div className="form-grid two-cols">
              <label>
                适用范围
                <Select
                  value={trafficPolicy.scope}
                  options={['合同合规审核智能体', '客户服务智能体', '全局'].map((s) => ({ value: s, label: s }))}
                  onChange={(val) => setTrafficPolicy({ ...trafficPolicy, scope: val })}
                />
              </label>
              <label>
                并发阈值
                <input defaultValue={60} />
              </label>
              <label>
                单日调用上限
                <input defaultValue={50000} />
              </label>
              <label>
                超限策略
                <Select
                  value={trafficPolicy.overloadStrategy}
                  options={['排队并切换备用模型', '直接拒绝', '降级响应'].map((s) => ({ value: s, label: s }))}
                  onChange={(val) => setTrafficPolicy({ ...trafficPolicy, overloadStrategy: val })}
                />
              </label>
              <label>
                熔断阈值
                <input defaultValue="8%" />
              </label>
              <label>
                备用模型
                <Select
                  value={trafficPolicy.fallbackModel}
                  options={['DeepSeek-R1 企业版', 'Spark Max 法务增强版'].map((m) => ({ value: m, label: m }))}
                  onChange={(val) => setTrafficPolicy({ ...trafficPolicy, fallbackModel: val })}
                />
              </label>
            </div>
            <button className="primary-btn" style={{ marginTop: 16 }} onClick={() => toast('流量策略已保存', 'success')}>
              保存策略
            </button>
          </div>
          <div className="summary-card">
            <h3>今日策略命中</h3>
            <div className="summary-metrics">
              <div>
                <span>削峰次数</span>
                <strong>17</strong>
              </div>
              <div>
                <span>排队降级次数</span>
                <strong>9</strong>
              </div>
              <div>
                <span>备用模型接管</span>
                <strong>3</strong>
              </div>
              <div>
                <span>超限拦截</span>
                <strong>1</strong>
              </div>
              <div>
                <span>熔断触发</span>
                <strong>0</strong>
              </div>
            </div>
          </div>
        </div>
      )}

      {tab === 'usage' && <UsageView models={models} />}

      {tab === 'audit' && (
        <div className="table-card">
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>调用人</th>
                  <th>时间</th>
                  <th>模型</th>
                  <th>输入摘要</th>
                  <th>输出摘要</th>
                  <th>耗时</th>
                  <th>消耗(token)</th>
                  <th>费用</th>
                  <th>状态</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>王琳</td>
                  <td>2026-06-25 10:21:18</td>
                  <td>Spark Max 法务增强版</td>
                  <td>审查供应合同违约责任条款</td>
                  <td>识别 3 处高风险条款</td>
                  <td>2.8s</td>
                  <td>1,820</td>
                  <td>¥0.042</td>
                  <td>
                    <span className="status-tag success">成功</span>
                  </td>
                </tr>
                <tr>
                  <td>周平</td>
                  <td>2026-06-25 09:58:04</td>
                  <td>Qwen-Office</td>
                  <td>生成会议纪要</td>
                  <td>超时后切至备用模型</td>
                  <td>7.6s</td>
                  <td>2,140</td>
                  <td>¥0.039</td>
                  <td>
                    <span className="status-tag warning">降级成功</span>
                  </td>
                </tr>
                <tr>
                  <td>陈思</td>
                  <td>2026-06-25 09:40:12</td>
                  <td>DeepSeek-R1 企业版</td>
                  <td>生成单元测试用例</td>
                  <td>输出 12 个测试用例</td>
                  <td>3.4s</td>
                  <td>3,260</td>
                  <td>¥0.101</td>
                  <td>
                    <span className="status-tag success">成功</span>
                  </td>
                </tr>
                <tr>
                  <td>李涛</td>
                  <td>2026-06-25 09:12:40</td>
                  <td>Spark Max 法务增强版</td>
                  <td>排查告警根因</td>
                  <td>定位为模型回退失败</td>
                  <td>1.9s</td>
                  <td>980</td>
                  <td>¥0.023</td>
                  <td>
                    <span className="status-tag success">成功</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* edit/create modal */}
      <Modal
        open={!!ef}
        title={editing ? `编辑模型 · ${editing.name}` : '新增模型接入'}
        wide
        onClose={() => {
          setCredentialFieldsUnlocked(false);
          setEditing(null);
          setCreating(null);
        }}
        footer={
          <>
            <button
              className="ghost-btn"
              onClick={() => {
                setCredentialFieldsUnlocked(false);
                setEditing(null);
                setCreating(null);
              }}
            >
              取消
            </button>
            <button className="primary-btn" onClick={saveModel} disabled={!canManageModels}>
              保存
            </button>
          </>
        }
      >
        {ef && (
          <form className="form-grid two-cols" autoComplete="off" onSubmit={(event) => event.preventDefault()}>
            <label>
              模型名称
              <input value={ef.name} onChange={(e) => setEF({ name: e.target.value })} placeholder="如：Spark Max 法务增强版" autoComplete="off" />
            </label>
            <label>
              Model 标识
              <input value={ef.model} onChange={(e) => setEF({ model: e.target.value })} placeholder="如：spark-max-legal, gpt-4" autoComplete="off" />
            </label>
            <label className="full">
              接口地址
              <input
                name="model-api-endpoint"
                value={ef.apiEndpoint}
                onFocus={unlockCredentialFields}
                onChange={(e) => setEF({ apiEndpoint: e.target.value })}
                placeholder="如：https://api.xunfei.cn/v1/chat"
                autoComplete="off"
                autoCapitalize="none"
                autoCorrect="off"
                spellCheck={false}
                readOnly={!credentialFieldsUnlocked}
              />
            </label>
            <label className="full">
              API 密钥
              <input
                type="password"
                name="model-api-secret"
                value={ef.apiKey ?? ''}
                onFocus={unlockCredentialFields}
                onChange={(e) => setEF({ apiKey: e.target.value })}
                placeholder={editing ? '留空表示不更换；保存后前端不回显' : '仅提交后端密钥托管，前端不保存'}
                autoComplete="new-password"
                autoCapitalize="none"
                autoCorrect="off"
                spellCheck={false}
                readOnly={!credentialFieldsUnlocked}
              />
            </label>
            <label className="full">
              模型描述
              <textarea rows={2} value={ef.description} onChange={(e) => setEF({ description: e.target.value })} placeholder="描述模型的特点、适用场景等" autoComplete="off" />
            </label>
            <label>
              状态
              <Select
                value={ef.status}
                options={[
                  { value: 'available', label: '可用' },
                  { value: 'maintenance', label: '维护中' },
                  { value: 'offline', label: '已下线' },
                ]}
                onChange={(val) => setEF({ status: val as ModelEntry['status'] })}
              />
            </label>
            <label>
              单价（元/百万 token）
              <input type="number" step="0.1" min="0" value={ef.price} onChange={(e) => setEF({ price: Math.max(0, Number(e.target.value)) })} />
            </label>
            <label>
              容器成本（元/天）
              <input type="number" step="10" min="0" value={ef.containerCost} onChange={(e) => setEF({ containerCost: Math.max(0, Number(e.target.value)) })} />
            </label>
          </form>
        )}
      </Modal>
    </div>
  );
}

/* ---------- 4.4 调用用量统计 ---------- */
function UsageView({ models }: { models: ModelEntry[] }) {
  const rows = models.map((m) => ({
    ...m,
    tokenCost: (m.todayTokens / 1000) * m.price,
    dailyContainerCost: m.containerCost || 0, // 防止 undefined 导致 NaN
  }));
  const totalTokenCost = rows.reduce((s, r) => s + (r.tokenCost || 0), 0);
  const totalContainerCost = rows.reduce((s, r) => s + (r.dailyContainerCost || 0), 0);
  const totalCost = totalTokenCost + totalContainerCost;
  const monthCost = totalCost * 26; // 模拟月累计
  const maxCost = Math.max(...rows.map((r) => (r.tokenCost || 0) + (r.dailyContainerCost || 0)), 1);

  // 计算总 Token 消耗（M）
  const totalTokensM = models.reduce((s, m) => s + (m.todayTokens || 0), 0) / 1000;

  return (
    <>
      <div className="info-banner">成本 = Token 成本（调用消耗 token × 模型单价）+ 容器成本（每日固定成本），按模型实时联动核算。下方为今日各模型消耗与费用分摊。</div>
      <div className="four-cols stats-grid">
        <div className="stat-card accent">
          <span>今日 Token 消耗</span>
          <strong>{totalTokensM.toFixed(1)}M</strong>
          <em>全模型合计</em>
        </div>
        <div className="stat-card">
          <span>今日 Token 成本</span>
          <strong>¥{Math.round(totalTokenCost).toLocaleString()}</strong>
          <em>按量计费</em>
        </div>
        <div className="stat-card">
          <span>今日容器成本</span>
          <strong>¥{Math.round(totalContainerCost).toLocaleString()}</strong>
          <em>固定成本</em>
        </div>
        <div className="stat-card">
          <span>今日总成本</span>
          <strong>¥{Math.round(totalCost).toLocaleString()}</strong>
          <em>本月预估 ¥{Math.round(monthCost).toLocaleString()}</em>
        </div>
      </div>

      <div className="split-layout">
        <div className="table-card" style={{ flex: 1.4 }}>
          <h3 style={{ padding: '18px 20px 0', margin: 0 }}>按模型消耗与成本</h3>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>模型</th>
                  <th>调用量</th>
                  <th>消耗(M token)</th>
                  <th>Token 成本</th>
                  <th>容器成本</th>
                  <th>总成本</th>
                  <th>占比</th>
                </tr>
              </thead>
              <tbody>
                {rows
                  .sort((a, b) => b.tokenCost + b.dailyContainerCost - (a.tokenCost + a.dailyContainerCost))
                  .map((r) => (
                    <tr key={r.id}>
                      <td>{r.name}</td>
                      <td>{r.todayCalls.toLocaleString()}</td>
                      <td>{((r.todayTokens || 0) / 1000).toFixed(1)}M</td>
                      <td>¥{Math.round(r.tokenCost || 0).toLocaleString()}</td>
                      <td>¥{r.dailyContainerCost || 0}</td>
                      <td>
                        <strong>¥{Math.round((r.tokenCost || 0) + (r.dailyContainerCost || 0)).toLocaleString()}</strong>
                      </td>
                      <td style={{ minWidth: 120 }}>
                        <div className="progress">
                          <i style={{ width: `${(((r.tokenCost || 0) + (r.dailyContainerCost || 0)) / maxCost) * 100}%` }} />
                        </div>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </div>
        <div className="summary-card">
          <h3>部门成本分摊</h3>
          <div className="summary-metrics">
            <div>
              <span>法务与合规中心</span>
              <strong>¥{Math.round(totalCost * 0.34).toLocaleString()}</strong>
            </div>
            <div>
              <span>科技研发中心</span>
              <strong>¥{Math.round(totalCost * 0.28).toLocaleString()}</strong>
            </div>
            <div>
              <span>客户服务中心</span>
              <strong>¥{Math.round(totalCost * 0.21).toLocaleString()}</strong>
            </div>
            <div>
              <span>综合办公室</span>
              <strong>¥{Math.round(totalCost * 0.1).toLocaleString()}</strong>
            </div>
            <div>
              <span>其他</span>
              <strong>¥{Math.round(totalCost * 0.07).toLocaleString()}</strong>
            </div>
          </div>
          <div className="success-box">成本与调用用量实时联动，可导出至财务系统进行内部结算与预算管控。</div>
        </div>
      </div>
    </>
  );
}
