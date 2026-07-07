import { useCallback, useState, type ReactNode } from 'react';
import type { OpLog } from './types';
import { createEmptyStoreData } from './initial-store-data';
import { StoreContext, nowStamp, type StoreContextValue, type StoreData, type ToastKind } from './store-context';
import { normalizeStoreData } from './store-normalizers';

interface ToastItem {
  id: number;
  msg: string;
  kind: ToastKind;
}

const toastTone: Record<ToastKind, string> = {
  info: 'bg-slate-800',
  success: 'bg-emerald-700',
  danger: 'bg-red-600',
  warning: 'bg-amber-600',
};

const toastIcon: Record<ToastKind, string> = {
  info: 'ℹ',
  success: '✓',
  danger: '✕',
  warning: '!',
};

declare global {
  interface Window {
    /** 仅供 Playwright mock 测试注入稳定业务数据；生产构建不会读取。 */
    __ASTRONCLAW_E2E_STORE__?: StoreData;
  }
}

let toastSeq = 1;

function createInitialStoreData() {
  if (import.meta.env.DEV && typeof window !== 'undefined' && window.__ASTRONCLAW_E2E_STORE__) {
    return window.__ASTRONCLAW_E2E_STORE__;
  }

  return createEmptyStoreData();
}

export function StoreProvider({ children }: { children: ReactNode }) {
  const [data, setData] = useState<StoreData>(() => normalizeStoreData(createInitialStoreData()));
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const update = useCallback((patch: Partial<StoreData> | ((data: StoreData) => Partial<StoreData>)) => {
    setData((prev) => normalizeStoreData({ ...prev, ...(typeof patch === 'function' ? patch(prev) : patch) }));
  }, []);

  const toast = useCallback((msg: string, kind: ToastKind = 'info') => {
    const id = toastSeq++;
    setToasts((items) => [...items, { id, msg, kind }]);
    setTimeout(() => setToasts((items) => items.filter((item) => item.id !== id)), 2800);
  }, []);

  const addOpLog = useCallback((entry: Omit<OpLog, 'id' | 'ts'>) => {
    setData((prev) =>
      normalizeStoreData({
        ...prev,
        opLogs: [{ ...entry, id: `op-${toastSeq++}-${prev.opLogs.length}`, ts: nowStamp() }, ...prev.opLogs],
      }),
    );
  }, []);

  const resetAll = useCallback(() => {
    setData(normalizeStoreData(createEmptyStoreData()));
    toast('已清空本地业务数据', 'info');
  }, [toast]);

  const value: StoreContextValue = { ...data, update, addOpLog, resetAll, toast };

  return (
    <StoreContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed top-5 right-5 z-[9999] flex flex-col gap-2.5">
        {toasts.map((item) => (
          <div
            key={item.id}
            className={`pointer-events-auto flex items-center gap-2.5 rounded-xl px-4 py-3 text-sm text-white shadow-[0_12px_30px_rgba(15,23,42,0.30)] ${toastTone[item.kind]}`}
          >
            <span>{toastIcon[item.kind]}</span>
            {item.msg}
          </div>
        ))}
      </div>
    </StoreContext.Provider>
  );
}
