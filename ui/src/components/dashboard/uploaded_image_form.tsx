import * as React from "react";
import { useRef } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

interface UploadImageFormProps {
  selectedFile: File | null;
  onFileChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onUpload: () => void;
}

export default function UploadImageForm({
  selectedFile,
  onFileChange,
  onUpload,
}: UploadImageFormProps) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Upload Docker Image (.tar)</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <Input
          type="file"
          accept=".tar"
          onChange={(e) => {
            onFileChange(e);
          }}
          ref={fileInputRef}
        />
        <Button disabled={!selectedFile} onClick={onUpload}>
          Upload
        </Button>
      </CardContent>
    </Card>
  );
}
