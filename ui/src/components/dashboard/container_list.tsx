import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface Container {
  id: string;
  docker_image_id: string;
  status?: string;
  image: string;
  exposed_port?: number;
  created_at: string;
}

interface ContainersListProps {
  containers: Container[];
  startContainer: { mutate: (id: string) => void };
  stopContainer: { mutate: (id: string) => void };
  deleteContainer: { mutate: (id: string) => void };
  viewLogs: (id: string) => void;
  truncate?: (str: string, length?: number) => string;
}

export default function ContainersList({
  containers,
  startContainer,
  stopContainer,
  deleteContainer,
  viewLogs,
  truncate,
}: ContainersListProps) {


    console.log(containers)
  return (
    <div>
      <h2 className="text-2xl font-semibold">Containers</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {containers.map((c) => (
          <Card key={c.id}>
            <CardHeader>
              <CardTitle className="flex justify-between items-center">
                <span title={c.id} className="truncate max-w-[150px]">
                  {truncate ? truncate(c.id) : c.id}
                </span>
                <Badge>{c.status?.toUpperCase() || "UNKNOWN"}</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
            <div title={c.image} className="truncate max-w-full">
                Image: {truncate ? truncate(c.image, 24) : c.image}
            </div>
            <div>Exposed Port: {c.exposed_port || "N/A"}</div>
            <div>Created: {new Date(c.created_at).toLocaleString()}</div>
            <div className="flex gap-2 mt-2 flex-wrap">
                {c.status !== "running" && (
                <Button onClick={() => startContainer.mutate(c.id)}>Start</Button>
                )}
                {c.status === "running" && (
                <Button onClick={() => stopContainer.mutate(c.id)}>Stop</Button>
                )}
                <Button variant="destructive" onClick={() => deleteContainer.mutate(c.id)}>
                Delete
                </Button>
                <Button variant="outline" onClick={() => viewLogs(c.id)}>
                View Logs
                </Button>
            </div>
            </CardContent>
            
          </Card>
        ))}
      </div>
    </div>
  );
}
