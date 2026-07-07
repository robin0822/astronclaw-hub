import { useEffect, type ReactNode } from 'react';

interface ModalProps {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
}

function findScrollableElement(target: EventTarget | null) {
  let element = target instanceof Element ? target : null;

  while (element && element !== document.body) {
    const { overflowY } = window.getComputedStyle(element);
    const canScrollY = ['auto', 'scroll', 'overlay'].includes(overflowY);
    if (canScrollY && element.scrollHeight > element.clientHeight) return element;
    element = element.parentElement;
  }

  return null;
}

function shouldPreventPageScroll(target: EventTarget | null, deltaY: number) {
  const modal = document.querySelector('.app-modal');
  if (!modal || !(target instanceof Node) || !modal.contains(target)) return true;

  const scrollable = findScrollableElement(target);
  if (!scrollable || !modal.contains(scrollable)) return true;

  const atTop = scrollable.scrollTop <= 0;
  const atBottom = scrollable.scrollTop + scrollable.clientHeight >= scrollable.scrollHeight - 1;
  return (deltaY < 0 && atTop) || (deltaY > 0 && atBottom);
}

export default function Modal({ open, title, onClose, children, footer, wide }: ModalProps) {
  useEffect(() => {
    if (!open) return;

    let touchStartY = 0;

    const handleWheel = (event: WheelEvent) => {
      if (shouldPreventPageScroll(event.target, event.deltaY)) event.preventDefault();
    };

    const handleTouchStart = (event: TouchEvent) => {
      touchStartY = event.touches[0]?.clientY ?? 0;
    };

    const handleTouchMove = (event: TouchEvent) => {
      const touch = event.touches[0];
      if (!touch) return;
      const deltaY = touchStartY - touch.clientY;
      if (shouldPreventPageScroll(event.target, deltaY)) event.preventDefault();
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };

    window.addEventListener('wheel', handleWheel, { passive: false });
    window.addEventListener('touchstart', handleTouchStart, { passive: true });
    window.addEventListener('touchmove', handleTouchMove, { passive: false });
    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('wheel', handleWheel);
      window.removeEventListener('touchstart', handleTouchStart);
      window.removeEventListener('touchmove', handleTouchMove);
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [onClose, open]);

  if (!open) return null;

  return (
    <div className="app-modal-mask" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section className={`app-modal${wide ? ' wide' : ''}`} role="dialog" aria-modal="true" aria-labelledby="app-modal-title">
        <header className="app-modal-header">
          <h2 id="app-modal-title">{title}</h2>
          <button type="button" className="app-modal-close" aria-label="关闭" onClick={onClose}>
            ×
          </button>
        </header>
        <div className="app-modal-body">{children}</div>
        {footer && <footer className="app-modal-footer">{footer}</footer>}
      </section>
    </div>
  );
}
