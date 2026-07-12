/**
 * 轻量 Toast 通知系统。
 * - 右上角固定定位，滑入/滑出动画
 * - 队列上限 5 个，满时挤最旧 success/info，保留 error/warning
 * - error 默认 5000ms，其余 3000ms
 * - 点击即时消失
 *
 * 用法：
 * ```tsx
 * // App.tsx
 * <ToastProvider>
 *   <App />
 * </ToastProvider>
 *
 * // 任意组件内
 * const toast = useToast();
 * toast.success("上传成功");
 * toast.error("上传失败：存储不可用");
 * ```
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

// -------------------------------------------------------------------
// types
// -------------------------------------------------------------------
export type ToastType = "success" | "error" | "warning" | "info";

export interface Toast {
  id: string;
  type: ToastType;
  message: string;
}

interface ToastItem extends Toast {
  exiting: boolean;
  duration: number;
}

interface ToastContextValue {
  success: (message: string) => void;
  error: (message: string) => void;
  warning: (message: string) => void;
  info: (message: string) => void;
}

// -------------------------------------------------------------------
// config
// -------------------------------------------------------------------
export interface ToastConfig {
  maxToasts?: number;
  defaultDuration?: number;
  errorDuration?: number;
  animationMs?: number;
}

const DEFAULT_MAX_TOASTS = 5;
const DEFAULT_DURATION_MS = 3000;
const DEFAULT_ERROR_DURATION_MS = 5000;
const DEFAULT_ANIMATION_MS = 300;

// -------------------------------------------------------------------
// helpers
// -------------------------------------------------------------------
let nextId = 0;
function uid(): string {
  nextId += 1;
  return `toast-${Date.now()}-${nextId}`;
}

function isCritical(type: ToastType): boolean {
  return type === "error" || type === "warning";
}

// -------------------------------------------------------------------
// context
// -------------------------------------------------------------------
const ToastContext = createContext<ToastContextValue>({
  success: () => {},
  error: () => {},
  warning: () => {},
  info: () => {},
});

export function useToast(): ToastContextValue {
  return useContext(ToastContext);
}

// -------------------------------------------------------------------
// provider
// -------------------------------------------------------------------
export function ToastProvider({
  children,
  config,
}: {
  children: ReactNode;
  config?: ToastConfig;
}) {
  const maxToasts = config?.maxToasts ?? DEFAULT_MAX_TOASTS;
  const defaultDuration = config?.defaultDuration ?? DEFAULT_DURATION_MS;
  const errorDuration = config?.errorDuration ?? DEFAULT_ERROR_DURATION_MS;
  const animationMs = config?.animationMs ?? DEFAULT_ANIMATION_MS;

  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const timers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const remove = useCallback((id: string) => {
    // mark as exiting → animate out → remove from array
    setToasts((prev) =>
      prev.map((t) => (t.id === id ? { ...t, exiting: true } : t)),
    );
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, animationMs);
    const timer = timers.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timers.current.delete(id);
    }
  }, []);

  const add = useCallback(
    (type: ToastType, message: string) => {
      const id = uid();
      const duration = type === "error" ? errorDuration : defaultDuration;

      setToasts((prev) => {
        if (prev.length < maxToasts) {
          return [...prev, { id, type, message, exiting: false, duration }];
        }
        // 队列满: 保留所有 error/warning, 从 success/info 中滑出最旧的
        const keep = prev.filter((t) => isCritical(t.type));
        const drop = prev.filter((t) => !isCritical(t.type));
        if (drop.length > 0) {
          // 有可挤的非关键 toast
          const [_, ...rest] = drop;
          return [...keep, ...rest, { id, type, message, exiting: false, duration }];
        }
        // 全部都是关键 toast → 不挤, 丢弃新 toast
        return prev;
      });

      // auto-dismiss
      const timer = setTimeout(() => remove(id), duration);
      timers.current.set(id, timer);
    },
    [remove],
  );

  const success = useCallback(
    (message: string) => add("success", message),
    [add],
  );
  const error = useCallback(
    (message: string) => add("error", message),
    [add],
  );
  const warning = useCallback(
    (message: string) => add("warning", message),
    [add],
  );
  const info = useCallback(
    (message: string) => add("info", message),
    [add],
  );

  // cleanup on unmount
  useEffect(() => {
    return () => {
      timers.current.forEach((t) => clearTimeout(t));
    };
  }, []);

  return (
    <ToastContext.Provider value={{ success, error, warning, info }}>
      {children}
      {/* toast container */}
      {toasts.length > 0 && (
        <div className="aiw-toast-container">
          {toasts.map((t) => (
            <div
              key={t.id}
              className={`aiw-toast aiw-toast-${t.type}${t.exiting ? " aiw-toast-exiting" : ""}`}
              onClick={() => remove(t.id)}
            >
              <span className="aiw-toast-icon">
                {t.type === "success"
                  ? "✓"
                  : t.type === "error"
                    ? "✕"
                    : t.type === "warning"
                      ? "⚠"
                      : "ℹ"}
              </span>
              <span className="aiw-toast-msg">{t.message}</span>
            </div>
          ))}
        </div>
      )}
    </ToastContext.Provider>
  );
}
