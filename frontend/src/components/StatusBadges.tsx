import { CheckCircle2, CircleSlash, ShieldAlert, ShieldCheck, XCircle } from "lucide-react";
import type { ExperimentStatus, ScoreStatus } from "../api/types";
import { Badge, type Tone } from "./ui/Badge";

const STATUS_TONE: Record<string, Tone> = {
  queued: "neutral",
  running: "accent",
  completed: "success",
  failed: "danger",
  cancelled: "warning",
};

export function StatusBadge({ status }: { status: ExperimentStatus }) {
  const tone = STATUS_TONE[status] ?? "neutral";
  return (
    <Badge tone={tone} dot pulse={status === "running" || status === "queued"}>
      {status}
    </Badge>
  );
}

export function GateBadge({ passed, compact }: { passed: boolean | null | undefined; compact?: boolean }) {
  if (passed === null || passed === undefined) {
    return (
      <Badge tone="neutral" icon={<CircleSlash className="size-3" />}>
        {compact ? "n/a" : "no gates"}
      </Badge>
    );
  }
  return passed ? (
    <Badge tone="success" icon={<ShieldCheck className="size-3" />}>
      {compact ? "pass" : "gates pass"}
    </Badge>
  ) : (
    <Badge tone="danger" icon={<ShieldAlert className="size-3" />}>
      {compact ? "fail" : "gates fail"}
    </Badge>
  );
}

export function PassBadge({ passed }: { passed: boolean | null | undefined }) {
  if (passed === null || passed === undefined) return <Badge tone="neutral">n/a</Badge>;
  return passed ? (
    <Badge tone="success" icon={<CheckCircle2 className="size-3" />}>
      pass
    </Badge>
  ) : (
    <Badge tone="danger" icon={<XCircle className="size-3" />}>
      fail
    </Badge>
  );
}

const SCORE_TONE: Record<string, Tone> = {
  done: "success",
  pending: "warning",
  running: "accent",
  failed: "danger",
  none: "neutral",
};

export function ScoreStatusBadge({ status }: { status: ScoreStatus }) {
  return (
    <Badge tone={SCORE_TONE[status] ?? "neutral"} dot pulse={status === "pending" || status === "running"}>
      {status === "none" ? "not scored" : status}
    </Badge>
  );
}
