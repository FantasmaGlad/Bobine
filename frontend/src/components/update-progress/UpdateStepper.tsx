import Icon from "@/components/Icon";
import { STEP_LABEL_KEYS, STEPPER_STEPS } from "./updateStatus";

type T = (key: string, params?: Record<string, string | number>) => string;

function StepDot({ state, title }: { state: "done" | "active" | "pending"; title: string }) {
  return (
    <div
      title={title}
      style={{
        width: 16,
        height: 16,
        borderRadius: "50%",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flexShrink: 0,
        background: state === "pending" ? "transparent" : "var(--accent-primary)",
        border: `2px solid ${state === "pending" ? "var(--border-color)" : "var(--accent-text)"}`,
      }}
    >
      {state === "done" && <Icon name="check" size={10} color="var(--accent-primary-fg)" />}
      {state === "active" && (
        <div style={{ width: 5, height: 5, borderRadius: "50%", background: "var(--accent-primary-fg)" }} />
      )}
    </div>
  );
}

export default function UpdateStepper({ current, t }: { current: number; t: T }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 0 }}>
      {STEPPER_STEPS.map((step, i) => {
        const state = i < current ? "done" : i === current ? "active" : "pending";
        const last = i === STEPPER_STEPS.length - 1;
        return (
          <div key={step} style={{ display: "flex", alignItems: "center", flex: !last ? 1 : "0 0 auto" }}>
            <StepDot state={state} title={t(STEP_LABEL_KEYS[step])} />
            {!last && (
              <div
                style={{
                  flex: 1,
                  height: 2,
                  background: i < current ? "var(--accent-primary)" : "var(--border-color)",
                }}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
