import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface DockerImage {
  id: string;
  name: string;
  tag: string;
  is_active: boolean;
  uploaded_image_id: string;
  docker_id: string;
}

interface DockerImagesListProps {
  dockerImages: DockerImage[];
  reloadDockerImage: { mutate: (id: string) => void };
  deleteDockerImage: { mutate: (id: string) => void };
  truncate?: (str: string, length?: number) => string;
}

export default function DockerImagesList({
  dockerImages,
  reloadDockerImage,
  deleteDockerImage,
  truncate,
}: DockerImagesListProps) {
  return (
    <div>
      <h2 className="text-2xl font-semibold">Docker Images</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {dockerImages.map((img, index) => (
          <Card key={img.id}>
            <CardHeader>
              <CardTitle className="flex justify-between items-center">
                {`${img.name || "unknown"}:${img.tag || "latest"} (#${index + 1})`}
                <Badge>{img.is_active ? "ACTIVE" : "INACTIVE"}</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              <div>Uploaded ID: {img.uploaded_image_id}</div>
              <div title={img.docker_id} className="truncate max-w-[200px]">
                Docker ID: {truncate ? truncate(img.docker_id) : img.docker_id}
              </div>
              <div className="flex gap-2 mt-2">
                <Button onClick={() => reloadDockerImage.mutate(img.id)}>Reload</Button>
                <Button variant="destructive" onClick={() => deleteDockerImage.mutate(img.id)}>Delete</Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
