import Badge from "./Badge";

export default function PageHeader({ title, subtitle, badges, accentLastWord = true }) {
  let titleContent = title;
  if (accentLastWord && typeof title === "string") {
    const words = title.split(" ");
    if (words.length >= 2) {
      const last = words.pop();
      titleContent = (
        <>
          {words.join(" ")}{" "}
          <em style={{ color: "var(--color-accent)", fontStyle: "italic" }}>{last}</em>
        </>
      );
    }
  }

  return (
    <div className="ck-page-header fade-up">
      {badges && badges.length > 0 && (
        <div className="ck-page-header__badges">
          {badges.map((kind) => (
            <Badge key={kind} kind={kind} />
          ))}
        </div>
      )}
      <h1 className="ck-page-header__title" style={{ fontFamily: "var(--font-display)" }}>
        {titleContent}
      </h1>
      {subtitle && <p className="ck-page-header__subtitle">{subtitle}</p>}
    </div>
  );
}
