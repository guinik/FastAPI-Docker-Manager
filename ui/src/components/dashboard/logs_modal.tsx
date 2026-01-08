import { Button } from "@/components/ui/button";

interface LogsModalProps {
  open: boolean;
  logs: string;
  containerId: string | null;
  onClose: () => void;
}

export default function LogsModal({ open, logs, containerId, onClose }: LogsModalProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex justify-center items-center z-50">
      <div className="bg-white p-4 rounded w-3/4 max-h-[80vh] overflow-auto relative">
        <h3 className="font-bold mb-2">Logs: {containerId}</h3>
        <pre className="text-sm whitespace-pre-wrap">{logs}</pre>
        <Button
          className="absolute top-2 right-2"
          onClick={onClose}
        >
          Close
        </Button>
      </div>
    </div>
  );
}
