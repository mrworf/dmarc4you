export function PlaceholderCard({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <section className="surface-card placeholder-grid">
      <article className="placeholder-card">
        <h3 style={{ margin: "0 0 8px" }}>{title}</h3>
        <p className="status-text" style={{ margin: 0 }}>
          {description}
        </p>
      </article>
    </section>
  );
}
