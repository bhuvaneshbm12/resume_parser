import Link from "next/link";
import { ArrowLeftIcon } from "lucide-react";
import ResultsDisplay from "@/components/ResultsDisplay";
import { Button } from "@/components/ui/button";

type ResultsPageProps = {
  params: {
    taskId: string;
  };
};

export default function ResultsPage({ params }: ResultsPageProps) {
  const taskId = String(params.taskId);

  return (
    <div className="w-full space-y-4">
      <Button asChild variant="ghost" className="pl-0">
        <Link href="/">
          <ArrowLeftIcon />
          Parse another resume
        </Link>
      </Button>
      <ResultsDisplay taskId={taskId} />
    </div>
  );
}
