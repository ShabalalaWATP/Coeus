import {
  Database,
  FileStack,
  FileText,
  Globe2,
  Package,
  RadioTower,
  Satellite,
  ScrollText,
  type LucideIcon,
} from "lucide-react";

const icons: Record<string, LucideIcon> = {
  assessment_report: ScrollText,
  intelligence_summary: FileText,
  satellite_imagery_product: Satellite,
  sigint_mock: RadioTower,
  geographic_product: Globe2,
  database_extract: Database,
  product_bundle: Package,
  finished_output: FileStack,
};

type ProductTypeIconProps = {
  productType: string;
  size?: number;
};

export function ProductTypeIcon({ productType, size = 18 }: ProductTypeIconProps) {
  const Icon = icons[productType] ?? FileText;
  return <Icon aria-hidden="true" size={size} strokeWidth={1.8} />;
}
