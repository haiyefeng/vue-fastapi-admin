/**
 * 四象限常量（与后端 QuadrantType、前端 design-tokens.scss 同源）
 */
const QUADRANTS = {
  urgent_important: { key: 'urgent_important', label: '重要且紧急', short: '紧急重要', color: '#f5222d' },
  urgent_not_important: { key: 'urgent_not_important', label: '紧急不重要', short: '紧急', color: '#faad14' },
  important_not_urgent: { key: 'important_not_urgent', label: '重要不紧急', short: '重要', color: '#1890ff' },
  not_urgent_not_important: { key: 'not_urgent_not_important', label: '不紧急不重要', short: '其他', color: '#909399' },
};
const QUADRANT_KEYS = Object.keys(QUADRANTS);
const QUADRANT_LIST = QUADRANT_KEYS.map((k) => QUADRANTS[k]);
function quadrantMeta(key) {
  return QUADRANTS[key] || { key: key, label: key, short: key, color: '#909399' };
}
module.exports = { QUADRANTS, QUADRANT_KEYS, QUADRANT_LIST, quadrantMeta };
