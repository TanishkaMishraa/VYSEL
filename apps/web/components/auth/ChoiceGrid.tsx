'use client';

import { Icon } from '@vysel/ui';
import type { Option } from '@/lib/preferences';

type Props<T extends string> = {
  legend: string;
  hint?: string;
  name: string;
  options: Option<T>[];
} & ({ multiple: true; value: T[]; onChange: (v: T[]) => void } | { multiple?: false; value: T | null; onChange: (v: T) => void });

/**
 * Card-style choices built on native checkboxes/radios inside a fieldset, so keyboard
 * (Tab/Space, arrow keys for radios) and screen readers work without extra ARIA.
 */
export function ChoiceGrid<T extends string>(props: Props<T>) {
  const { legend, hint, name, options } = props;
  const selected = (v: T) => (props.multiple ? props.value.includes(v) : props.value === v);
  const toggle = (v: T) => {
    if (props.multiple) props.onChange(props.value.includes(v) ? props.value.filter((x) => x !== v) : [...props.value, v]);
    else props.onChange(v);
  };

  return (
    <fieldset className="au-choices">
      <legend className="vy-label">{legend}</legend>
      {hint && <p className="vy-hint">{hint}</p>}
      <div className="au-choices__grid">
        {options.map((o) => (
          <label key={o.value} className="au-choice" data-selected={selected(o.value)}>
            <input type={props.multiple ? 'checkbox' : 'radio'} name={name} value={o.value} checked={selected(o.value)} onChange={() => toggle(o.value)} />
            <span className="au-choice__mark" aria-hidden="true">
              <Icon name="check" />
            </span>
            <span className="au-choice__text">
              <span className="au-choice__label">{o.label}</span>
              {o.description && <span className="au-choice__desc">{o.description}</span>}
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
