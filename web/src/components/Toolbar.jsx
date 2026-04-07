const CHIPS = [
  { label: '✍️ Essay',    starter: 'Write an essay about ' },
  { label: '📝 Blog Post', starter: 'Write a blog post about ' },
  { label: '📄 CV',        starter: 'Write a CV for ' },
  { label: '📧 Email',     starter: 'Draft an email to ' },
  { label: '📋 Proposal',  starter: 'Write a business proposal for ' },
  { label: '🌐 Website',   starter: 'Build a website for ' },
];

export function Toolbar({ onChipClick }) {
  return (
    <div className="toolbar">
      {CHIPS.map(c => (
        <button
          key={c.label}
          className="chip"
          onClick={() => onChipClick(c.starter)}
          type="button"
        >
          {c.label}
        </button>
      ))}
    </div>
  );
}
