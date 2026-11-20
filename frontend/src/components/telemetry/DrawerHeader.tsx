import Icon from "@/components/Icon";

type T = (key: string, params?: Record<string, string | number>) => string;

export default function DrawerHeader({ iconName, title, subtitle, onClose, t }: { iconName: string; title: string; subtitle: string; onClose: () => void; t: T }) {
  return (
    <div className="telemetry-drawer-header">
      <div className="telemetry-drawer-title-wrap">
        <div className="telemetry-drawer-icon" style={{ color: "var(--accent-text)" }}>
          <Icon name={iconName} size={22} />
        </div>
        <div>
          <h2 className="telemetry-drawer-title">{title}</h2>
          <span className="telemetry-drawer-subtitle">
            {subtitle}
          </span>
        </div>
      </div>
      <button
        type="button"
        className="close-btn"
        onClick={onClose}
        aria-label={t("telemetryDrawer.close")}
      >
        <Icon name="close" size={20} />
      </button>
    </div>
  );
}
