"use client";

import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, CheckCircle, Info, X, XCircle } from "lucide-react";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

export type ToastType = "success" | "error" | "warning" | "info";

interface Toast {
  id: string;
  message: string;
  type: ToastType;
}

interface ConfirmOptions {
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
}

interface ToastContextValue {
  toast: (message: string, type?: ToastType) => void;
  confirm: (options: ConfirmOptions) => Promise<boolean>;
}

const ToastContext = createContext<ToastContextValue | null>(null);

// Lets plain async functions outside the component tree (e.g. downloadWithAuth
// in MediaPreview.tsx) surface a toast without needing the useToast() hook.
let globalToast: ((message: string, type?: ToastType) => void) | null = null;

export function showGlobalToast(message: string, type: ToastType = "info") {
  globalToast?.(message, type);
}

const typeConfig: Record<
  ToastType,
  { classes: string; icon: ReactNode }
> = {
  success: {
    classes: "status-success",
    icon: <CheckCircle className="w-4 h-4 text-success flex-shrink-0" />,
  },
  error: {
    classes: "status-danger",
    icon: <XCircle className="w-4 h-4 text-danger flex-shrink-0" />,
  },
  warning: {
    classes: "status-warning",
    icon: <AlertTriangle className="w-4 h-4 text-warning flex-shrink-0" />,
  },
  info: {
    classes: "status-info",
    icon: <Info className="w-4 h-4 text-info flex-shrink-0" />,
  },
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [confirmState, setConfirmState] = useState<{
    options: ConfirmOptions;
    resolve: (value: boolean) => void;
  } | null>(null);

  const addToast = useCallback((message: string, type: ToastType = "info") => {
    const id = Math.random().toString(36).slice(2);
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  }, []);

  useEffect(() => {
    globalToast = addToast;
    return () => {
      if (globalToast === addToast) globalToast = null;
    };
  }, [addToast]);

  const showConfirm = useCallback(
    (options: ConfirmOptions): Promise<boolean> => {
      return new Promise((resolve) => {
        setConfirmState({ options, resolve });
      });
    },
    []
  );

  const handleConfirmClose = (value: boolean) => {
    confirmState?.resolve(value);
    setConfirmState(null);
  };

  return (
    <ToastContext.Provider value={{ toast: addToast, confirm: showConfirm }}>
      {children}

      {/* Toast stack */}
      <div className="fixed bottom-5 right-5 z-[100] flex flex-col gap-2 pointer-events-none">
        <AnimatePresence mode="popLayout">
          {toasts.map((t) => {
            const cfg = typeConfig[t.type];
            return (
              <motion.div
                key={t.id}
                layout
                initial={{ opacity: 0, x: 20, scale: 0.95 }}
                animate={{ opacity: 1, x: 0, scale: 1 }}
                exit={{ opacity: 0, x: 20, scale: 0.95 }}
                transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
                className={`pointer-events-auto flex items-center gap-2.5 px-4 py-3 rounded-xl border shadow-dropdown text-sm font-medium max-w-sm backdrop-blur-sm ${cfg.classes}`}
              >
                {cfg.icon}
                <span className="flex-1">{t.message}</span>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>

      {/* Confirm modal */}
      <AnimatePresence>
        {confirmState && (
          <div className="fixed inset-0 z-[200] flex items-center justify-center p-4">
            <motion.div
              className="absolute inset-0 bg-black/60 backdrop-blur-md"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => handleConfirmClose(false)}
            />
            <motion.div
              className="relative bg-surface rounded-2xl shadow-modal border border-border p-6 w-full max-w-sm overflow-hidden"
              initial={{ opacity: 0, scale: 0.95, y: 8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.97, y: 4 }}
              transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
            >
              <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-accent/40 to-transparent" />
              <h3 className="text-sm font-semibold text-text mb-2">
                {confirmState.options.title}
              </h3>
              <p className="text-sm text-text-muted mb-6">
                {confirmState.options.message}
              </p>
              <div className="flex gap-2 justify-end">
                <button
                  data-testid="confirm-dialog-cancel"
                  onClick={() => handleConfirmClose(false)}
                  className="px-3.5 py-2 text-sm font-medium text-text-secondary hover:text-text bg-surface-2 hover:bg-surface-3 rounded-lg border border-border transition-colors"
                >
                  {confirmState.options.cancelLabel ?? "İptal"}
                </button>
                <button
                  data-testid="confirm-dialog-accept"
                  onClick={() => handleConfirmClose(true)}
                  className={`px-3.5 py-2 text-sm font-semibold rounded-lg transition-colors ${
                    confirmState.options.destructive
                      ? "bg-red-500/90 hover:bg-red-500 text-white"
                      : "bg-gradient-accent text-white hover:opacity-90"
                  }`}
                >
                  {confirmState.options.confirmLabel ?? "Onayla"}
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}
