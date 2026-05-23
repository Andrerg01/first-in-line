const sectionStyle = {
  maxWidth: "720px",
  margin: "40px auto",
  padding: "24px",
  fontFamily: "Georgia, 'Times New Roman', serif",
  lineHeight: 1.5,
};

const badgeStyle = {
  display: "inline-block",
  padding: "6px 10px",
  background: "#e9f7ef",
  border: "1px solid #9fd2b2",
  borderRadius: "999px",
  marginBottom: "12px",
};

export default function App() {
  return (
    <main style={sectionStyle}>
      <span style={badgeStyle}>Phase 0 Placeholder</span>
      <h1>Grand Opening Radar</h1>
      <p>
        Frontend scaffold is running. Next steps are event list, event detail,
        and admin ingestion views.
      </p>
    </main>
  );
}
