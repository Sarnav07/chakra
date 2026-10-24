// OWNER: P4 (stub created by P2 for P3)
import { PageHeader, Notice } from "../ui";

export default function Home() {
  return (
    <>
      <PageHeader title="Home" badges={["simulated"]} />
      <Notice kind="info">Coming soon - owner P4</Notice>
    </>
  );
}
