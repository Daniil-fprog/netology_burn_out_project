// Палитра B «Бирюзовый» + фиксированные семантические цвета (см. решение от 08.11.2026).
export const colors = {
  primary: '#1F7A6D',
  bg: '#F4F7F6',
  surface: '#FFFFFF',
  text: '#1E2B28',
  muted: '#55625F',
  border: '#DCE5E2',
  soft: '#E3F1EE',
  // 1–5 шкалы самочувствия: оттенки основного цвета, без «светофора» (не диагноз)
  scale: ['#D5EBE7', '#A6D3CB', '#6DB3A7', '#2B8272', '#145A50'],
  plan: '#7A8FB5',
  planText: '#4E6390',
  fact: '#D9822B',
  factText: '#A35A0E',
  factSoft: '#FBEBDC',
  // красный — только ошибки форм/импорта; превышение факта над планом — янтарный
  error: '#C2410C',
  status: {
    not_started: { bg: '#EEF1F0', fg: '#55625F', label: 'Не начат' },
    draft: { bg: '#FEF3C7', fg: '#8A4B08', label: 'Черновик' },
    completed: { bg: '#DCFCE7', fg: '#166534', label: 'Завершён' },
  },
};

export const antTheme = {
  token: {
    colorPrimary: colors.primary,
    colorInfo: colors.primary,
    colorLink: colors.primary,
    colorError: colors.error,
    colorWarning: colors.fact,
    colorText: colors.text,
    colorTextSecondary: colors.muted,
    colorBorder: colors.border,
    colorBorderSecondary: colors.border,
    colorBgLayout: colors.bg,
    fontFamily: "'Golos Text', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
    fontSize: 16,
    borderRadius: 8,
  },
  components: {
    Layout: { siderBg: '#FFFFFF', headerBg: '#FFFFFF', headerHeight: 56, headerPadding: '0 16px' },
    Menu: { itemSelectedBg: colors.soft, itemSelectedColor: colors.primary },
    Card: { paddingLG: 20 },
  },
};
