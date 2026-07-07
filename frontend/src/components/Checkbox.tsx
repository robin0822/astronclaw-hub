import { Checkbox as AntCheckbox } from 'antd';
import type { CheckboxChangeEvent } from 'antd/es/checkbox';
import type { CSSProperties, ReactNode } from 'react';

interface CheckboxProps {
  checked?: boolean;
  indeterminate?: boolean;
  onChange?: (event: CheckboxChangeEvent) => void;
  children?: ReactNode;
  className?: string;
  style?: CSSProperties;
  disabled?: boolean;
}

export default function Checkbox({ checked = false, indeterminate = false, onChange, children, className = '', style, disabled = false }: CheckboxProps) {
  return (
    <AntCheckbox
      checked={checked}
      indeterminate={indeterminate}
      onChange={onChange ?? (() => undefined)}
      disabled={disabled}
      className={`checkbox-wrapper app-checkbox${className ? ` ${className}` : ''}`}
      style={style}
    >
      {children}
    </AntCheckbox>
  );
}
