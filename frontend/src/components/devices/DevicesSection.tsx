"use client";

import Icon from "@/components/Icon";
import AudioSection from "./AudioSection";
import BluetoothSection from "./BluetoothSection";
import { type SectionProps } from "./shared/section";

export default function DevicesSection(props: SectionProps) {
  const { t } = props;
  return (
    <div className="dv-groups">
      <section className="dv-group" aria-labelledby="dv-audio-title">
        <h3 id="dv-audio-title" className="dv-group-title"><Icon name="speaker" size={18} /> {t("devices.groups.audio")}</h3>
        <AudioSection {...props} />
      </section>
      <section className="dv-group" aria-labelledby="dv-bt-title">
        <h3 id="dv-bt-title" className="dv-group-title"><Icon name="bluetooth" size={18} /> {t("devices.groups.bluetooth")}</h3>
        <BluetoothSection {...props} />
      </section>
    </div>
  );
}
