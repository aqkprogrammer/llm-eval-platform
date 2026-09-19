import { Area, AreaChart, ResponsiveContainer, Tooltip, YAxis } from "recharts";
import { ChartTooltip } from "./ChartTooltip";

export function Sparkline({
  data,
  dataKey,
  color = "var(--chart-1)",
  height = 40,
  name,
  valueFormatter,
  labelKey = "ts",
  labelFormatter,
}: {
  data: Record<string, unknown>[];
  dataKey: string;
  color?: string;
  height?: number;
  name?: string;
  valueFormatter?: (v: number) => string;
  labelKey?: string;
  labelFormatter?: (v: unknown) => string;
}) {
  const id = `spark-${dataKey}`;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.3} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <YAxis hide domain={[0, "auto"]} />
        <Tooltip
          cursor={{ stroke: "var(--chart-axis)", strokeWidth: 1 }}
          content={({ active, payload }) => (
            <ChartTooltip
              active={active}
              payload={payload}
              label={payload?.[0] ? (payload[0].payload as Record<string, unknown>)[labelKey] : undefined}
              labelFormatter={labelFormatter ? (l) => labelFormatter(l) : undefined}
              valueFormatter={valueFormatter ? (v) => valueFormatter(v) : undefined}
            />
          )}
        />
        <Area
          type="monotone"
          dataKey={dataKey}
          name={name ?? dataKey}
          stroke={color}
          strokeWidth={2}
          fill={`url(#${id})`}
          connectNulls
          isAnimationActive={false}
          dot={false}
          activeDot={{ r: 3, strokeWidth: 2, stroke: "var(--surface)" }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
