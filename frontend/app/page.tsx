import UploadForm from "@/components/UploadForm";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function HomePage() {
  return (
    <div className="flex min-h-[70vh] w-full items-center justify-center">
      <Card className="w-full max-w-xl shadow-sm">
        <CardHeader>
          <CardTitle>Upload a resume</CardTitle>
          <p className="text-sm text-slate-600">
            Upload a PDF resume and get structured data in seconds
          </p>
        </CardHeader>
        <CardContent>
          <UploadForm />
        </CardContent>
      </Card>
    </div>
  );
}
