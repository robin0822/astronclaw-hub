import { useMemo } from 'react';
import type { AgentStatus } from '../store/types';

export const STATUS_META: Record<AgentStatus, { label: string; tag: string; dot: string }> = {
  draft: { label: '草稿', tag: 'neutral', dot: 'gray' },
  running: { label: '运行中', tag: 'success', dot: 'green' },
  stopped: { label: '已停止', tag: 'neutral', dot: 'gray' },
  abnormal: { label: '异常', tag: 'danger', dot: 'red' },
  deploying: { label: '部署中', tag: 'info', dot: 'blue' },
  upgrading: { label: '升级中', tag: 'warning', dot: 'orange' },
  stopping: { label: '停止中', tag: 'warning', dot: 'orange' },
  archived: { label: '已归档', tag: 'neutral', dot: 'gray' },
  violation_offline: { label: '违规下线', tag: 'danger', dot: 'red' },
};

export function StatusTag({ status }: { status: AgentStatus }) {
  const meta = STATUS_META[status] ?? { label: status || '未知', tag: 'neutral', dot: 'gray' };
  return <span className={`status-tag ${meta.tag}`}>{meta.label}</span>;
}

export function StatusDot({ status }: { status: AgentStatus }) {
  const meta = STATUS_META[status] ?? { dot: 'gray' };
  return <span className={`status-dot ${meta.dot}`} />;
}

export function useBars(seed: number, count = 8) {
  return useMemo(() => {
    const out: number[] = [];
    let nextSeed = seed;
    for (let i = 0; i < count; i += 1) {
      nextSeed = (nextSeed * 9301 + 49297) % 233280;
      out.push(20 + Math.round((nextSeed / 233280) * 70));
    }
    return out;
  }, [seed, count]);
}
