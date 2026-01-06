import * as React from "react";
import { useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client.ts";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Toast,
  ToastProvider,
  ToastViewport,
  ToastTitle,
  ToastDescription,
  ToastClose,
} from "@/components/ui/toast";
import { Progress } from "@/components/ui/progress";

// Form interface
interface ContainerForm {
  image: string;
  image_id: string;
  cpu_limit: number;
  memory_limit_mb: number;
  internal_port: number;
  host_port: number;
  auto_start: boolean;
}

export default function DashboardPage() {
  const qc = useQueryClient();

  // --------------------------
  // State
  // --------------------------
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [form, setForm] = useState<ContainerForm>({
    image: "",
    image_id: "",
    cpu_limit: 1,
    memory_limit_mb: 512,
    internal_port: 80,
    host_port: 8080,
    auto_start: false,
  });

  const [toasts, setToasts] = useState<{ id: number; title: string; description?: string }[]>([]);
  const toastId = React.useRef(0);

  const addToast = (title: string, description?: string) => {
    const id = toastId.current++;
    setToasts((prev) => [...prev, { id, title, description }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 5000);
  };

  // --------------------------
  // Queries
  // --------------------------
  const { data: uploaded = [] } = useQuery({
    queryKey: ["uploaded-images"],
    queryFn: async () => (await api.get("/images/uploaded")).data,
    refetchInterval: 2000,
  });

  const { data: dockerImages = [] } = useQuery({
    queryKey: ["docker-images"],
    queryFn: async () => (await api.get("/images/docker")).data,
    refetchInterval: 5000,
  });

  const { data: containers = [] } = useQuery({
    queryKey: ["containers"],
    queryFn: async () => (await api.get("/containers")).data,
    refetchInterval: 5000,
  });

  // --------------------------
  // Mutations
  // --------------------------
  const uploadImage = useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData();
      formData.append("file", file);
      return (await api.post("/images/upload", formData)).data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["uploaded-images"] });
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      addToast("Upload successful", "Docker image uploaded");
    },
    onError: () => addToast("Error", "Failed to upload image"),
  });

  const loadImage = useMutation({
    mutationFn: (id: string) => api.post(`/images/uploaded/${id}/load`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["uploaded-images"] });
      addToast("Load started", "Docker image is loading in background");
    },
    onError: () => addToast("Error", "Failed to load Docker image"),
  });

  const createContainer = useMutation({
    mutationFn: (payload: ContainerForm) => {
    // Ensure mutual exclusivity
    const body = {
      ...payload,
      image: payload.image_id ? null : payload.image,
      image_id: payload.image ? null : payload.image_id,
    };
    return api.post("/containers", body);
  },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["containers"] });
      addToast("Container created", `Container for image ${form.image_id} created`);
      setForm({
        image: "",
        image_id: "",
        cpu_limit: 1,
        memory_limit_mb: 512,
        internal_port: 80,
        host_port: 8080,
        auto_start: false,
      });
    },
    onError: () => addToast("Error", "Failed to create container"),
  });

  const startContainer = useMutation({
    mutationFn: (containerId: string) => api.post(`/containers/${containerId}/start`),
    onSuccess: (_, containerId) => {
      qc.invalidateQueries({ queryKey: ["containers"] });
      addToast("Container started", `Container ${containerId} started`);
    },
    onError: (_, containerId) => addToast("Error", `Failed to start container ${containerId}`),
  });

  const stopContainer = useMutation({
    mutationFn: (containerId: string) => api.post(`/containers/${containerId}/stop`),
    onSuccess: (_, containerId) => {
      qc.invalidateQueries({ queryKey: ["containers"] });
      addToast("Container stopped", `Container ${containerId} stopped`);
    },
    onError: (_, containerId) => addToast("Error", `Failed to stop container ${containerId}`),
  });

  const deleteContainer = useMutation({
    mutationFn: (containerId: string) => api.delete(`/containers/${containerId}`),
    onSuccess: (_, containerId) => {
      qc.invalidateQueries({ queryKey: ["containers"] });
      addToast("Container deleted", `Container ${containerId} deleted`);
    },
    onError: (_, containerId) => addToast("Error", `Failed to delete container ${containerId}`),
  });

  // --------------------------
  // Handlers
  // --------------------------
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) setSelectedFile(e.target.files[0]);
  };

  const handleUpload = () => {
    if (selectedFile) uploadImage.mutate(selectedFile);
  };

  return (
    <ToastProvider>
      <div className="flex gap-6 p-6">
        {/* Sidebar for container form */}
        <div className="w-80 flex-shrink-0 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Create Container</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <Input
                placeholder="Image name"
                value={form.image}
                onChange={(e) => setForm({ ...form, image: e.target.value })}
              />
              <small className="text-xs text-gray-500">Name of Docker image to use.</small>

              <Input
                placeholder="Image UUID"
                value={form.image_id}
                onChange={(e) => setForm({ ...form, image_id: e.target.value })}
              />
              <small className="text-xs text-gray-500">UUID of the uploaded image.</small>

              <Input
                type="number"
                placeholder="CPU Limit"
                value={form.cpu_limit}
                onChange={(e) => setForm({ ...form, cpu_limit: Number(e.target.value) })}
              />
              <small className="text-xs text-gray-500">Number of CPU cores assigned to container.</small>

              <Input
                type="number"
                placeholder="Memory (MB)"
                value={form.memory_limit_mb}
                onChange={(e) => setForm({ ...form, memory_limit_mb: Number(e.target.value) })}
              />
              <small className="text-xs text-gray-500">Max memory for container in MB.</small>

              <Input
                type="number"
                placeholder="Internal Port"
                value={form.internal_port}
                onChange={(e) => setForm({ ...form, internal_port: Number(e.target.value) })}
              />
              <small className="text-xs text-gray-500">Port inside container.</small>

              <Input
                type="number"
                placeholder="Host Port"
                value={form.host_port}
                onChange={(e) => setForm({ ...form, host_port: Number(e.target.value) })}
              />
              <small className="text-xs text-gray-500">Port on your host machine.</small>

              <div className="flex items-center space-x-2">
                <Input
                  type="checkbox"
                  checked={form.auto_start}
                  onChange={(e) => setForm({ ...form, auto_start: e.target.checked })}
                />
                <span>Auto Start</span>
              </div>
              <small className="text-xs text-gray-500">Start container automatically after creation.</small>

              <Button onClick={() => createContainer.mutate(form)}>Create Container</Button>
            </CardContent>
          </Card>

          {/* Upload Docker Image */}
          <Card>
            <CardHeader>
              <CardTitle>Upload Docker Image (.tar)</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <Input
                type="file"
                accept=".tar"
                onChange={handleFileChange}
                ref={fileInputRef}
              />
              <Button disabled={!selectedFile} onClick={handleUpload}>
                Upload
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* Main Content */}
        <div className="flex-1 space-y-6">
          <h2 className="text-2xl font-semibold">Uploaded Images</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {uploaded.map((img: any) => (
              <Card key={img.id}>
                <CardHeader>
                  <CardTitle className="flex justify-between items-center">
                    {img.id}
                    <Badge>{img.status.toUpperCase()}</Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col gap-2">
                  {img.status === "uploaded" && <Button onClick={() => loadImage.mutate(img.id)}>Load</Button>}
                  {img.status === "loading" && <Progress value={50} />}
                </CardContent>
              </Card>
            ))}
          </div>

          <h2 className="text-2xl font-semibold">Docker Images</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {dockerImages.map((img: any) => (
              <Card key={img.id}>
                <CardHeader>
                  <CardTitle className="flex justify-between items-center">
                    {img.id}
                    <Badge>{img.status.toUpperCase()}</Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div>DOCKER ID: {img.docker_id}</div>
                  <div>Uploaded ID: {img.uploaded_image_id}</div>
                </CardContent>
              </Card>
            ))}
          </div>

          <h2 className="text-2xl font-semibold">Containers</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {containers.map((c: any) => (
                <Card key={c.id}>
                  <CardHeader>
                    <CardTitle className="flex justify-between items-center">
                      {c.id}
                      <Badge>{c.status?.toUpperCase() || "UNKNOWN"}</Badge>
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-2">
                    <div>Image: {c.image || "N/A"}</div>
                    <div>Exposed Port: {c.exposed_port || "N/A"}</div>
                    <div>Created At: {new Date(c.created_at).toLocaleString()}</div>
                    <div className="flex gap-2 mt-2">
                      {c.status !== "running" && (
                        <Button onClick={() => startContainer.mutate(c.id)}>Start</Button>
                      )}
                      {c.status === "running" && (
                        <Button onClick={() => stopContainer.mutate(c.id)}>Stop</Button>
                      )}
                      <Button variant="destructive" onClick={() => deleteContainer.mutate(c.id)}>
                        Delete
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          
        </div>
      </div>

      {/* Toast Viewport */}
      <ToastViewport>
        {toasts.map((t) => (
          <Toast key={t.id}>
            <ToastTitle>{t.title}</ToastTitle>
            {t.description && <ToastDescription>{t.description}</ToastDescription>}
            <ToastClose />
          </Toast>
        ))}
      </ToastViewport>
    </ToastProvider>
  );
}
