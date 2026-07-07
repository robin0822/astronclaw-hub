import { useMemo, useState } from 'react';
import { useStore } from '../store/store-context';
import { confirmDangerousAction } from '../utils';
import type { Knowledge } from '../store/types';
import Modal from '../components/Modal';
import Select from '../components/Select';

const SHARE_META: Record<Knowledge['shareStatus'], { label: string; tag: string }> = {
  shared: { label: '已共享', tag: 'success' },
  pending: { label: '待审批共享', tag: 'warning' },
  private: { label: '私有', tag: 'neutral' },
};

const LEVEL_FILTERS = ['全部', '个人记忆', '组织记忆', '企业记忆'];
const FORM_LEVELS = ['个人记忆', '组织记忆', '企业记忆'];

const today = () => new Date().toISOString().slice(0, 10);

interface DraftKnowledge {
  title: string;
  level: string;
  owner: string;
  tags: string;
  content: string;
}

const emptyDraft = (): DraftKnowledge => ({ title: '', level: '个人记忆', owner: '平台管理员', tags: '', content: '' });

export default function MemoryPage() {
  const { knowledge, update, addOpLog, toast } = useStore();
  const [search, setSearch] = useState('');
  const [level, setLevel] = useState('全部');
  const [draft, setDraft] = useState<DraftKnowledge | null>(null);
  const [viewing, setViewing] = useState<Knowledge | null>(null);

  const filtered = useMemo(() => {
    const kw = search.trim().toLowerCase();
    return knowledge.filter((k) => {
      if (level !== '全部' && k.level !== level) return false;
      if (kw && !`${k.title} ${k.owner} ${k.tags.join(' ')}`.toLowerCase().includes(kw)) return false;
      return true;
    });
  }, [knowledge, search, level]);

  const stats = useMemo(
    () => ({
      total: knowledge.length,
      shared: knowledge.filter((k) => k.shareStatus === 'shared').length,
      pending: knowledge.filter((k) => k.shareStatus === 'pending').length,
      refs: knowledge.reduce((sum, k) => sum + k.refs, 0),
    }),
    [knowledge],
  );

  function approveShare(k: Knowledge) {
    if (k.shareStatus !== 'pending') return;
    update((d) => ({ knowledge: d.knowledge.map((x) => (x.id === k.id ? { ...x, shareStatus: 'shared', updatedAt: today() } : x)) }));
    addOpLog({ operator: '平台管理员', module: '记忆管理', action: '审批共享', target: k.title, result: 'success', ip: '10.1.28.16', detail: `${k.level} · 审批通过` });
    toast(`${k.title} 已批准共享`, 'success');
  }

  function removeKnowledge(k: Knowledge) {
    if (!confirmDangerousAction(`确认删除记忆「${k.title}」？该操作会影响后续引用和共享状态。`)) return;
    update((d) => ({ knowledge: d.knowledge.filter((x) => x.id !== k.id) }));
    addOpLog({ operator: '平台管理员', module: '记忆管理', action: '删除记忆', target: k.title, result: 'success', ip: '10.1.28.16', detail: `${k.level} · 已移除` });
    toast(`${k.title} 已删除`, 'danger');
  }

  function createKnowledge() {
    if (!draft) return;
    if (!draft.title.trim()) {
      toast('请填写记忆标题', 'danger');
      return;
    }
    const id = `kn-${Date.now().toString().slice(-6)}`;
    const item: Knowledge = {
      id,
      title: draft.title.trim(),
      level: draft.level,
      owner: draft.owner.trim() || '平台管理员',
      tags: draft.tags
        .split(/[,，]/)
        .map((t) => t.trim())
        .filter(Boolean),
      refs: 0,
      updatedAt: today(),
      shareStatus: 'private',
    };
    update((d) => ({ knowledge: [item, ...d.knowledge] }));
    addOpLog({ operator: '平台管理员', module: '记忆管理', action: '新建记忆', target: item.title, result: 'success', ip: '10.1.28.16', detail: `${item.level} · 私有` });
    toast('记忆已创建', 'success');
    setDraft(null);
  }

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>记忆管理</h1>
          <p>记忆作为企业资产沉淀，经授权审批后在个人 / 组织 / 企业层级共享复用，让智能体越用越懂业务。</p>
        </div>
        <div className="head-actions">
          <button className="primary-btn" onClick={() => setDraft(emptyDraft())}>
            + 新建记忆
          </button>
        </div>
      </div>

      <div className="info-banner">
        记忆分级：会话记忆（单次对话临时上下文）→ 个人记忆 user.md（个人偏好与习惯）→ 组织记忆 org.md（部门知识沉淀）→ 企业记忆 global.md（全公司共享资产）。逐级共享需经授权审批。
      </div>

      <div className="four-cols stats-grid">
        <div className="stat-card accent">
          <span>记忆总数</span>
          <strong>{stats.total}</strong>
          <em>四级记忆合计</em>
        </div>
        <div className="stat-card">
          <span>已共享数</span>
          <strong>{stats.shared}</strong>
          <em>跨层级复用中</em>
        </div>
        <div className="stat-card">
          <span>待审批共享数</span>
          <strong>{stats.pending}</strong>
          <em>等待管理员审批</em>
        </div>
        <div className="stat-card">
          <span>总引用次数</span>
          <strong>{stats.refs}</strong>
          <em>被智能体累计引用</em>
        </div>
      </div>

      <div className="card-grid two-cols">
        <div className="form-card" style={{ borderLeft: '6px solid #1494e8' }}>
          <h3>会话记忆</h3>
          <ul>
            <li>单次对话临时上下文</li>
            <li>会话结束自动清理</li>
            <li>不进入长期资产库</li>
          </ul>
        </div>
        <div className="form-card" style={{ borderLeft: '6px solid #2bb3ff' }}>
          <h3>个人记忆 user.md</h3>
          <ul>
            <li>沉淀个人偏好与习惯</li>
            <li>仅本人智能体可读取</li>
            <li>可申请上升为组织记忆</li>
          </ul>
        </div>
        <div className="form-card" style={{ borderLeft: '6px solid #7879ff' }}>
          <h3>组织记忆 org.md</h3>
          <ul>
            <li>部门级知识与规范沉淀</li>
            <li>组织内智能体共享复用</li>
            <li>需部门负责人审批</li>
          </ul>
        </div>
        <div className="form-card" style={{ borderLeft: '6px solid #4f59ff' }}>
          <h3>企业记忆 global.md</h3>
          <ul>
            <li>全公司共享知识资产</li>
            <li>全量智能体可引用</li>
            <li>需平台管理员审批发布</li>
          </ul>
        </div>
      </div>

      <div className="toolbar-card">
        <div className="search-row">
          <input placeholder="搜索记忆标题 / 所有者 / 标签…" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <div className="chip-group">
          {LEVEL_FILTERS.map((l) => (
            <button key={l} className={`chip${level === l ? ' active' : ''}`} onClick={() => setLevel(l)}>
              {l}
            </button>
          ))}
        </div>
      </div>

      <div className="table-card">
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>记忆标题</th>
                <th>层级</th>
                <th>所有者</th>
                <th>标签</th>
                <th>引用次数</th>
                <th>更新时间</th>
                <th>共享状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((k) => (
                <tr key={k.id}>
                  <td>{k.title}</td>
                  <td>
                    <span className="tag-pill">{k.level}</span>
                  </td>
                  <td>{k.owner}</td>
                  <td>
                    {k.tags.map((t) => (
                      <span key={t} className="tag-pill">
                        {t}
                      </span>
                    ))}
                  </td>
                  <td>{k.refs}</td>
                  <td className="subtle">{k.updatedAt}</td>
                  <td>
                    <span className={`status-tag ${SHARE_META[k.shareStatus].tag}`}>{SHARE_META[k.shareStatus].label}</span>
                  </td>
                  <td>
                    <button className="text-btn" onClick={() => setViewing(k)}>
                      查看
                    </button>
                    {'　'}
                    {k.shareStatus === 'pending' ? (
                      <button className="text-btn" onClick={() => approveShare(k)}>
                        共享审批
                      </button>
                    ) : k.shareStatus === 'shared' ? (
                      <button className="text-btn" disabled style={{ opacity: 0.5, cursor: 'default' }}>
                        已共享
                      </button>
                    ) : (
                      <button className="text-btn" disabled style={{ opacity: 0.5, cursor: 'default' }}>
                        私有
                      </button>
                    )}
                    {'　'}
                    <button className="text-btn danger-text" onClick={() => removeKnowledge(k)}>
                      删除
                    </button>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={8} className="subtle" style={{ textAlign: 'center', padding: '28px 0' }}>
                    没有匹配的记忆
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <Modal
        open={!!draft}
        title="新建记忆"
        wide
        onClose={() => setDraft(null)}
        footer={
          <>
            <button className="ghost-btn" onClick={() => setDraft(null)}>
              取消
            </button>
            <button className="primary-btn" onClick={createKnowledge}>
              保存
            </button>
          </>
        }
      >
        {draft && (
          <>
            <div className="info-banner">新建记忆默认为私有状态，如需在组织或企业层级共享，请在创建后发起共享审批。</div>
            <div className="form-grid two-cols">
              <label>
                标题
                <input value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} placeholder="如：合同评审要点清单" />
              </label>
              <label>
                层级
                <Select value={draft.level} options={FORM_LEVELS.map((l) => ({ value: l, label: l }))} onChange={(val) => setDraft({ ...draft, level: val })} />
              </label>
              <label>
                所有者
                <input value={draft.owner} onChange={(e) => setDraft({ ...draft, owner: e.target.value })} />
              </label>
              <label>
                标签（逗号分隔）
                <input value={draft.tags} onChange={(e) => setDraft({ ...draft, tags: e.target.value })} placeholder="法务, 合同, 风控" />
              </label>
              <label className="full">
                内容
                <textarea rows={4} value={draft.content} onChange={(e) => setDraft({ ...draft, content: e.target.value })} placeholder="记录该条记忆的具体内容与适用场景" />
              </label>
            </div>
          </>
        )}
      </Modal>

      <Modal
        open={!!viewing}
        title={viewing ? `记忆详情 · ${viewing.title}` : '记忆详情'}
        wide
        onClose={() => setViewing(null)}
        footer={
          <button className="ghost-btn" onClick={() => setViewing(null)}>
            关闭
          </button>
        }
      >
        {viewing && (
          <>
            <div className="form-grid two-cols">
              <label>
                标题
                <input value={viewing.title} readOnly />
              </label>
              <label>
                层级
                <input value={viewing.level} readOnly />
              </label>
              <label>
                所有者
                <input value={viewing.owner} readOnly />
              </label>
              <label>
                共享状态
                <input value={SHARE_META[viewing.shareStatus].label} readOnly />
              </label>
              <label className="full">
                标签
                <div style={{ marginTop: 6 }}>
                  {viewing.tags.length ? (
                    viewing.tags.map((t) => (
                      <span key={t} className="tag-pill">
                        {t}
                      </span>
                    ))
                  ) : (
                    <span className="subtle">无标签</span>
                  )}
                </div>
              </label>
            </div>
            <h4 className="section-title">引用与版本概览</h4>
            <div className="summary-metrics">
              <div>
                <span>累计引用次数</span>
                <strong>{viewing.refs}</strong>
              </div>
              <div>
                <span>引用实例数</span>
                <strong>{Math.max(1, Math.round(viewing.refs / 6))}</strong>
              </div>
              <div>
                <span>版本记录</span>
                <strong>{Math.max(1, Math.round(viewing.refs / 20) + 1)}</strong>
              </div>
              <div>
                <span>最近更新</span>
                <strong>{viewing.updatedAt}</strong>
              </div>
            </div>
          </>
        )}
      </Modal>
    </div>
  );
}
