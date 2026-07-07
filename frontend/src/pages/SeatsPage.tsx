import { useMemo, useState } from 'react';
import { useStore } from '../store/store-context';
import type { Seat } from '../store/types';
import Modal from '../components/Modal';

const today = () => new Date().toISOString().slice(0, 10);

const emptySeat = (): Omit<Seat, 'id'> => ({
  pkg: '',
  dept: '科技研发中心',
  total: 100,
  used: 0,
  expireAt: today(),
});

const safeSeatTotal = (value: unknown) => Math.max(0, Math.round(Number(value) || 0));

export default function SeatsPage() {
  const { seats, update, addOpLog, toast } = useStore();
  const [editing, setEditing] = useState<Seat | null>(null);
  const [creating, setCreating] = useState<Omit<Seat, 'id'> | null>(null);

  const totals = useMemo(() => {
    const total = seats.reduce((s, x) => s + x.total, 0);
    const used = seats.reduce((s, x) => s + x.used, 0);
    const rate = total ? Math.round((used / total) * 100) : 0;
    return { total, used, remain: total - used, rate };
  }, [seats]);

  function expand(seat: Seat) {
    update((d) => ({ seats: d.seats.map((s) => (s.id === seat.id ? { ...s, total: s.total + 50 } : s)) }));
    addOpLog({
      operator: 'admin',
      module: '席位管理',
      action: '扩容席位包',
      target: seat.pkg,
      result: 'success',
      ip: '10.1.28.16',
      detail: `总席位 ${seat.total} → ${seat.total + 50}`,
    });
    toast(`${seat.pkg} 已扩容 50 席`, 'success');
  }

  function recycle(seat: Seat) {
    const next = Math.max(0, seat.used - 10);
    update((d) => ({ seats: d.seats.map((s) => (s.id === seat.id ? { ...s, used: next } : s)) }));
    addOpLog({ operator: 'admin', module: '席位管理', action: '回收席位', target: seat.pkg, result: 'success', ip: '10.1.28.16', detail: `已分配 ${seat.used} → ${next}` });
    toast(`${seat.pkg} 已回收 ${seat.used - next} 席`, 'info');
  }

  function saveSeat() {
    if (editing) {
      if (!editing.pkg) {
        toast('请填写套餐名称', 'danger');
        return;
      }
      const total = safeSeatTotal(editing.total);
      if (total < 1) {
        toast('总席位数必须大于 0', 'danger');
        return;
      }
      if (total < editing.used) {
        toast(`总席位不能小于已分配席位 ${editing.used}`, 'danger');
        return;
      }
      const next = { ...editing, total };
      update((d) => ({ seats: d.seats.map((s) => (s.id === next.id ? next : s)) }));
      addOpLog({
        operator: 'admin',
        module: '席位管理',
        action: '编辑席位包',
        target: next.pkg,
        result: 'success',
        ip: '10.1.28.16',
        detail: `${next.dept} · 总席位 ${next.total} · 到期 ${next.expireAt}`,
      });
      toast('席位包已更新', 'success');
      setEditing(null);
    } else if (creating) {
      if (!creating.pkg) {
        toast('请填写套餐名称', 'danger');
        return;
      }
      const total = safeSeatTotal(creating.total);
      if (total < 1) {
        toast('总席位数必须大于 0', 'danger');
        return;
      }
      const id = `seat-${Date.now().toString().slice(-6)}`;
      update((d) => ({ seats: [...d.seats, { ...creating, total, used: 0, id }] }));
      addOpLog({
        operator: 'admin',
        module: '席位管理',
        action: '新增席位包',
        target: creating.pkg,
        result: 'success',
        ip: '10.1.28.16',
        detail: `${creating.dept} · 总席位 ${total} · 到期 ${creating.expireAt}`,
      });
      toast('席位包已创建', 'success');
      setCreating(null);
    }
  }

  const ef = editing || creating;
  const setEF = (p: Partial<Seat>) => {
    if (editing) setEditing({ ...editing, ...p });
    else if (creating) setCreating({ ...creating, ...p });
  };

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>席位管理</h1>
          <p>统一管理智能体平台的席位授权与额度管控，支持按套餐包分配、按部门核算与到期续期。</p>
        </div>
        <div className="head-actions">
          <button className="primary-btn" onClick={() => setCreating(emptySeat())}>
            + 新增席位包
          </button>
        </div>
      </div>

      <div className="four-cols stats-grid">
        <div className="stat-card accent">
          <span>席位包总数</span>
          <strong>{seats.length}</strong>
          <em>覆盖多部门</em>
        </div>
        <div className="stat-card">
          <span>总席位数</span>
          <strong>{totals.total.toLocaleString()}</strong>
          <em>授权额度合计</em>
        </div>
        <div className="stat-card">
          <span>已分配</span>
          <strong>{totals.used.toLocaleString()}</strong>
          <em>使用率 {totals.rate}%</em>
        </div>
        <div className="stat-card">
          <span>剩余席位</span>
          <strong>{totals.remain.toLocaleString()}</strong>
          <em>{totals.rate > 85 ? '额度紧张' : '额度充足'}</em>
        </div>
      </div>

      <div className="info-banner">席位按套餐包管理，支持按部门分配与到期管理。临近到期或使用率超过 85% 的套餐包将以橙色高亮提示，建议及时扩容或回收。</div>

      <div className="card-grid three-cols">
        {seats.map((s) => {
          const pct = s.total ? Math.round((s.used / s.total) * 100) : 0;
          const high = s.total ? s.used / s.total > 0.85 : false;
          return (
            <div className="form-card" key={s.id}>
              <h3>{s.pkg}</h3>
              <div style={{ marginBottom: 12 }}>
                <span className="tag-pill">{s.dept}</span>
              </div>
              <div className={`progress${high ? ' orange' : ' green'}`}>
                <i style={{ width: `${Math.min(100, pct)}%` }} />
              </div>
              <p className="subtle" style={{ margin: '6px 0 0' }}>
                已用 {s.used} / 总 {s.total}（{pct}%）
              </p>
              <p className="subtle" style={{ margin: '4px 0 0' }}>
                到期时间：{s.expireAt}
              </p>
              <div style={{ marginTop: 14 }}>
                <button className="text-btn" onClick={() => expand(s)}>
                  扩容
                </button>
                {'　'}
                <button className="text-btn danger-text" onClick={() => recycle(s)}>
                  回收
                </button>
                {'　'}
                <button className="text-btn" onClick={() => setEditing({ ...s })}>
                  编辑
                </button>
              </div>
            </div>
          );
        })}
      </div>

      <div className="table-card">
        <h3 style={{ padding: '18px 20px 0', margin: 0 }}>席位分配明细</h3>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>套餐包</th>
                <th>适用部门</th>
                <th>总席位</th>
                <th>已分配</th>
                <th>使用率</th>
                <th>到期时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {seats.map((s) => {
                const pct = s.total ? Math.round((s.used / s.total) * 100) : 0;
                const high = s.total ? s.used / s.total > 0.85 : false;
                return (
                  <tr key={s.id}>
                    <td>{s.pkg}</td>
                    <td>
                      <span className="tag-pill">{s.dept}</span>
                    </td>
                    <td>{s.total}</td>
                    <td>{s.used}</td>
                    <td style={{ minWidth: 140 }}>
                      <div className={`progress${high ? ' orange' : ' green'}`}>
                        <i style={{ width: `${Math.min(100, pct)}%` }} />
                      </div>
                      <span className="subtle">{pct}%</span>
                    </td>
                    <td>{s.expireAt}</td>
                    <td>
                      <button className="text-btn" onClick={() => setEditing({ ...s })}>
                        编辑
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <Modal
        open={!!ef}
        title={editing ? `编辑席位包 · ${editing.pkg}` : '新增席位包'}
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
            <button className="primary-btn" onClick={saveSeat}>
              保存
            </button>
          </>
        }
      >
        {ef && (
          <div className="form-grid two-cols">
            <label>
              套餐名称
              <input value={ef.pkg} onChange={(e) => setEF({ pkg: e.target.value })} />
            </label>
            <label>
              适用部门
              <input value={ef.dept} onChange={(e) => setEF({ dept: e.target.value })} />
            </label>
            <label>
              总席位数
              <input type="number" min="1" step="1" value={ef.total} onChange={(e) => setEF({ total: safeSeatTotal(e.target.value) })} />
            </label>
            <label>
              到期时间
              <input type="date" value={ef.expireAt} onChange={(e) => setEF({ expireAt: e.target.value })} />
            </label>
          </div>
        )}
      </Modal>
    </div>
  );
}
