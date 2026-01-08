import * as React from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";

interface UploadedImage {
  id: string;
  filename: string;
  status: string;
}

interface UploadedImagesListProps {
  uploaded: UploadedImage[];
  loadUploadedImage: { mutate: (id: string) => void };
  deleteUploadedImage: { mutate: (id: string) => void };
  truncate?: (str: string, length?: number) => string;
}

export default function UploadedImagesList({
  uploaded,
  loadUploadedImage,
  deleteUploadedImage,
  truncate,
}: UploadedImagesListProps) {
  return (
    <div>
      <h2 className="text-2xl font-semibold">Uploaded Images</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {uploaded.map((img) => (
          <Card key={img.id}>
            <CardHeader>
              <CardTitle className="flex justify-between items-center">
                {truncate ? truncate(img.filename) : img.filename}
                <Badge>{img.status.toUpperCase()}</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              {img.status === "uploaded" && (
                <Button onClick={() => loadUploadedImage.mutate(img.id)}>Load</Button>
              )}
              {img.status === "loading" && <Progress value={50} />}
              <Button variant="destructive" onClick={() => deleteUploadedImage.mutate(img.id)}>
                Delete
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
