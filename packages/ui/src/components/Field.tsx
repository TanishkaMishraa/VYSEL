'use client';

import {
  cloneElement,
  forwardRef,
  isValidElement,
  useId,
  type InputHTMLAttributes,
  type ReactElement,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from 'react';
import { cx } from '../cx';
import { Icon } from './Icon';

export interface FieldProps {
  label: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  optional?: boolean;
  /** A single Input, Textarea or Select. Field wires id, aria-describedby and aria-invalid. */
  children: ReactElement;
  className?: string;
}

/** Label + control + hint/error, with all accessibility wiring done for you. */
export function Field({ label, hint, error, optional, children, className }: FieldProps) {
  const autoId = useId();
  const id = (isValidElement<{ id?: string }>(children) && children.props.id) || autoId;
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(' ') || undefined;

  return (
    <div className={cx('vy-field', className)}>
      <label className="vy-label" htmlFor={id}>
        {label}
        {optional && <span className="vy-label__optional"> (optional)</span>}
      </label>
      {cloneElement(children as ReactElement<Record<string, unknown>>, {
        id,
        'aria-describedby': describedBy,
        'aria-invalid': error ? true : undefined,
      })}
      {hint && (
        <p className="vy-hint" id={hintId}>
          {hint}
        </p>
      )}
      {error && (
        <p className="vy-field__error" id={errorId}>
          <Icon name="alert" />
          {error}
        </p>
      )}
    </div>
  );
}

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  startAdornment?: ReactNode;
  endAdornment?: ReactNode;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input({ className, startAdornment, endAdornment, ...rest }, ref) {
  const input = <input ref={ref} className={cx('vy-input', className)} {...rest} />;
  if (!startAdornment && !endAdornment) return input;
  return (
    <div className="vy-input-group">
      {startAdornment && <span className="vy-input-group__affix vy-input-group__affix--start">{startAdornment}</span>}
      {input}
      {endAdornment && <span className="vy-input-group__affix vy-input-group__affix--end">{endAdornment}</span>}
    </div>
  );
});

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(function Textarea({ className, ...rest }, ref) {
  return <textarea ref={ref} className={cx('vy-textarea', className)} {...rest} />;
});

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  options: SelectOption[];
  placeholder?: string;
}

/** Native select: keyboard, screen-reader and mobile-picker support for free. */
export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select({ options, placeholder, className, ...rest }, ref) {
  return (
    <div className={cx('vy-select', className)}>
      <select ref={ref} className="vy-select__control" {...rest}>
        {placeholder && (
          <option value="" disabled>
            {placeholder}
          </option>
        )}
        {options.map((o) => (
          <option key={o.value} value={o.value} disabled={o.disabled}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
});

export interface ChoiceChipsProps {
  /** Visible group label (rendered as the fieldset legend). */
  legend: ReactNode;
  name: string;
  options: SelectOption[];
  /** Single value for radio mode; array for multiple. */
  value: string | string[];
  onChange: (value: string | string[]) => void;
  multiple?: boolean;
}

/** Pill-shaped radio/checkbox group — for preferences like budget and style. */
export function ChoiceChips({ legend, name, options, value, onChange, multiple }: ChoiceChipsProps) {
  const selected = Array.isArray(value) ? value : [value];
  return (
    <fieldset className="vy-field">
      <legend className="vy-label">{legend}</legend>
      <div className="vy-chips">
        {options.map((o) => (
          <label key={o.value} className="vy-chip">
            <input
              type={multiple ? 'checkbox' : 'radio'}
              name={name}
              value={o.value}
              disabled={o.disabled}
              checked={selected.includes(o.value)}
              onChange={(e) => {
                if (!multiple) return onChange(o.value);
                onChange(e.target.checked ? [...selected, o.value] : selected.filter((v) => v !== o.value));
              }}
            />
            <span>{o.label}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
