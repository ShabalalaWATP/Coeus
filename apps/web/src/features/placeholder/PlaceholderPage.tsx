type PlaceholderPageProps = {
  title: string;
  description: string;
};

export default function PlaceholderPage({ title, description }: PlaceholderPageProps) {
  return (
    <section className="surface placeholder-page" aria-labelledby="placeholder-title">
      <div className="section-heading">
        <h1 id="placeholder-title">{title}</h1>
        <p>{description}</p>
      </div>
      <div className="placeholder-page__rule" aria-hidden="true" />
    </section>
  );
}
