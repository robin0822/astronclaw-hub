import { useMemo, useState } from 'react';
import { useStore } from '../store/store-context';
import type { Agent, Alert } from '../store/types';
import Modal from '../components/Modal';
import { diagnosticsApi } from '../api/diagnostics';

interface DiagTarget {
  key: string;
  diagnosisId: string;
  kind: 'agent' | 'alert';
  name: string;
  statusLabel: string;
  statusTag: string;
  errorCode: string;
  symptom: string;
  impact: string;
}

interface KbRow {
  code: string;
  symptom: string;
  cause: string;
  fix: string;
}

interface TraceStep {
  name: string;
  state: 'ok' | 'fail' | 'skip';
}

const TRACE_STEPS: TraceStep[] = [
  { name: '输入解析', state: 'ok' },
  { name: '知识检索', state: 'ok' },
  { name: '模型调用', state: 'fail' },
  { name: '结果输出', state: 'skip' },
];

const KB_SEED: KbRow[] = [
  { code: 'E5021', symptom: '模型回退失败，请求大面积超时', cause: '主模型熔断后备用模型连接被拒绝', fix: '检查备用模型连通性、配额与模型网关策略，恢复后重试链路' },
  { code: 'E2010', symptom: '节点心跳异常，实例频繁掉线', cause: '节点网络抖动或负载过高导致心跳丢失', fix: '排查节点网络与负载，必要时迁移实例至健康节点' },
  { code: 'W3304', symptom: 'GPU 过载，推理时延升高', cause: '并发超过 GPU 算力上限', fix: '降低并发阈值或扩容 GPU 节点，开启请求排队' },
  { code: 'W4102', symptom: '接口超时升高，偶发 504', cause: '下游依赖响应慢或超时阈值过低', fix: '提高超时阈值并优化下游依赖，增加重试与缓存' },
];

const STATE_META: Record<TraceStep['state'], { tag: string; label: string }> = {
  ok: { tag: 'success', label: '通过' },
  fail: { tag: 'danger', label: '失败点' },
  skip: { tag: 'neutral', label: '未执行' },
};

export default function DiagnosisPage() {
  const { agents, alerts, update, addOpLog, toast } = useStore();
  const [target, setTarget] = useState<DiagTarget | null>(null);
  const [fixing, setFixing] = useState(false);

  const abnormalCount = useMemo(() => agents.filter((agent) => agent.status === 'abnormal').length, [agents]);
  const activeAlerts = useMemo(() => alerts.filter((alert) => alert.status !== 'resolved').length, [alerts]);

  const targets = useMemo<DiagTarget[]>(() => {
    const fromAgents: DiagTarget[] = agents
      .filter((agent: Agent) => agent.status === 'abnormal')
      .map((agent) => ({
        key: `agent-${agent.id}`,
        diagnosisId: `diag-agent-${agent.id}`,
        kind: 'agent',
        name: agent.name,
        statusLabel: '实例异常',
        statusTag: 'danger',
        errorCode: 'E2010',
        symptom: `实例运行异常 · 模型 ${agent.model}`,
        impact: `负责人 ${agent.owner} · ${agent.department}`,
      }));
    const fromAlerts: DiagTarget[] = alerts
      .filter((alert: Alert) => alert.status !== 'resolved' && (alert.level === 'critical' || alert.level === 'warning'))
      .map((alert) => ({
        key: `alert-${alert.id}`,
        diagnosisId: `diag-alert-${alert.id}`,
        kind: 'alert',
        name: alert.source,
        statusLabel: alert.level === 'critical' ? '严重告警' : '一般告警',
        statusTag: alert.level === 'critical' ? 'danger' : 'warning',
        errorCode: alert.errorCode,
        symptom: alert.type,
        impact: alert.impact,
      }));
    return [...fromAgents, ...fromAlerts];
  }, [agents, alerts]);

  async function repair() {
    if (!target) return;
    setFixing(true);
    try {
      const result = await diagnosticsApi.fix(target.diagnosisId);
      const matchedAgent = target.kind === 'agent' ? agents.find((agent) => `agent-${agent.id}` === target.key) : agents.find((agent) => agent.name === target.name);
      if (matchedAgent && (result.status === 'completed' || result.status === 'success')) {
        update((data) => ({ agents: data.agents.map((agent) => (agent.id === matchedAgent.id ? { ...agent, status: 'running', qps: Math.max(agent.qps, 10) } : agent)) }));
      }
      addOpLog({
        operator: 'admin',
        module: '问题诊断',
        action: '执行修复',
        target: `${target.name} (${target.errorCode})`,
        result: 'success',
        ip: '10.1.28.16',
        detail: `POST /diagnostics/{diagnosisId}/fix · diagnosisId=${target.diagnosisId} · status=${result.status || 'running'} · ${result.output || ''}`,
      });
      toast(result.status === 'completed' || result.status === 'success' ? '自动修复完成' : `自动修复已触发：${result.status || 'running'}`, 'success');
      setTarget(null);
    } catch (error) {
      toast(error instanceof Error ? error.message : '业务后端调用失败', 'danger');
    } finally {
      setFixing(false);
    }
  }

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>问题诊断</h1>
          <p>面向异常实例与告警提供根因分析、链路诊断与一键修复建议，修复动作按后端文档提交到诊断接口。</p>
        </div>
      </div>

      <div className="four-cols stats-grid">
        <div className="stat-card">
          <span>异常实例数</span>
          <strong style={{ color: 'var(--danger)' }}>{abnormalCount}</strong>
          <em>需诊断处置</em>
        </div>
        <div className="stat-card">
          <span>活跃告警数</span>
          <strong>{activeAlerts}</strong>
          <em>未闭环</em>
        </div>
        <div className="stat-card">
          <span>今日已诊断</span>
          <strong>12</strong>
          <em>较昨日 +3</em>
        </div>
        <div className="stat-card accent">
          <span>平均修复时长</span>
          <strong>8.5min</strong>
          <em>环比下降</em>
        </div>
      </div>

      <div className="section-title">待诊断对象</div>
      {targets.length === 0 ? (
        <div className="success-box">当前无异常实例与未闭环告警，平台运行健康。</div>
      ) : (
        <div className="card-grid two-cols">
          {targets.map((item) => (
            <div className="form-card" key={item.key}>
              <div className="card-topline">
                <h3>{item.name}</h3>
                <span className={`status-tag ${item.statusTag}`}>{item.statusLabel}</span>
              </div>
              <p>
                <span className="kbd">{item.errorCode}</span> {item.symptom}
              </p>
              <p className="subtle">影响范围：{item.impact}</p>
              <button className="primary-btn small" onClick={() => setTarget(item)}>
                一键诊断
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="section-title">常见问题知识库</div>
      <div className="table-card">
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>编码</th>
                <th>现象</th>
                <th>可能原因</th>
                <th>修复建议</th>
              </tr>
            </thead>
            <tbody>
              {KB_SEED.map((row) => (
                <tr key={row.code}>
                  <td>
                    <span className="kbd">{row.code}</span>
                  </td>
                  <td>{row.symptom}</td>
                  <td>{row.cause}</td>
                  <td>{row.fix}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <Modal
        open={Boolean(target)}
        title={target ? `${target.name} 诊断详情` : '诊断详情'}
        wide
        onClose={() => setTarget(null)}
        footer={
          <>
            <button className="ghost-btn" onClick={() => setTarget(null)}>
              取消
            </button>
            <button className="primary-btn" onClick={() => void repair()} disabled={fixing}>
              {fixing ? '修复中...' : '执行修复'}
            </button>
          </>
        }
      >
        {target && (
          <>
            <div className="summary-metrics">
              <div>
                <span>诊断 ID</span>
                <strong>{target.diagnosisId}</strong>
              </div>
              <div>
                <span>对象</span>
                <strong>{target.name}</strong>
              </div>
              <div>
                <span>错误编码</span>
                <strong>{target.errorCode}</strong>
              </div>
              <div>
                <span>影响范围</span>
                <strong>{target.impact}</strong>
              </div>
            </div>
            <div className="section-title">诊断链路</div>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>步骤</th>
                    <th>结果</th>
                  </tr>
                </thead>
                <tbody>
                  {TRACE_STEPS.map((step) => (
                    <tr key={step.name}>
                      <td>{step.name}</td>
                      <td>
                        <span className={`status-tag ${STATE_META[step.state].tag}`}>{STATE_META[step.state].label}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="section-title">根因分析</div>
            <div className="warning-box">主模型响应超时触发熔断，备用模型连接被拒绝。请求在「模型调用」环节中断，结果输出未执行。</div>
            <div className="section-title">修复建议</div>
            <div className="success-box">检查模型网关连通性与配额，恢复后通过 POST /diagnostics/{'{diagnosisId}'}/fix 下发自动修复任务。</div>
          </>
        )}
      </Modal>
    </div>
  );
}
