import { Select as AntSelect } from 'antd';

export interface SelectOption {
  value: string;
  label: string;
  title?: string;
}

interface SelectProps {
  value: string;
  options: SelectOption[];
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
  disabled?: boolean;
}

const DEFAULT_PLACEHOLDER = '\u8bf7\u9009\u62e9';
const EMPTY_DESCRIPTION = '\u6682\u65e0\u6570\u636e';

const emptyContent = <span className="app-select-empty">{EMPTY_DESCRIPTION}</span>;

export default function Select({ value, options, onChange, placeholder = DEFAULT_PLACEHOLDER, className = '', disabled = false }: SelectProps) {
  const hasEmptyOption = options.some((option) => option.value === '');
  const selectValue = value === '' && !hasEmptyOption ? undefined : value;
  const normalizedOptions = options.map((option) => ({ ...option, title: option.title ?? '' }));

  return (
    <AntSelect<string>
      title=""
      value={selectValue}
      options={normalizedOptions}
      onChange={(nextValue) => onChange(nextValue)}
      placeholder={placeholder}
      className={`app-select${className ? ` ${className}` : ''}`}
      classNames={{ popup: { root: 'app-select-dropdown' } }}
      notFoundContent={emptyContent}
      disabled={disabled}
      aria-label={placeholder}
    />
  );
}
