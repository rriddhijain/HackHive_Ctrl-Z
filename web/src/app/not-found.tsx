import { Button, EmptyState } from "@/components/m3";
import { Page } from "@/components/shell";

export default function NotFound() {
  return (
    <Page className="py-10">
      <div className="rounded-xl-plus bg-surface-container-low">
        <EmptyState icon="explore_off" title="Page not found" body="This address is not part of the console."
          action={<Button variant="tonal" icon="arrow_back" href="/">Go to the console</Button>} />
      </div>
    </Page>
  );
}
