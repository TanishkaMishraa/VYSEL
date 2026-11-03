import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react';
import { cx } from '../cx';
import { Spinner } from './Loading';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'link';
export type ButtonSize = 'sm' | 'md' | 'lg';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  block?: boolean;
  /** Shows a spinner, keeps width, sets aria-busy and blocks clicks. */
  loading?: boolean;
  /** Icon-only button. Requires `aria-label`. */
  iconOnly?: boolean;
  leadingIcon?: ReactNode;
  trailingIcon?: ReactNode;
}

/**
 * Button classes for non-button elements — e.g. a Next.js <Link> that should
 * look like a button: <Link className={buttonClassName({ size: 'lg' })} href="/scan">.
 * Wrap the text in <span className="vy-btn__label"> for identical layout.
 */
export function buttonClassName({ variant = 'primary', size = 'md', block, iconOnly, className }: Pick<ButtonProps, 'variant' | 'size' | 'block' | 'iconOnly' | 'className'> = {}) {
  return cx('vy-btn', `vy-btn--${variant}`, size !== 'md' && `vy-btn--${size}`, block && 'vy-btn--block', iconOnly && 'vy-btn--icon', className);
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'primary', size = 'md', block, loading, iconOnly, leadingIcon, trailingIcon, className, children, disabled, onClick, type = 'button', ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={buttonClassName({ variant, size, block, iconOnly, className })}
      disabled={disabled}
      aria-busy={loading || undefined}
      // aria-disabled (not disabled) while loading keeps focus on the button.
      aria-disabled={loading || undefined}
      onClick={loading ? (e) => e.preventDefault() : onClick}
      {...rest}
    >
      <span className="vy-btn__label">
        {leadingIcon}
        {children}
        {trailingIcon}
      </span>
      {loading && <Spinner label={null} />}
    </button>
  );
});
