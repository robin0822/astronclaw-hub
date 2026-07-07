import { useMemo, useState } from 'react';
import { useStore } from '../store/store-context';
import type { Channel } from '../store/types';
import Modal from '../components/Modal';
import Select from '../components/Select';

const CHANNEL_TYPES = ['企业微信', '飞书', '钉钉', '私有IM', 'Astron客户端'];

const STATUS_META: Record<Channel['status'], { label: string; tag: string }> = {
  connected: { label: '已连接', tag: 'success' },
  disconnected: { label: '未连接', tag: 'neutral' },
  error: { label: '异常', tag: 'danger' },
};

const nowShort = () => new Date().toLocaleString('zh-CN', { hour12: false });

const emptyChannel = (firstAgent: string): Omit<Channel, 'id'> => ({
  name: '',
  type: '企业微信',
  status: 'connected',
  boundAgent: firstAgent,
  messages: 0,
  updatedAt: nowShort(),
});

export default function ChannelsPage() {
  const { channels, agents, update, addOpLog, toast } = useStore();
  const [editing, setEditing] = useState<Channel | null>(null);
  const [creating, setCreating] = useState<Omit<Channel, 'id'> | null>(null);
  const agentName = (id: string) => agents.find((a) => a.id === id)?.name || id || '未绑定';

  const totals = useMemo(
    () => ({
      count: channels.length,
      connected: channels.filter((c) => c.status === 'connected').length,
      errors: channels.filter((c) => c.status === 'error').length,
      messages: channels.reduce((s, c) => s + c.messages, 0),
    }),
    [channels],
  );

  function testConn(c: Channel) {
    if (c.status === 'connected') toast(`${c.name} 连接测试通过`, 'success');
    else toast(`${c.name} 连接测试失败，请检查接入配置`, 'danger');
  }

  function reconnect(c: Channel) {
    update((d) => ({ channels: d.channels.map((x) => (x.id === c.id ? { ...x, status: 'connected', updatedAt: nowShort() } : x)) }));
    addOpLog({ operator: 'admin', module: '消息渠道', action: '重连渠道', target: c.name, result: 'success', ip: '10.1.28.16', detail: `${c.type} · 已恢复连接` });
    toast(`${c.name} 已重新连接`, 'success');
  }

  function unbind(c: Channel) {
    update((d) => ({ channels: d.channels.map((x) => (x.id === c.id ? { ...x, status: 'disconnected', updatedAt: nowShort() } : x)) }));
    addOpLog({ operator: 'admin', module: '消息渠道', action: '停用渠道', target: c.name, result: 'success', ip: '10.1.28.16', detail: `${c.type} · 已解绑停用` });
    toast(`${c.name} 已停用`, 'warning');
  }

  function saveChannel() {
    if (editing) {
      if (!editing.name) {
        toast('请填写渠道名称', 'danger');
        return;
      }
      if (!agents.some((a) => a.id === editing.boundAgent)) {
        toast('请选择有效的绑定智能体', 'danger');
        return;
      }
      update((d) => ({ channels: d.channels.map((x) => (x.id === editing.id ? { ...editing, updatedAt: nowShort() } : x)) }));
      addOpLog({
        operator: 'admin',
        module: '消息渠道',
        action: '编辑渠道',
        target: editing.name,
        result: 'success',
        ip: '10.1.28.16',
        detail: `${editing.type} · 绑定 ${agentName(editing.boundAgent)} · ${STATUS_META[editing.status].label}`,
      });
      toast('渠道已更新', 'success');
      setEditing(null);
    } else if (creating) {
      if (!creating.name) {
        toast('请填写渠道名称', 'danger');
        return;
      }
      if (!agents.some((a) => a.id === creating.boundAgent)) {
        toast('请选择有效的绑定智能体', 'danger');
        return;
      }
      const id = `ch-${Date.now().toString().slice(-6)}`;
      update((d) => ({ channels: [...d.channels, { ...creating, messages: 0, status: 'connected', updatedAt: nowShort(), id }] }));
      addOpLog({
        operator: 'admin',
        module: '消息渠道',
        action: '接入渠道',
        target: creating.name,
        result: 'success',
        ip: '10.1.28.16',
        detail: `${creating.type} · 绑定 ${agentName(creating.boundAgent)}`,
      });
      toast('渠道已接入', 'success');
      setCreating(null);
    }
  }

  const ef = editing || creating;
  const setEF = (p: Partial<Channel>) => {
    if (editing) setEditing({ ...editing, ...p });
    else if (creating) setCreating({ ...creating, ...p });
  };

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>消息渠道管理</h1>
          <p>统一接入企业微信 / 飞书 / 钉钉 / 私有 IM / Astron 客户端，绑定智能体对外提供智能体服务。</p>
        </div>
        <div className="head-actions">
          <button className="primary-btn" onClick={() => setCreating(emptyChannel(agents[0]?.id ?? ''))}>
            + 接入渠道
          </button>
        </div>
      </div>

      <div className="four-cols stats-grid">
        <div className="stat-card accent">
          <span>接入渠道数</span>
          <strong>{totals.count}</strong>
          <em>多端统一接入</em>
        </div>
        <div className="stat-card">
          <span>已连接</span>
          <strong>{totals.connected}</strong>
          <em>正常对外服务</em>
        </div>
        <div className="stat-card">
          <span>异常渠道</span>
          <strong>{totals.errors}</strong>
          <em>{totals.errors ? '需尽快处理' : '运行平稳'}</em>
        </div>
        <div className="stat-card">
          <span>今日消息总量</span>
          <strong>{totals.messages.toLocaleString()}</strong>
          <em>全渠道合计</em>
        </div>
      </div>

      <div className="info-banner">渠道接入后可绑定智能体实例，统一管理消息收发与会话路由。支持连接测试、异常重连与按渠道的消息量监控。</div>

      <div className="card-grid three-cols">
        {channels.map((c) => (
          <div className="form-card" key={c.id}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <h3 style={{ margin: 0 }}>{c.name}</h3>
              <span className={`status-tag ${STATUS_META[c.status].tag}`}>{STATUS_META[c.status].label}</span>
            </div>
            <div style={{ margin: '10px 0' }}>
              <span className="tag-pill">{c.type}</span>
            </div>
            <p className="subtle" style={{ margin: '4px 0 0' }}>
              绑定智能体：{agentName(c.boundAgent)}
            </p>
            <p className="subtle" style={{ margin: '4px 0 0' }}>
              今日消息：{c.messages.toLocaleString()}
            </p>
            <p className="subtle" style={{ margin: '4px 0 0' }}>
              更新时间：{c.updatedAt}
            </p>
            <div style={{ marginTop: 14 }}>
              <button className="text-btn" onClick={() => testConn(c)}>
                测试连接
              </button>
              {'　'}
              {c.status !== 'connected' && (
                <>
                  <button className="text-btn" onClick={() => reconnect(c)}>
                    重连
                  </button>
                  {'　'}
                </>
              )}
              <button className="text-btn" onClick={() => setEditing({ ...c })}>
                编辑
              </button>
              {'　'}
              <button className="text-btn danger-text" onClick={() => unbind(c)}>
                停用
              </button>
            </div>
          </div>
        ))}
      </div>

      <div className="table-card">
        <h3 style={{ padding: '18px 20px 0', margin: 0 }}>渠道接入明细</h3>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>渠道名称</th>
                <th>类型</th>
                <th>绑定智能体</th>
                <th>状态</th>
                <th>今日消息</th>
                <th>更新时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {channels.map((c) => (
                <tr key={c.id}>
                  <td>{c.name}</td>
                  <td>
                    <span className="tag-pill">{c.type}</span>
                  </td>
                  <td>{agentName(c.boundAgent)}</td>
                  <td>
                    <span className={`status-tag ${STATUS_META[c.status].tag}`}>{STATUS_META[c.status].label}</span>
                  </td>
                  <td>{c.messages.toLocaleString()}</td>
                  <td>{c.updatedAt}</td>
                  <td>
                    <button className="text-btn" onClick={() => setEditing({ ...c })}>
                      编辑
                    </button>
                    {'　'}
                    {c.status !== 'connected' ? (
                      <button className="text-btn" onClick={() => reconnect(c)}>
                        重连
                      </button>
                    ) : (
                      <button className="text-btn danger-text" onClick={() => unbind(c)}>
                        停用
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <Modal
        open={!!ef}
        title={editing ? `编辑渠道 · ${editing.name}` : '接入消息渠道'}
        onClose={() => {
          setEditing(null);
          setCreating(null);
        }}
        footer={
          <>
            <button
              className="ghost-btn"
              onClick={() => {
                setEditing(null);
                setCreating(null);
              }}
            >
              取消
            </button>
            <button className="primary-btn" onClick={saveChannel}>
              保存
            </button>
          </>
        }
      >
        {ef && (
          <div className="form-grid two-cols">
            <label>
              渠道名称
              <input value={ef.name} onChange={(e) => setEF({ name: e.target.value })} />
            </label>
            <label>
              渠道类型
              <Select value={ef.type} options={CHANNEL_TYPES.map((t) => ({ value: t, label: t }))} onChange={(val) => setEF({ type: val })} />
            </label>
            <label>
              绑定智能体
              <Select value={ef.boundAgent} options={agents.map((a) => ({ value: a.id, label: a.name }))} onChange={(val) => setEF({ boundAgent: val })} />
            </label>
            <label>
              状态
              <Select
                value={ef.status}
                options={[
                  { value: 'connected', label: '已连接' },
                  { value: 'disconnected', label: '未连接' },
                  { value: 'error', label: '异常' },
                ]}
                onChange={(val) => setEF({ status: val as Channel['status'] })}
              />
            </label>
          </div>
        )}
      </Modal>
    </div>
  );
}
