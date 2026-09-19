import { Link } from "react-router-dom";
import { ArrowUpRight } from "lucide-react";
import type { CaseResult } from "../../api/types";
import { fmtMs, fmtTokens, fmtUsd } from "../../lib/format";
import { PassBadge } from "../StatusBadges";
import { Badge } from "../ui/Badge";
import { CodeBlock, Collapsible } from "../ui/CodeBlock";
import { Drawer } from "../ui/Modal";
import { ContextList, Section, StatsRow, TextPanel } from "../ui/Panels";
import { ScoreList } from "./ScoreList";

export function ResultDrawer({
  result,
  variantLabel,
  onClose,
}: {
  result: CaseResult | null;
  variantLabel?: string;
  onClose: () => void;
}) {
  return (
    <Drawer
      open={!!result}
      onClose={onClose}
      title="Case result"
      description={
        result && (
          <span className="flex flex-wrap items-center gap-2">
            <PassBadge passed={result.passed} />
            {variantLabel && <span className="truncate">{variantLabel}</span>}
          </span>
        )
      }
    >
      {result && (
        <div className="space-y-6">
          <StatsRow
            items={[
              { label: "Latency", value: fmtMs(result.latency_ms) },
              { label: "Time to first token", value: fmtMs(result.ttft_ms) },
              { label: "Tokens (in / out)", value: `${fmtTokens(result.input_tokens)} / ${fmtTokens(result.output_tokens)}` },
              { label: "Cost", value: fmtUsd(result.cost_usd) },
            ]}
          />
          <Section
            title="Input"
            right={
              result.tags.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {result.tags.map((t) => (
                    <Badge key={t}>{t}</Badge>
                  ))}
                </div>
              )
            }
          >
            <TextPanel>{result.input}</TextPanel>
          </Section>
          <Section title={`Context (${result.context.length})`}>
            <ContextList items={result.context} />
          </Section>
          <Section title="Expected output">
            {result.expected_output ? (
              <TextPanel>{result.expected_output}</TextPanel>
            ) : (
              <p className="text-sm text-zinc-500 italic">No reference answer.</p>
            )}
          </Section>
          <Collapsible title="Rendered prompt">
            <CodeBlock>{result.rendered_prompt}</CodeBlock>
          </Collapsible>
          <Section title="Output">
            {result.output !== null ? <TextPanel>{result.output}</TextPanel> : <p className="text-sm text-zinc-500 italic">No output.</p>}
          </Section>
          {result.error && (
            <Section title="Error">
              <TextPanel tone="danger">{result.error}</TextPanel>
            </Section>
          )}
          <Section
            title="Metric scores"
            right={
              result.trace_id && (
                <Link
                  to={`/traces/${result.trace_id}`}
                  className="inline-flex items-center gap-1 text-xs font-medium text-accent-600 hover:underline dark:text-accent-400"
                >
                  View trace <ArrowUpRight className="size-3" />
                </Link>
              )
            }
          >
            <ScoreList scores={result.scores} />
          </Section>
        </div>
      )}
    </Drawer>
  );
}
