import * as echarts from "echarts/core";
import { BarChart, LineChart, ScatterChart } from "echarts/charts";
import { GridComponent, LegendComponent, MarkLineComponent, TooltipComponent } from "echarts/components";
import { SVGRenderer } from "echarts/renderers";
import { useEffect, useRef } from "react";

echarts.use([BarChart, LineChart, ScatterChart, GridComponent, LegendComponent, TooltipComponent, MarkLineComponent, SVGRenderer]);

export const AXIS = {
  axisLine: { lineStyle: { color: "#334155" } },
  axisLabel: { color: "#94a3b8", fontFamily: "Inter Variable, Inter, sans-serif" },
  splitLine: { lineStyle: { color: "rgba(148,163,184,0.08)" } },
};

export const TOOLTIP = {
  backgroundColor: "#0f1729",
  borderColor: "#334155",
  textStyle: { color: "#e2e8f0", fontFamily: "Inter Variable, Inter, sans-serif" },
};

export default function Chart({ option, className = "chart" }: { option: any; className?: string }) {
  const el = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!el.current) return;
    const chart = echarts.init(el.current, undefined, { renderer: "svg" });
    chart.setOption({ textStyle: { fontFamily: "Inter Variable, Inter, sans-serif" }, animationDuration: 900, ...option });
    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(el.current);
    return () => {
      ro.disconnect();
      chart.dispose();
    };
  }, [option]);
  return <div ref={el} className={className} />;
}
