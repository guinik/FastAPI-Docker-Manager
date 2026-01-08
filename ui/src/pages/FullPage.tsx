
import { useState, useRef } from "react";
import React from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client.ts";
import {
  Toast,
  ToastProvider,
  ToastViewport,
  ToastTitle,
  ToastDescription,
  ToastClose,
} from "@/components/ui/toast";
import CreateContainerForm  from "@/components/dashboard/container_form.tsx";
import UploadImageForm from "@/components/dashboard/uploaded_image_form.tsx";
import UploadedImagesList from "@/components/dashboard/uploaded_image_list.tsx";
import DockerImagesList from "@/components/dashboard/docker_images_list.tsx";
import ContainersList from "@/components/dashboard/container_list.tsx";
import LogsModal from "@/components/dashboard/logs_modal.tsx";

interface ContainerForm {
  image: string;
  image_id: string;
  cpu_limit: number;
  memory_limit_mb: number;
  internal_port: number;
  host_port: number;
}

export default function DashboardPage() {
  const qc = useQueryClient();

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [form, setForm] = useState<ContainerForm>({
    image: "",
    image_id: "",
    cpu_limit: 1,
    memory_limit_mb: 512,
    internal_port: 80,
    host_port: 8080
  });

  const [toasts, setToasts] = useState<{ id: number; title: string; description?: string }[]>([]);
  const toastId = React.useRef(0);

  const [logsModal, setLogsModal] = useState<{ open: boolean; logs: string; containerId: string | null }>({
    open: false,
    logs: "",
    containerId: null,
  });

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

  const loadUploadedImage = useMutation({
    mutationFn: (id: string) => api.post(`/images/uploaded/${id}/load`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["uploaded-images"] });
      qc.invalidateQueries({ queryKey: ["docker-images"] });
      addToast("Load started", "Docker image is loading in background");
    },
    onError: () => addToast("Error", "Failed to load Docker image"),
  });

  const reloadDockerImage = useMutation({
    mutationFn: (id: string) => api.post(`/images/docker/${id}/load`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["docker-images"] });
      addToast("Reload started", "Docker image reloading");
    },
    onError: () => addToast("Error", "Failed to reload Docker image"),
  });

  const deleteUploadedImage = useMutation({
    mutationFn: (id: string) => api.delete(`/images/uploaded/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["uploaded-images"] });
      qc.invalidateQueries({ queryKey: ["docker-images"] });
      addToast("Deleted", "Uploaded image deleted");
    },
    onError: () => addToast("Error", "Failed to delete uploaded image"),
  });

  const deleteDockerImage = useMutation({
    mutationFn: (id: string) => api.delete(`/images/docker/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["docker-images"] });
      addToast("Deleted", "Docker image deleted");
    },
    onError: () => addToast("Error", "Failed to delete Docker image"),
  });

  const createContainer = useMutation({
    mutationFn: (payload: ContainerForm) => {
      const body = {
        ...payload,
        image: payload.image_id ? null : payload.image,
        image_id: payload.image ? null : payload.image_id,
      };
      return api.post("/containers", body);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["containers"] });
      addToast("Container created", `Container created successfully`);
      setForm({
        image: "",
        image_id: "",
        cpu_limit: 1,
        memory_limit_mb: 512,
        internal_port: 80,
        host_port: 8080
      });
    },
    onError: () => addToast("Error", "Failed to create container"),
  });

  const startContainer = useMutation({
    mutationFn: (id: string) => api.post(`/containers/${id}/start`),
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: ["containers"] });
      addToast("Container started", `Container ${id} started`);
    },
    onError: (_, id) => addToast("Error", `Failed to start container ${id}`),
  });

  const stopContainer = useMutation({
    mutationFn: (id: string) => api.post(`/containers/${id}/stop`),
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: ["containers"] });
      addToast("Container stopped", `Container ${id} stopped`);
    },
    onError: (_, id) => addToast("Error", `Failed to stop container ${id}`),
  });

  const deleteContainer = useMutation({
    mutationFn: (id: string) => api.delete(`/containers/${id}`),
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: ["containers"] });
      addToast("Container deleted", `Container ${id} deleted`);
    },
    onError: (_, id) => addToast("Error", `Failed to delete container ${id}`),
  });

  const viewLogs = async (id: string) => {
    try {
      const res = await api.get(`/containers/${id}/logs`);
      setLogsModal({ open: true, logs: res.data.logs, containerId: id });
    } catch (err) {
      addToast("Error", `Failed to fetch logs for container ${id}`);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) setSelectedFile(e.target.files[0]);
  };

  const handleUpload = () => {
    if (selectedFile) uploadImage.mutate(selectedFile);
  };

  // --------------------------
  // Helpers
  // --------------------------
  const truncate = (str: string, length = 12) =>
    str.length > length ? str.slice(0, length) + "..." : str;

  console.log("Rendering containers:", containers)
  return (
    <ToastProvider>
      <div className="flex gap-6 p-6">
        {/* Sidebar */}
        <div className="w-80 flex-shrink-0 space-y-4">
          {/* Create Container Form */}
          <CreateContainerForm
            form={form}
            setForm={setForm}
            dockerImages={dockerImages}
            onSubmit={() => createContainer.mutate(form)}
          />

          {/* Upload Docker Image */}
          <UploadImageForm
            selectedFile={selectedFile}
            onFileChange={handleFileChange}
            onUpload={handleUpload}
          />
        </div>

        {/* Main Content */}
        <div className="flex-1 space-y-6">
          {/* Uploaded Images */}
          <UploadedImagesList
            uploaded={uploaded}
            loadUploadedImage={loadUploadedImage}
            deleteUploadedImage={deleteUploadedImage}
            truncate={truncate}
          />

          {/* Docker Images */}
          <DockerImagesList
            dockerImages={dockerImages}
            reloadDockerImage={reloadDockerImage}
            deleteDockerImage={deleteDockerImage}
            truncate={truncate}
          />

          {/* Containers */}
          <ContainersList
            containers={containers}
            startContainer={startContainer}
            stopContainer={stopContainer}
            deleteContainer={deleteContainer}
            viewLogs={viewLogs}
            truncate={truncate}
          />
        </div>
      </div> {/* <-- THIS CLOSES THE MAIN FLEX CONTAINER */}

      {/* Logs Modal */}
      <LogsModal
        open={logsModal.open}
        logs={logsModal.logs}
        containerId={logsModal.containerId}
        onClose={() => setLogsModal({ open: false, logs: "", containerId: null })}
      />

      {/* Toasts */}
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