import * as React from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

export interface ContainerForm {
  image: string;
  image_id: string;
  cpu_limit: number;
  memory_limit_mb: number;
  internal_port: number;
  host_port: number;
}

interface CreateContainerFormProps {
  form: ContainerForm;
  setForm: React.Dispatch<React.SetStateAction<ContainerForm>>;
  dockerImages: any[];
  onSubmit: () => void;
}

export default function CreateContainerForm({
  form,
  setForm,
  dockerImages,
  onSubmit,
}: CreateContainerFormProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Create Container</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <label className="font-semibold">Select Docker Image</label>
        <select
          className="border rounded px-2 py-1 bg-white text-black"
          value={form.image_id || ""}
          onChange={(e) =>
            setForm({ ...form, image_id: e.target.value, image: "" })
          }
        >
          <option value="">-- Use name instead --</option>
          {dockerImages.map((img: any, index: number) => (
            <option key={img.id} value={img.id}>
              {`${img.name || "unknown"}:${img.tag || "latest"} (#${index + 1})`}
            </option>
          ))}
        </select>

        <Input
          placeholder="Or enter image name"
          value={form.image}
          onChange={(e) =>
            setForm({ ...form, image: e.target.value, image_id: "" })
          }
        />

        <Input
          type="number"
          placeholder="CPU Limit"
          value={form.cpu_limit}
          onChange={(e) => setForm({ ...form, cpu_limit: Number(e.target.value) })}
        />
        <Input
          type="number"
          placeholder="Memory (MB)"
          value={form.memory_limit_mb}
          onChange={(e) => setForm({ ...form, memory_limit_mb: Number(e.target.value) })}
        />
        <Input
          type="number"
          placeholder="Internal Port"
          value={form.internal_port}
          onChange={(e) => setForm({ ...form, internal_port: Number(e.target.value) })}
        />
        <Input
          type="number"
          placeholder="Host Port"
          value={form.host_port}
          onChange={(e) => setForm({ ...form, host_port: Number(e.target.value) })}
        />

        <Button onClick={onSubmit}>Create Container</Button>
      </CardContent>
    </Card>
  );
}
