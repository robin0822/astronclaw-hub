import type { StoreData } from './store-context';

/**
 * 构造前端本地 store 的空数据。
 *
 * 这里不放演示数据，只保留页面运行所需的最小结构；
 * 后续真正接入后端后，各页面应通过 API 拉取并写入 store。
 */
export function createEmptyStoreData(): StoreData {
  return {
    agents: [],
    departments: [],
    members: [],
    roles: [],
    opLogs: [],
    models: [],
    alerts: [],
    skills: [],
    knowledge: [],
    knowledgeFiles: [],
    seats: [],
    securityPolicies: [],
    channels: [],
    inspection: {
      id: 'empty',
      ts: '—',
      scope: '未连接业务后端',
      total: 0,
      pass: 0,
      warn: 0,
      fail: 0,
      items: [],
    },
  };
}
