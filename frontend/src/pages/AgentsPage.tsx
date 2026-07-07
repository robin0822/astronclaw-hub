import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import { useStore } from '../store/store-context';
import { confirmDangerousAction } from '../utils';
import Modal from '../components/Modal';
import Select from '../components/Select';
import Checkbox from '../components/Checkbox';
import { agentsApi } from '../api/agents';
import { batchTasksApi } from '../api/batch-tasks';
import type {
  AgentAction,
  AgentDetail,
  AgentLogType,
  AgentHistory,
  AgentStatus,
  AgentSummary,
  BatchTaskType,
  CreateAgentPayload,
  RuntimeConfigPayload,
  NameRef,
} from '../api/types';

type StatusFilter = 'all' | AgentStatus;
type DetailTab = 'config' | 'logs' | 'deployHistory' | 'versionHistory' | 'stateEvents' | 'skills' | 'knowledgeBases' | 'callStats' | 'alerts' | 'auditLogs';

interface RuntimeConfigForm {
  cpu: string;
  memory: string;
  storage: string;
  gpu: string;
  concurrencyLimit: string;
  dailyCallLimit: string;
  timeoutMs: string;
  primaryModelId: string;
  backupModelId: string;
}

interface CreateForm {
  name: string;
  departmentId: string;
  ownerId: string;
  description: string;
  cpu: string;
  memory: string;
  storage: string;
  gpu: string;
  primaryModelId: string;
  backupModelId: string;
  concurrencyLimit: string;
  dailyCallLimit: string;
  timeoutMs: string;
  skillIds: string;
  knowledgeBaseIds: string;
  memoryPolicy: string;
  messageChannelIds: string;
}

const STATUS_OPTIONS: Array<{ value: StatusFilter; label: string }> = [
  { value: 'all', label: '全部状态' },
  { value: 'draft', label: '草稿' },
  { value: 'running', label: '运行中' },
  { value: 'stopped', label: '已停止' },
  { value: 'abnormal', label: '异常' },
  { value: 'deploying', label: '部署中' },
  { value: 'upgrading', label: '升级中' },
  { value: 'stopping', label: '停止中' },
  { value: 'archived', label: '已归档' },
  { value: 'violation_offline', label: '违规下线' },
];

const STATUS_META: Record<AgentStatus, { label: string; tag: string }> = {
  draft: { label: '草稿', tag: 'neutral' },
  running: { label: '运行中', tag: 'success' },
  stopped: { label: '已停止', tag: 'neutral' },
  abnormal: { label: '异常', tag: 'danger' },
  deploying: { label: '部署中', tag: 'info' },
  upgrading: { label: '升级中', tag: 'warning' },
  stopping: { label: '停止中', tag: 'warning' },
  archived: { label: '已归档', tag: 'neutral' },
  violation_offline: { label: '违规下线', tag: 'danger' },
};

const ACTION_LABEL: Record<AgentAction | 'delete', string> = {
  deploy: '部署',
  start: '启动',
  stop: '停止',
  restart: '重启',
  upgrade: '升级',
  archive: '归档',
  delete: '删除',
};

const LOG_TYPE_OPTIONS: Array<{ value: AgentLogType; label: string }> = [
  { value: 'runtime', label: '运行日志' },
  { value: 'deploy', label: '部署日志' },
  { value: 'upgrade', label: '升级日志' },
  { value: 'container', label: '容器日志' },
  { value: 'model_call', label: '模型调用日志' },
];

const DETAIL_TABS: Array<{ key: DetailTab; label: string }> = [
  { key: 'config', label: '配置' },
  { key: 'logs', label: '运行日志' },
  { key: 'deployHistory', label: '部署历史' },
  { key: 'versionHistory', label: '版本历史' },
  { key: 'stateEvents', label: '状态事件' },
  { key: 'skills', label: '绑定 Skill' },
  { key: 'knowledgeBases', label: '绑定知识库' },
  { key: 'callStats', label: '调用统计' },
  { key: 'alerts', label: '告警记录' },
  { key: 'auditLogs', label: '审计记录' },
];

function statusPill(status: AgentStatus) {
  const meta = STATUS_META[status];
  return <span className={`status-tag ${meta.tag}`}>{meta.label}</span>;
}

function formatDate(value?: string) {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN', { hour12: false });
}

function formatNumber(value: number | string | undefined) {
  if (value === undefined || value === null || value === '') return '-';
  return typeof value === 'number' ? value.toLocaleString('zh-CN') : value;
}

function parseList(value: string) {
  return value
    .split(/[，,\s]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function numeric(value: string, fallback: number) {
  const next = Number(value);
  return Number.isFinite(next) ? next : fallback;
}

function nameOf(value?: string | NameRef) {
  if (!value) return '-';
  return typeof value === 'string' ? value : value.name;
}

function metric(label: string, value: ReactNode) {
  return (
    <div className="metric-pair" key={label}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function runtimeFormFromAgent(agent?: AgentSummary | null): RuntimeConfigForm {
  return {
    cpu: String(agent?.cpu ?? 2),
    memory: String(agent?.memory ?? '4Gi').replace(/Gi$/i, ''),
    storage: String(agent?.storage ?? '20Gi').replace(/Gi$/i, ''),
    gpu: String(agent?.gpu ?? 0),
    concurrencyLimit: String(agent?.concurrencyLimit ?? 20),
    dailyCallLimit: String(agent?.dailyCallLimit ?? 10000),
    timeoutMs: String(agent?.timeoutMs ?? 300000),
    primaryModelId: agent?.primaryModel.id ?? '',
    backupModelId: agent?.backupModel.id ?? '',
  };
}

function runtimePayloadFromForm(form: RuntimeConfigForm): RuntimeConfigPayload {
  return {
    concurrencyLimit: numeric(form.concurrencyLimit, 20),
    dailyCallLimit: numeric(form.dailyCallLimit, 10000),
    timeoutMs: numeric(form.timeoutMs, 300000),
    resourceSpec: {
      cpu: numeric(form.cpu, 2),
      memory: `${numeric(form.memory, 4)}Gi`,
      storage: `${numeric(form.storage, 20)}Gi`,
      gpu: form.gpu.trim() || 0,
    },
    primaryModelId: form.primaryModelId,
    backupModelId: form.backupModelId,
  };
}

function emptyCreateForm(departmentId = '', ownerId = '', primaryModelId = '', backupModelId = ''): CreateForm {
  return {
    name: '',
    departmentId,
    ownerId,
    description: '',
    cpu: '2',
    memory: '4',
    storage: '20',
    gpu: '0',
    primaryModelId,
    backupModelId: backupModelId || primaryModelId,
    concurrencyLimit: '20',
    dailyCallLimit: '10000',
    timeoutMs: '300000',
    skillIds: 'sk001 sk002',
    knowledgeBaseIds: 'kb001',
    memoryPolicy: 'personal',
    messageChannelIds: '',
  };
}

export default function AgentsPage() {
  const { departments, members, models, addOpLog, toast } = useStore();
  const [rows, setRows] = useState<AgentSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState<StatusFilter>('all');
  const [keyword, setKeyword] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(12);
  const [loading, setLoading] = useState(false);
  const [apiNotice, setApiNotice] = useState('');
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [detailAgent, setDetailAgent] = useState<AgentSummary | null>(null);
  const [detail, setDetail] = useState<AgentDetail | null>(null);
  const [detailTab, setDetailTab] = useState<DetailTab>('config');
  const [detailLoading, setDetailLoading] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [logType, setLogType] = useState<AgentLogType>('runtime');
  const [logKeyword, setLogKeyword] = useState('');
  const [detailLogsLoading, setDetailLogsLoading] = useState(false);
  const [runtimeSaving, setRuntimeSaving] = useState(false);
  const [runtimeForm, setRuntimeForm] = useState<RuntimeConfigForm>(() => runtimeFormFromAgent());
  const canCreate = true;
  const canEdit = true;
  const canLifecycle = true;
  const canDelete = true;

  const departmentOptions = useMemo(() => departments.map((item) => ({ value: item.id, label: item.name })), [departments]);
  const ownerOptions = useMemo(() => members.map((item) => ({ value: item.id, label: item.name })), [members]);
  const modelOptions = useMemo(() => models.map((item) => ({ value: item.id, label: item.name })), [models]);
  const [form, setForm] = useState<CreateForm>(() => emptyCreateForm(departments[0]?.id, members[0]?.id, models[0]?.id, models[1]?.id));

  useEffect(() => {
    setForm((prev) => ({
      ...prev,
      departmentId: prev.departmentId || departments[0]?.id || '',
      ownerId: prev.ownerId || members[0]?.id || '',
      primaryModelId: prev.primaryModelId || models[0]?.id || '',
      backupModelId: prev.backupModelId || models[1]?.id || models[0]?.id || '',
    }));
  }, [departments, members, models]);

  const loadAgents = useCallback(async () => {
    setLoading(true);
    try {
      const data = await agentsApi.list({
        keyword: keyword.trim() || undefined,
        status: status === 'all' ? undefined : status,
        page,
        pageSize,
      });
      setRows(data.items);
      setTotal(data.total);
      setApiNotice('');
    } catch (error) {
      setRows([]);
      setTotal(0);
      setApiNotice(`业务后端调用失败：${error instanceof Error ? error.message : '业务后端调用失败'}`);
    } finally {
      setLoading(false);
    }
  }, [keyword, page, pageSize, status]);

  useEffect(() => {
    void loadAgents();
  }, [loadAgents]);

  const selectedAgents = useMemo(() => rows.filter((agent) => selectedIds.includes(agent.id)), [rows, selectedIds]);
  const allChecked = rows.length > 0 && rows.every((agent) => selectedIds.includes(agent.id));
  const someChecked = rows.some((agent) => selectedIds.includes(agent.id)) && !allChecked;
  const pageCount = Math.max(1, Math.ceil(total / pageSize));

  const stats = useMemo(() => {
    return {
      total,
      running: rows.filter((agent) => agent.status === 'running').length,
      abnormal: rows.filter((agent) => agent.status === 'abnormal').length,
      changing: rows.filter((agent) => agent.status === 'deploying' || agent.status === 'upgrading' || agent.status === 'stopping').length,
    };
  }, [rows, total]);

  function updateSearch(next: string) {
    setKeyword(next);
    setPage(1);
  }

  function updateStatus(next: string) {
    setStatus(next as StatusFilter);
    setPage(1);
  }

  function toggleSelected(agentId: string) {
    setSelectedIds((ids) => (ids.includes(agentId) ? ids.filter((id) => id !== agentId) : [...ids, agentId]));
  }

  function toggleAll() {
    setSelectedIds((ids) => {
      const pageIds = rows.map((agent) => agent.id);
      if (pageIds.every((id) => ids.includes(id))) return ids.filter((id) => !pageIds.includes(id));
      return Array.from(new Set([...ids, ...pageIds]));
    });
  }

  async function openDetail(agent: AgentSummary) {
    setDetailAgent(agent);
    setDetail(null);
    setRuntimeForm(runtimeFormFromAgent(agent));
    setLogType('runtime');
    setLogKeyword('');
    setDetailTab('config');
    setDetailLoading(true);
    try {
      const data = await agentsApi.detail(agent.id);
      setDetail(data);
      setRuntimeForm(runtimeFormFromAgent(data.basic));
    } catch (error) {
      setDetail(null);
      setApiNotice(`详情接口读取失败：${error instanceof Error ? error.message : '业务后端调用失败'}`);
    } finally {
      setDetailLoading(false);
    }
  }

  function patchDetailBasic(patch: Partial<AgentSummary>) {
    setDetail((current) => (current ? { ...current, basic: { ...current.basic, ...patch } } : current));
    setDetailAgent((current) => (current ? { ...current, ...patch } : current));
  }

  async function syncCurrentAgent() {
    if (!basic) return;
    try {
      const result = await agentsApi.sync(basic.id);
      patchDetailBasic({ status: result.status, updatedAt: result.lastSyncAt });
      toast(result.syncError ? `同步完成，但存在异常：${result.syncError}` : '实例状态已同步', result.syncError ? 'warning' : 'success');
      await loadAgents();
    } catch (error) {
      toast(error instanceof Error ? error.message : '业务后端调用失败', 'danger');
    }
  }

  async function loadCurrentLogs() {
    if (!basic) return;
    setDetailLogsLoading(true);
    try {
      const result = await agentsApi.logs(basic.id, {
        logType,
        keyword: logKeyword.trim() || undefined,
        page: 1,
        pageSize: 50,
      });
      setDetail((current) => {
        if (!current) return current;
        return { ...current, runtime: { ...(current.runtime ?? {}), logs: result.items } };
      });
      setDetailTab('logs');
      toast('实例日志已刷新', 'success');
    } catch (error) {
      toast(error instanceof Error ? error.message : '业务后端调用失败', 'danger');
    } finally {
      setDetailLogsLoading(false);
    }
  }

  async function saveRuntimeConfig() {
    if (!basic) return;
    if (!canEdit) {
      toast('当前账号缺少 agent.edit 权限，无法保存运行参数', 'danger');
      return;
    }
    setRuntimeSaving(true);
    const payload = runtimePayloadFromForm(runtimeForm);
    try {
      const result = await agentsApi.updateRuntimeConfig(basic.id, payload);
      patchDetailBasic({
        cpu: payload.resourceSpec.cpu,
        memory: payload.resourceSpec.memory,
        storage: payload.resourceSpec.storage,
        gpu: payload.resourceSpec.gpu,
        concurrencyLimit: payload.concurrencyLimit,
        dailyCallLimit: payload.dailyCallLimit,
        timeoutMs: payload.timeoutMs,
        primaryModel: { ...basic.primaryModel, id: payload.primaryModelId },
        backupModel: { ...basic.backupModel, id: payload.backupModelId },
      });
      toast(`运行参数已提交：${result.taskId || result.status}`, 'success');
      await loadAgents();
    } catch (error) {
      toast(error instanceof Error ? error.message : '业务后端调用失败', 'danger');
    } finally {
      setRuntimeSaving(false);
    }
  }
  async function runAgentAction(agent: AgentSummary, action: AgentAction | 'delete') {
    const allowed = action === 'delete' ? canDelete : canLifecycle;
    if (!allowed) {
      toast(`当前账号缺少 ${action === 'delete' ? 'agent.delete' : 'agent.lifecycle'} 权限`, 'danger');
      return;
    }
    if (
      (action === 'delete' || action === 'archive' || action === 'stop') &&
      !confirmDangerousAction(`确认${ACTION_LABEL[action]}智能体「${agent.name}」？该操作会提交到业务后端并写入审计。`)
    )
      return;

    try {
      const result = action === 'delete' ? await agentsApi.remove(agent.id) : await agentsApi.lifecycle(agent.id, action);
      toast(`${agent.name} ${ACTION_LABEL[action]}任务已提交：${result.taskId || result.status}`, 'success');
      addOpLog({
        operator: 'admin',
        module: '智能体管理',
        action: `${ACTION_LABEL[action]}智能体`,
        target: agent.name,
        result: 'success',
        ip: '10.1.28.16',
        detail: `调用 ${action === 'delete' ? 'DELETE /agents/{agentId}' : `POST /agents/{agentId}/${action}`} · task=${result.taskId || '-'}`,
      });
      await loadAgents();
    } catch (error) {
      toast(error instanceof Error ? error.message : '业务后端调用失败', 'danger');
    }
  }

  async function runBatch(type: BatchTaskType) {
    if (selectedIds.length === 0) {
      toast('请先选择智能体实例', 'warning');
      return;
    }
    const allowed = type === 'delete' ? canDelete : canLifecycle;
    if (!allowed) {
      toast(`当前账号缺少 ${type === 'delete' ? 'agent.delete' : 'agent.lifecycle'} 权限`, 'danger');
      return;
    }
    if (
      (type === 'delete' || type === 'archive' || type === 'stop') &&
      !confirmDangerousAction(`确认对 ${selectedIds.length} 个智能体执行批量${ACTION_LABEL[type as AgentAction | 'delete'] || type}？`)
    )
      return;

    try {
      const result = await batchTasksApi.create({
        type,
        scopeType: 'selected',
        targetIds: selectedIds,
        strategy: { batchSize: 10, pauseOnFailure: false, grayPercent: null },
        reason: '前端批量维护操作',
      });
      toast(`批量${ACTION_LABEL[type as AgentAction | 'delete'] || type}任务已创建：${result.id}`, 'success');
      addOpLog({
        operator: 'admin',
        module: '批量任务',
        action: `创建批量${type}`,
        target: `${selectedIds.length} 个智能体`,
        result: 'success',
        ip: '10.1.28.16',
        detail: `POST /batch-tasks · task=${result.id}`,
      });
      setSelectedIds([]);
      await loadAgents();
    } catch (error) {
      toast(error instanceof Error ? error.message : '业务后端调用失败', 'danger');
    }
  }

  async function createAgent() {
    if (!canCreate) {
      toast('当前账号缺少 agent.create 权限，无法创建智能体', 'danger');
      return;
    }
    if (!form.name.trim()) {
      toast('请输入实例名称', 'warning');
      return;
    }
    setCreating(true);
    const payload: CreateAgentPayload = {
      name: form.name.trim(),
      type: 'astronclaw',
      departmentId: form.departmentId,
      ownerId: form.ownerId,
      description: form.description.trim(),
      resourceSpec: {
        cpu: numeric(form.cpu, 2),
        memory: `${numeric(form.memory, 4)}Gi`,
        storage: `${numeric(form.storage, 20)}Gi`,
        gpu: form.gpu.trim() || 0,
      },
      primaryModelId: form.primaryModelId,
      backupModelId: form.backupModelId,
      concurrencyLimit: numeric(form.concurrencyLimit, 20),
      dailyCallLimit: numeric(form.dailyCallLimit, 10000),
      timeoutMs: numeric(form.timeoutMs, 300000),
      skillIds: parseList(form.skillIds),
      knowledgeBaseIds: parseList(form.knowledgeBaseIds),
      memoryPolicy: form.memoryPolicy,
      messageChannelIds: parseList(form.messageChannelIds),
    };

    try {
      const result = await agentsApi.create(payload);
      toast(`${payload.name} 创建成功，部署任务 ${result.deployTaskId}`, 'success');
      addOpLog({
        operator: 'admin',
        module: '智能体管理',
        action: '创建智能体',
        target: payload.name,
        result: 'success',
        ip: '10.1.28.16',
        detail: `POST /agents · botId=${result.botId}`,
      });
      setCreateOpen(false);
      setForm(emptyCreateForm(departments[0]?.id, members[0]?.id, models[0]?.id, models[1]?.id));
      await loadAgents();
    } catch (error) {
      toast(error instanceof Error ? error.message : '业务后端调用失败', 'danger');
    } finally {
      setCreating(false);
    }
  }

  const detailData = detail;
  const basic = detailData?.basic ?? detailAgent;

  function renderHistory(items: AgentHistory[] | undefined, emptyText: string) {
    if (!items?.length) return <div className="empty-state">{emptyText}</div>;
    return (
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>时间</th>
              <th>动作</th>
              <th>版本</th>
              <th>状态</th>
              <th>操作人</th>
              <th>说明</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item, index) => (
              <tr key={item.id || index}>
                <td>{formatDate(item.createdAt || item.startedAt || item.endedAt)}</td>
                <td>{item.action || '-'}</td>
                <td>{item.version || '-'}</td>
                <td>{item.status || '-'}</td>
                <td>{nameOf(item.operator)}</td>
                <td>{item.message || '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  function renderDetailContent() {
    if (!detailData || !basic) return <div className="empty-state">请选择一个智能体实例</div>;

    if (detailTab === 'config') {
      return (
        <>
          <div className="summary-metrics">
            {[
              metric('实例名称', basic.name),
              metric('运行 instanceId', basic.instanceId),
              metric('状态', statusPill(basic.status)),
              metric('版本', basic.version),
              metric('部门', basic.department.name),
              metric('负责人', basic.owner.name),
              metric('容器数', basic.containerCount),
              metric('Skill 数', basic.skillCount),
              metric('绑定知识库', basic.knowledgeBaseCount),
              metric('主模型', basic.primaryModel.name),
              metric('备用模型', basic.backupModel.name),
              metric('CPU', formatNumber(basic.cpu)),
              metric('内存', basic.memory),
              metric('存储', basic.storage),
              metric('GPU', formatNumber(basic.gpu)),
              metric('并发阈值', basic.concurrencyLimit),
              metric('单日调用上限', formatNumber(basic.dailyCallLimit)),
              metric('超时阈值', `${basic.timeoutMs} ms`),
              metric('当前服务人数', basic.currentUsers),
              metric('最大服务人数', basic.maxUsers),
              metric('QPS', basic.qps),
              metric('创建时间', formatDate(basic.createdAt)),
              metric('最近更新时间', formatDate(basic.updatedAt)),
            ]}
          </div>
          <div className="section-title">远程运行参数</div>
          <div className="form-grid two-cols">
            <label>
              CPU
              <input value={runtimeForm.cpu} onChange={(event) => setRuntimeForm({ ...runtimeForm, cpu: event.target.value })} />
            </label>
            <label>
              内存 Gi
              <input value={runtimeForm.memory} onChange={(event) => setRuntimeForm({ ...runtimeForm, memory: event.target.value })} />
            </label>
            <label>
              存储 Gi
              <input value={runtimeForm.storage} onChange={(event) => setRuntimeForm({ ...runtimeForm, storage: event.target.value })} />
            </label>
            <label>
              GPU
              <input value={runtimeForm.gpu} onChange={(event) => setRuntimeForm({ ...runtimeForm, gpu: event.target.value })} />
            </label>
            <label>
              并发阈值
              <input value={runtimeForm.concurrencyLimit} onChange={(event) => setRuntimeForm({ ...runtimeForm, concurrencyLimit: event.target.value })} />
            </label>
            <label>
              单日调用上限
              <input value={runtimeForm.dailyCallLimit} onChange={(event) => setRuntimeForm({ ...runtimeForm, dailyCallLimit: event.target.value })} />
            </label>
            <label>
              超时阈值 ms
              <input value={runtimeForm.timeoutMs} onChange={(event) => setRuntimeForm({ ...runtimeForm, timeoutMs: event.target.value })} />
            </label>
            <label>
              主模型 ID
              <input value={runtimeForm.primaryModelId} onChange={(event) => setRuntimeForm({ ...runtimeForm, primaryModelId: event.target.value })} />
            </label>
            <label>
              备用模型 ID
              <input value={runtimeForm.backupModelId} onChange={(event) => setRuntimeForm({ ...runtimeForm, backupModelId: event.target.value })} />
            </label>
          </div>
          <div className="card-actions">
            <button className="primary-btn small" onClick={() => void saveRuntimeConfig()} disabled={runtimeSaving || !canEdit}>
              {runtimeSaving ? '保存中...' : '保存运行参数'}
            </button>
          </div>
        </>
      );
    }

    if (detailTab === 'logs') {
      const logs = detailData.runtime?.logs ?? [];
      return logs.length ? (
        <div className="log-console">
          {logs.map((log, index) => (
            <p key={log.id || index}>
              <span>[{formatDate(log.ts || log.time)}]</span> <strong>{log.level || 'info'}</strong> {log.message}
            </p>
          ))}
        </div>
      ) : (
        <div className="empty-state">暂无运行日志</div>
      );
    }

    if (detailTab === 'deployHistory') return renderHistory(detailData.deployHistory, '暂无部署历史');
    if (detailTab === 'versionHistory') return renderHistory(detailData.versionHistory, '暂无版本历史');

    if (detailTab === 'skills') {
      return detailData.skills?.length ? (
        <div className="card-grid two-cols">
          {detailData.skills.map((skill) => (
            <div className="form-card" key={skill.id}>
              <div className="card-topline">
                <h3>{skill.name}</h3>
                <span className="status-tag success">{skill.status || 'enabled'}</span>
              </div>
              <p className="subtle">
                版本：{skill.version || '-'} · 分类：{skill.category || '-'}
              </p>
            </div>
          ))}
        </div>
      ) : (
        <div className="empty-state">暂无绑定 Skill</div>
      );
    }

    if (detailTab === 'knowledgeBases') {
      return detailData.knowledgeBases?.length ? (
        <div className="card-grid two-cols">
          {detailData.knowledgeBases.map((kb) => (
            <div className="form-card" key={kb.id}>
              <div className="card-topline">
                <h3>{kb.name}</h3>
                <span className="status-tag info">{kb.status || 'ready'}</span>
              </div>
              <p className="subtle">文件数：{kb.fileCount ?? '-'}</p>
            </div>
          ))}
        </div>
      ) : (
        <div className="empty-state">暂无绑定知识库</div>
      );
    }

    if (detailTab === 'callStats') {
      const statsData = detailData.callStats ?? {};
      return (
        <div className="summary-metrics">
          {metric('今日调用量', formatNumber(statsData.todayCalls as number | undefined))}
          {metric('今日 Token', formatNumber(statsData.todayTokens as number | undefined))}
          {metric('成功率', statsData.successRate === undefined ? '-' : `${statsData.successRate}%`)}
          {metric('平均延迟', statsData.avgLatencyMs === undefined ? '-' : `${statsData.avgLatencyMs} ms`)}
          {metric('峰值 QPS', formatNumber(statsData.peakQps as number | undefined))}
        </div>
      );
    }

    if (detailTab === 'alerts') {
      return detailData.alerts?.length ? (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>时间</th>
                <th>级别</th>
                <th>类型</th>
                <th>状态</th>
                <th>说明</th>
              </tr>
            </thead>
            <tbody>
              {detailData.alerts.map((alert) => (
                <tr key={alert.id}>
                  <td>{formatDate(alert.triggeredAt)}</td>
                  <td>{alert.level}</td>
                  <td>{alert.type || '-'}</td>
                  <td>{alert.status || '-'}</td>
                  <td>{alert.message || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="empty-state">暂无告警记录</div>
      );
    }

    return detailData.auditLogs?.length ? (
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>时间</th>
              <th>操作人</th>
              <th>动作</th>
              <th>结果</th>
              <th>详情</th>
            </tr>
          </thead>
          <tbody>
            {detailData.auditLogs.map((log) => (
              <tr key={log.id}>
                <td>{formatDate(log.createdAt || log.ts)}</td>
                <td>{nameOf(log.operator)}</td>
                <td>{log.action}</td>
                <td>{log.result || '-'}</td>
                <td>{log.detail || '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    ) : (
      <div className="empty-state">暂无审计记录</div>
    );
  }

  function agentFields(agent: AgentSummary) {
    const gpuText = String(agent.gpu ?? '').trim();
    const gpuPart = gpuText && gpuText !== '0' && gpuText !== '-' ? ` / GPU ${formatNumber(agent.gpu)}` : '';

    return [
      metric('运行 instanceId', agent.instanceId),
      metric('部门', agent.department.name),
      metric('负责人', agent.owner.name),
      metric('主模型', agent.primaryModel.name),
      metric('版本', agent.version),
      metric('能力', `${agent.skillCount} Skill / ${agent.knowledgeBaseCount} 知识库`),
      metric('资源', `CPU ${formatNumber(agent.cpu)} / 内存 ${agent.memory}${gpuPart}`),
      metric('服务', `${agent.currentUsers}/${agent.maxUsers} 人 · QPS ${agent.qps}`),
      metric('最近更新', formatDate(agent.updatedAt)),
    ];
  }

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>智能体龙虾管理</h1>
          <p>按后端业务接口统一展示官方 AstronClaw 智能体，支持状态筛选、名称/部门/负责人/模型搜索、完整资源字段、详情分类与生命周期任务。</p>
        </div>
        <div className="head-actions">
          <button className="primary-btn" onClick={() => setCreateOpen(true)} disabled={!canCreate} title={canCreate ? undefined : '缺少 agent.create 权限'}>
            新建智能体
          </button>
        </div>
      </div>

      <div className="four-cols stats-grid">
        <div className="stat-card">
          <span>智能体总数</span>
          <strong>{stats.total}</strong>
          <em>仅官方 AstronClaw</em>
        </div>
        <div className="stat-card">
          <span>运行中</span>
          <strong>{stats.running}</strong>
          <em>正在服务用户</em>
        </div>
        <div className="stat-card">
          <span>异常</span>
          <strong style={{ color: 'var(--danger)' }}>{stats.abnormal}</strong>
          <em>需要诊断处置</em>
        </div>
        <div className="stat-card accent">
          <span>部署/升级中</span>
          <strong>{stats.changing}</strong>
          <em>异步任务执行中</em>
        </div>
      </div>

      <div className="toolbar-card">
        <div className="search-row">
          <input value={keyword} onChange={(event) => updateSearch(event.target.value)} placeholder="按名称、部门、负责人、模型搜索" />
          <Select value={status} onChange={updateStatus} options={STATUS_OPTIONS} placeholder="状态筛选" />
          <Select
            value={String(pageSize)}
            onChange={(value) => {
              setPageSize(Number(value));
              setPage(1);
            }}
            options={[
              { value: '12', label: '12 条/页' },
              { value: '24', label: '24 条/页' },
              { value: '48', label: '48 条/页' },
            ]}
          />
        </div>
        <div className="bulk-actions">
          <button className="ghost-btn small" onClick={() => void runBatch('deploy')} disabled={!canLifecycle}>
            批量部署
          </button>
          <button className="ghost-btn small" onClick={() => void runBatch('start')} disabled={!canLifecycle}>
            批量启动
          </button>
          <button className="ghost-btn small" onClick={() => void runBatch('stop')} disabled={!canLifecycle}>
            批量停止
          </button>
          <button className="ghost-btn small" onClick={() => void runBatch('restart')} disabled={!canLifecycle}>
            批量重启
          </button>
          <button className="ghost-btn small" onClick={() => void runBatch('upgrade')} disabled={!canLifecycle}>
            批量升级
          </button>
        </div>
      </div>

      {apiNotice && <div className="info-banner">{apiNotice}</div>}

      {selectedIds.length > 0 && (
        <div className="bulk-bar">
          <strong>已选择 {selectedIds.length} 个智能体</strong>
          <span className="subtle">{selectedAgents.map((agent) => agent.name).join('、')}</span>
          <div className="bulk-actions">
            <button className="ghost-btn small" onClick={() => void runBatch('archive')} disabled={!canLifecycle}>
              批量归档
            </button>
            <button className="danger-btn small" onClick={() => void runBatch('delete')} disabled={!canDelete}>
              批量删除
            </button>
          </div>
        </div>
      )}

      <div className="toolbar-card" style={{ alignItems: 'center' }}>
        <Checkbox checked={allChecked} indeterminate={someChecked} onChange={toggleAll}>
          选择当前页
        </Checkbox>
        <span className="subtle">
          第 {page} / {pageCount} 页，共 {total} 条
        </span>
        <div className="bulk-actions">
          <button className="ghost-btn small" onClick={() => setPage((value) => Math.max(1, value - 1))} disabled={page <= 1}>
            上一页
          </button>
          <button className="ghost-btn small" onClick={() => setPage((value) => Math.min(pageCount, value + 1))} disabled={page >= pageCount}>
            下一页
          </button>
        </div>
      </div>

      {loading ? (
        <div className="empty-state">正在加载智能体列表...</div>
      ) : rows.length === 0 ? (
        <div className="empty-state">没有匹配的官方智能体</div>
      ) : (
        <div className="card-grid three-cols">
          {rows.map((agent) => (
            <div key={agent.id} className={`entity-card${selectedIds.includes(agent.id) ? ' selected' : ''}`}>
              <div className="entity-head">
                <div>
                  <Checkbox checked={selectedIds.includes(agent.id)} onChange={() => toggleSelected(agent.id)}>
                    <h3>{agent.name}</h3>
                  </Checkbox>
                  <p className="subtle">官方 AstronClaw · botId {agent.botId}</p>
                </div>
                {statusPill(agent.status)}
              </div>
              <div className="summary-metrics">{agentFields(agent)}</div>
              <div className="card-actions">
                <button className="primary-btn small" onClick={() => void openDetail(agent)}>
                  查看详情
                </button>
                {agent.status === 'stopped' ? (
                  <button className="ghost-btn small" onClick={() => void runAgentAction(agent, 'start')} disabled={!canLifecycle}>
                    启动
                  </button>
                ) : (
                  <button className="ghost-btn small" onClick={() => void runAgentAction(agent, 'stop')} disabled={!canLifecycle}>
                    停止
                  </button>
                )}
                <button className="ghost-btn small" onClick={() => void runAgentAction(agent, 'restart')} disabled={!canLifecycle}>
                  重启
                </button>
                <button className="ghost-btn small" onClick={() => void runAgentAction(agent, 'upgrade')} disabled={!canLifecycle}>
                  升级
                </button>
                <button className="ghost-btn small" onClick={() => void runAgentAction(agent, 'deploy')} disabled={!canLifecycle}>
                  部署
                </button>
                <button className="ghost-btn small" onClick={() => void runAgentAction(agent, 'archive')} disabled={!canLifecycle}>
                  归档
                </button>
                <button className="danger-btn small" onClick={() => void runAgentAction(agent, 'delete')} disabled={!canDelete}>
                  删除
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <Modal open={Boolean(detailAgent)} title={detailAgent ? `${detailAgent.name} 实例详情` : '实例详情'} wide onClose={() => setDetailAgent(null)}>
        {detailAgent && (
          <div className="toolbar-card">
            <div className="search-row">
              <Select value={logType} onChange={(value) => setLogType(value as AgentLogType)} options={LOG_TYPE_OPTIONS} placeholder="日志类型" />
              <input value={logKeyword} onChange={(event) => setLogKeyword(event.target.value)} placeholder="日志关键字" />
            </div>
            <div className="bulk-actions">
              <button className="ghost-btn small" onClick={() => void syncCurrentAgent()}>
                手动同步状态
              </button>
              <button className="ghost-btn small" onClick={() => void loadCurrentLogs()} disabled={detailLogsLoading}>
                {detailLogsLoading ? '查询中...' : '查询日志'}
              </button>
            </div>
          </div>
        )}{' '}
        {detailLoading && <div className="info-banner">正在读取 /agents/{'{agentId}'} 详情接口...</div>}
        <div className="tab-group" style={{ marginBottom: 16 }}>
          {DETAIL_TABS.map((tab) => (
            <button key={tab.key} className={`tab${detailTab === tab.key ? ' active' : ''}`} onClick={() => setDetailTab(tab.key)}>
              {tab.label}
            </button>
          ))}
        </div>
        {renderDetailContent()}
      </Modal>

      <Modal
        open={createOpen}
        title="新建智能体"
        wide
        onClose={() => setCreateOpen(false)}
        footer={
          <>
            <button className="ghost-btn" onClick={() => setCreateOpen(false)}>
              取消
            </button>
            <button className="primary-btn" onClick={() => void createAgent()} disabled={creating || !canCreate}>
              {creating ? '提交中...' : '提交创建'}
            </button>
          </>
        }
      >
        <div className="form-grid two-cols">
          <label>
            实例名称
            <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="例如：寿险业务助手" />
          </label>
          <label>
            部门
            <Select value={form.departmentId} onChange={(value) => setForm({ ...form, departmentId: value })} options={departmentOptions} placeholder="选择部门" />
          </label>
          <label>
            负责人
            <Select value={form.ownerId} onChange={(value) => setForm({ ...form, ownerId: value })} options={ownerOptions} placeholder="选择负责人" />
          </label>
          <label>
            主模型
            <Select value={form.primaryModelId} onChange={(value) => setForm({ ...form, primaryModelId: value })} options={modelOptions} placeholder="选择主模型" />
          </label>
          <label>
            备用模型
            <Select value={form.backupModelId} onChange={(value) => setForm({ ...form, backupModelId: value })} options={modelOptions} placeholder="选择备用模型" />
          </label>
          <label>
            CPU
            <input value={form.cpu} onChange={(event) => setForm({ ...form, cpu: event.target.value })} />
          </label>
          <label>
            内存 Gi
            <input value={form.memory} onChange={(event) => setForm({ ...form, memory: event.target.value })} />
          </label>
          <label>
            存储 Gi
            <input value={form.storage} onChange={(event) => setForm({ ...form, storage: event.target.value })} />
          </label>
          <label>
            GPU
            <input value={form.gpu} onChange={(event) => setForm({ ...form, gpu: event.target.value })} placeholder="0 或 GPU 规格" />
          </label>
          <label>
            并发阈值
            <input value={form.concurrencyLimit} onChange={(event) => setForm({ ...form, concurrencyLimit: event.target.value })} />
          </label>
          <label>
            单日调用上限
            <input value={form.dailyCallLimit} onChange={(event) => setForm({ ...form, dailyCallLimit: event.target.value })} />
          </label>
          <label>
            超时阈值 ms
            <input value={form.timeoutMs} onChange={(event) => setForm({ ...form, timeoutMs: event.target.value })} />
          </label>
          <label>
            Skill IDs
            <input value={form.skillIds} onChange={(event) => setForm({ ...form, skillIds: event.target.value })} placeholder="sk001 sk002" />
          </label>
          <label>
            知识库 IDs
            <input value={form.knowledgeBaseIds} onChange={(event) => setForm({ ...form, knowledgeBaseIds: event.target.value })} placeholder="kb001" />
          </label>
          <label>
            记忆策略
            <Select
              value={form.memoryPolicy}
              onChange={(value) => setForm({ ...form, memoryPolicy: value })}
              options={[
                { value: 'personal', label: 'personal' },
                { value: 'department', label: 'department' },
                { value: 'none', label: 'none' },
              ]}
            />
          </label>
          <label>
            消息渠道 IDs
            <input value={form.messageChannelIds} onChange={(event) => setForm({ ...form, messageChannelIds: event.target.value })} placeholder="可留空" />
          </label>
          <label className="full">
            描述
            <textarea value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} placeholder="描述该官方智能体的业务用途" />
          </label>
        </div>
        <div className="success-box">创建请求将按接口文档提交到 POST /agents，类型固定为 astronclaw，不提供非官方创建入口。</div>
      </Modal>
    </div>
  );
}
