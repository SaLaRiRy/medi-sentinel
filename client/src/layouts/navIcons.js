/**
 * 导航图标（视觉重做 第一阶段）。
 *
 * 无第三方图标依赖：每个条目是一组 24×24 viewBox 的 SVG path，外壳用
 * `<path v-for>` 渲染，`currentColor` 继承文字颜色，深色侧边栏 / 渐变顶栏都适用。
 * 按菜单的 `to` 路径取图，未登记的路径回退到通用圆点。
 */

const ICONS = {
  // 控制台
  '/admin/dashboard': ['M3 3h7v7H3z', 'M14 3h7v7h-7z', 'M14 14h7v7h-7z', 'M3 14h7v7H3z'],
  '/doctor/dashboard': ['M3 3h7v7H3z', 'M14 3h7v7h-7z', 'M14 14h7v7h-7z', 'M3 14h7v7H3z'],
  '/admin/users': [
    'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2',
    'M9 3a4 4 0 1 1 0 8 4 4 0 0 1 0-8',
    'M22 21v-2a4 4 0 0 0-3-3.87',
    'M16 3.13a4 4 0 0 1 0 7.75',
  ],
  '/admin/doctors': [
    'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2',
    'M9 3a4 4 0 1 1 0 8 4 4 0 0 1 0-8',
    'M16 11l2 2 4-4',
  ],
  '/admin/departments': [
    'M3 21h18',
    'M5 21V7l7-4 7 4v14',
    'M9 9h.01',
    'M9 13h.01',
    'M9 17h.01',
    'M15 9h.01',
    'M15 13h.01',
    'M15 17h.01',
  ],
  '/admin/knowledge': [
    'M4 19.5A2.5 2.5 0 0 1 6.5 17H20',
    'M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z',
  ],
  '/admin/graph': [
    'M18 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6z',
    'M6 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z',
    'M18 22a3 3 0 1 0 0-6 3 3 0 0 0 0 6z',
    'M8.6 13.5l6.8 4',
    'M15.4 6.5l-6.8 4',
  ],
  '/admin/consults': ['M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z'],
  '/doctor/consults': ['M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z'],
  '/admin/appointments': ['M3 4h18v18H3z', 'M16 2v4', 'M8 2v4', 'M3 10h18'],
  '/doctor/appointments': ['M3 4h18v18H3z', 'M16 2v4', 'M8 2v4', 'M3 10h18'],
  '/admin/articles': [
    'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z',
    'M14 2v6h6',
    'M16 13H8',
    'M16 17H8',
    'M10 9H8',
  ],
  '/admin/notices': [
    'M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9',
    'M13.73 21a2 2 0 0 1-3.46 0',
  ],
  '/doctor/patients': [
    'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2',
    'M9 3a4 4 0 1 1 0 8 4 4 0 0 1 0-8',
    'M16 11l2 2 4-4',
  ],

  // 患者门户
  '/portal/home': ['M3 9.5L12 3l9 6.5V21a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z'],
  '/portal/chat': ['M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z'],
  '/portal/symptom': ['M22 12h-4l-3 9L9 3l-3 9H2'],
  '/portal/consult': ['M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z'],
  '/portal/appointment': ['M3 4h18v18H3z', 'M16 2v4', 'M8 2v4', 'M3 10h18'],
  '/portal/records': [
    'M9 2h6a1 1 0 0 1 1 1v2H8V3a1 1 0 0 1 1-1z',
    'M8 4H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2h-2',
  ],
  '/portal/articles': [
    'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z',
    'M14 2v6h6',
    'M16 13H8',
    'M16 17H8',
    'M10 9H8',
  ],
}

const FALLBACK = ['M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z']

export function navIcon(to) {
  return ICONS[to] ?? FALLBACK
}
