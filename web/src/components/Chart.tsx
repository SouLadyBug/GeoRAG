import * as echarts from "echarts/core";
import { BarChart, LineChart, ScatterChart } from "echarts/charts";
import { GridComponent, LegendComponent, MarkLineComponent, TooltipComponent } from "echarts/components";
import { SVGRenderer } from "echarts/renderers";
import { useEffect, useRef } from "react";

echarts.use([BarChart, LineChart, ScatterChart, GridComponent, LegendComponent, TooltipComponent, MarkLineComponent, SVGRenderer]);

export const AXIS = {
  axisLine: { lineStyle: { color: "#8a857a" } },
  axisLabel: { color: "#4a4843", fontFamily: "Source Sans 3, Helvetica, Arial, sans-serif", fontSize: 13 },
  splitLine: { lineStyle: { color: "#e6e2d9" } },
};

export const TOOLTIP = {
  backgroundColor: "#ffffff",
  borderColor: "#bdb7aa",
  textStyle: { color: "#1c1c1a", fontFamily: "Source Sans 3, Helvetica, Arial, sans-serif" },
};

export default function Chart({ option, className = "chart" }: { option: any; className?: string }) {
  const el = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!el.current) return;
    const chart = echarts.init(el.current, undefined, { renderer: "svg" });
    chart.setOption({ textStyle: { fontFamily: "Source Sans 3, Helvetica, Arial, sans-serif" }, animation: false, ...option });
    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(el.current);
    return () => {
      ro.disconnect();
      chart.dispose();
    };
  }, [option]);
  return <div ref={el} className={className} />;
}
