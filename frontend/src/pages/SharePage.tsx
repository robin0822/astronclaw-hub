import { useEffect, useMemo, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { shareLinksApi } from '../api/share-links';

type SharedAgent = {
  id: string;
  name: string;
  status?: string;
  engine?: string;
  version?: string;
  description?: string;
  department?: string;
  owner?: string;
  primaryModel?: string;
  backupModel?: string;
  createdAt?: string;
  skillNames: string[];
  expiresAt?: string;
};

const STATUS_META: Record<string, { label: string; tag: string }> = {
  running: { label: '运行中', tag: 'success' },
  stopped: { label: '已停止', tag: 'neutral' },
  abnormal: { label: '异常', tag: 'danger' },
  deploying: { label: '部署中', tag: 'info' },
  upgrading: { label: '升级中', tag: 'warning' },
};

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function textOf(value: unknown): string {
  if (!value) return '';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  const record = asRecord(value);
  return textOf(record.name) || textOf(record.label) || textOf(record.id);
}

function listOf(value: unknown) {
  return Array.isArray(value) ? value.map(textOf).filter(Boolean) : [];
}

function normalizePayload(payload: Record<string, unknown>, id: string): SharedAgent {
  const source = asRecord(payload.agent ?? payload.data ?? payload);
  return {
    id: textOf(source.id) || id,
    name: textOf(source.name) || '未命名智能体',
    status: textOf(source.status),
    engine: textOf(source.engine),
    version: textOf(source.version),
    description: textOf(source.description),
    department: textOf(source.department),
    owner: textOf(source.owner),
    primaryModel: textOf(source.primaryModel ?? source.model),
    backupModel: textOf(source.backupModel ?? source.fallbackModel),
    createdAt: textOf(source.createdAt),
    skillNames: listOf(source.skillNames ?? source.skillList ?? source.skills),
    expiresAt: textOf(payload.expiresAt ?? source.expiresAt),
  };
}

function ShareStatus({ status }: { status?: string }) {
  if (!status) return null;
  const meta = STATUS_META[status] ?? { label: status, tag: 'neutral' };
  return <span className={`status-tag ${meta.tag}`}>{meta.label}</span>;
}

export default function SharePage() {
  const { id } = useParams<{ id: string }>();
  const [params] = useSearchParams();
  const token = params.get('token') ?? '';
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [agent, setAgent] = useState<SharedAgent | null>(null);

  useEffect(() => {
    let alive = true;

    async function loadShare() {
      if (!id) {
        setError('分享链接缺少资源 ID');
        setLoading(false);
        return;
      }
      if (!token) {
        setError('分享链接缺少访问令牌，无法校验授权范围');
        setLoading(false);
        return;
      }

      setLoading(true);
      setError('');
      try {
        const payload = await shareLinksApi.get(id, token);
        if (!alive) return;
        setAgent(normalizePayload(payload, id));
      } catch (err) {
        if (!alive) return;
        setAgent(null);
        setError(err instanceof Error ? err.message : '业务后端调用失败');
      } finally {
        if (alive) setLoading(false);
      }
    }

    void loadShare();
    return () => {
      alive = false;
    };
  }, [id, token]);

  const metrics = useMemo(
    () =>
      [
        ['所属部门', agent?.department],
        ['负责人', agent?.owner],
        ['主模型', agent?.primaryModel],
        ['备用模型', agent?.backupModel],
        ['创建时间', agent?.createdAt],
        ['有效期至', agent?.expiresAt],
      ].filter(([, value]) => Boolean(value)),
    [agent],
  );

  if (loading) {
    return (
      <div className="share-page">
        <div className="share-card">
          <div className="share-brand">讯飞 AstronClaw 智能体分享</div>
          <div className="empty-state">正在校验分享授权...</div>
        </div>
      </div>
    );
  }

  if (error || !agent) {
    return (
      <div className="share-page">
        <div className="share-card">
          <div className="share-brand">讯飞 AstronClaw 智能体分享</div>
          <div className="empty-state">
            <h2>分享链接无效或已失效</h2>
            <p className="subtle">{error || '后端未返回可访问的分享资源。链接可能已过期、被撤销或超出授权范围。'}</p>
            <Link className="primary-btn" to="/login" style={{ marginTop: 16, display: 'inline-block' }}>
              登录平台
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="share-page">
      <div className="share-card">
        <div className="share-brand">讯飞 AstronClaw 智能体分享</div>

        <div className="entity-head" style={{ marginTop: 12 }}>
          <h1 style={{ margin: 0 }}>{agent.name}</h1>
          <ShareStatus status={agent.status} />
        </div>

        <p className="meta-tags" style={{ marginTop: 12 }}>
          {agent.engine && <span>{agent.engine}</span>}
          {agent.version && <span>{agent.version}</span>}
          <span>后端授权分享</span>
        </p>

        {agent.description && (
          <p className="subtle" style={{ marginTop: 8 }}>
            {agent.description}
          </p>
        )}

        {metrics.length > 0 && (
          <div className="summary-metrics" style={{ marginTop: 16 }}>
            {metrics.map(([label, value]) => (
              <div key={label}>
                <span>{label}</span>
                <strong>{value}</strong>
              </div>
            ))}
          </div>
        )}

        {agent.skillNames.length > 0 && (
          <>
            <div className="section-title" style={{ marginTop: 20 }}>
              Skill 能力（{agent.skillNames.length}）
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {agent.skillNames.map((skill) => (
                <span key={skill} className="tag-pill">
                  {skill}
                </span>
              ))}
            </div>
          </>
        )}

        <div className="info-banner" style={{ marginTop: 20 }}>
          分享访问已由业务后端校验；如需使用或管理该智能体，请登录 AstronClaw 平台。
        </div>

        <Link className="primary-btn" to="/login" style={{ marginTop: 8, display: 'inline-block' }}>
          登录平台查看更多
        </Link>
      </div>
    </div>
  );
}
