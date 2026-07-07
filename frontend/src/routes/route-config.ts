export type AppRouteIcon = 'agents' | 'org' | 'monitoring' | 'models' | 'security' | 'ops' | 'skills' | 'knowledge' | 'memory' | 'seats' | 'sharing' | 'channels' | 'diagnosis';

export interface AppRouteItem {
  to: string;
  label: string;
  icon: AppRouteIcon;
}

export interface AppRouteSection {
  title: string;
  items: AppRouteItem[];
}

export const APP_SECTIONS: AppRouteSection[] = [
  {
    title: '核心功能',
    items: [
      { to: '/agents', label: '智能体龙虾管理', icon: 'agents' },
      { to: '/org', label: '组织架构', icon: 'org' },
      { to: '/monitoring', label: '监控告警', icon: 'monitoring' },
      { to: '/models', label: '模型网关', icon: 'models' },
      { to: '/security', label: '安全审计', icon: 'security' },
      { to: '/ops', label: '运维自动化', icon: 'ops' },
    ],
  },
  {
    title: '平台能力',
    items: [
      { to: '/skills', label: 'Skill 管理', icon: 'skills' },
      { to: '/knowledge', label: '知识管理', icon: 'knowledge' },
      { to: '/memory', label: '记忆管理', icon: 'memory' },
      { to: '/seats', label: '席位管理', icon: 'seats' },
      { to: '/sharing', label: '实例共享', icon: 'sharing' },
      { to: '/channels', label: '消息渠道', icon: 'channels' },
      { to: '/diagnosis', label: '问题诊断', icon: 'diagnosis' },
    ],
  },
];

const ROUTE_ITEMS = APP_SECTIONS.flatMap((section) => section.items);

export const PAGE_TITLES = ROUTE_ITEMS.reduce<Record<string, string>>((titles, item) => {
  titles[item.to] = item.label;
  return titles;
}, {});
