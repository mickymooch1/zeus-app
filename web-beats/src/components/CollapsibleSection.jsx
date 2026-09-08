import { useState } from 'react';

export default function CollapsibleSection({ title, defaultOpen = false, children }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        style={{
          width: '100%',
          textAlign: 'left',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          padding: '8px 0',
          fontWeight: 600,
        }}
        aria-expanded={open}
      >
        {title} {open ? '▲' : '▼'}
      </button>
      {open && <div>{children}</div>}
    </div>
  );
}
