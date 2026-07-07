import { MoonOutlined, SunOutlined } from '@ant-design/icons';
import { useTheme } from '../theme/theme-store';

interface ThemeToggleProps {
  className?: string;
}

export default function ThemeToggle({ className = '' }: ThemeToggleProps) {
  const { isDark, toggleTheme } = useTheme();
  const nextThemeLabel = isDark ? '浅色模式' : '深色模式';

  return (
    <button
      type="button"
      className={`theme-toggle${isDark ? ' is-dark' : ''}${className ? ` ${className}` : ''}`}
      onClick={toggleTheme}
      aria-label={`切换到${nextThemeLabel}`}
      title={`切换到${nextThemeLabel}`}
    >
      <span className="theme-toggle-icon" aria-hidden="true">
        {isDark ? <SunOutlined /> : <MoonOutlined />}
      </span>
    </button>
  );
}
