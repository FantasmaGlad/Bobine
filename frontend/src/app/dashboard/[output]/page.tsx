import DashboardScreen from "@/components/DashboardScreen";
import { DEFAULT_OUTPUT, isOutputId, OUTPUTS } from "@/lib/outputs";

export function generateStaticParams() {
  return OUTPUTS.map((output) => ({ output: output.id }));
}

export default async function DashboardOutputPage({ params }: { params: Promise<{ output: string }> }) {
  const { output } = await params;
  return <DashboardScreen channel={isOutputId(output) ? output : DEFAULT_OUTPUT} />;
}
