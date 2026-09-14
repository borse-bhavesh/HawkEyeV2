import type { HistoricalProcessingRunResponse } from '@/types/sessions';

export interface AnalyticsSummary {
  totalSessions: number;
  totalEvents: number;
  totalRisks: number;
  totalTracks: number;
}

export interface Distribution {
  label: string;
  count: number;
  percentage: number;
}

export interface SessionComparison {
  sessionId: string;
  durationSeconds: number;
  eventCount: number;
  riskCount: number;
  trackCount: number;
}

export interface AnalyticsResult {
  summary: AnalyticsSummary;
  eventDistribution: Distribution[];
  riskLevelDistribution: Distribution[];
  priorityDistribution: Distribution[];
  statusDistribution: Distribution[];
  sessionComparisons: SessionComparison[];
}

/**
 * Deterministically aggregates a collection of historical runs into analytics view models.
 */
export function calculateAnalytics(runs: HistoricalProcessingRunResponse[]): AnalyticsResult {
  const summary: AnalyticsSummary = {
    totalSessions: runs.length,
    totalEvents: 0,
    totalRisks: 0,
    totalTracks: 0
  };

  const eventCounts: Record<string, number> = {};
  const riskCounts: Record<string, number> = {};
  const priorityCounts: Record<string, number> = {};
  const statusCounts: Record<string, number> = {};

  const sessionComparisons: SessionComparison[] = [];

  for (const run of runs) {
    summary.totalEvents += run.events.length;
    summary.totalRisks += run.risk_assessments.length;
    summary.totalTracks += run.tracks.length;

    // Track Session Comparison
    const start = run.session.started_at ? new Date(run.session.started_at).getTime() : 0;
    const end = run.session.completed_at ? new Date(run.session.completed_at).getTime() : start;
    const durationSeconds = start > 0 ? (end - start) / 1000 : 0;

    sessionComparisons.push({
      sessionId: run.session.session_id,
      durationSeconds,
      eventCount: run.events.length,
      riskCount: run.risk_assessments.length,
      trackCount: run.tracks.length
    });

    // Aggregate Events
    for (const event of run.events) {
      eventCounts[event.event_type] = (eventCounts[event.event_type] || 0) + 1;
    }

    // Aggregate Risks
    for (const risk of run.risk_assessments) {
      riskCounts[risk.risk_level] = (riskCounts[risk.risk_level] || 0) + 1;
      priorityCounts[risk.priority] = (priorityCounts[risk.priority] || 0) + 1;
      statusCounts[risk.status] = (statusCounts[risk.status] || 0) + 1;
    }
  }

  // Convert to sorted distributions with percentages
  const toDistribution = (counts: Record<string, number>, total: number): Distribution[] => {
    if (total === 0) return [];
    return Object.entries(counts)
      .map(([label, count]) => ({
        label,
        count,
        percentage: Number(((count / total) * 100).toFixed(1))
      }))
      .sort((a, b) => b.count - a.count);
  };

  return {
    summary,
    eventDistribution: toDistribution(eventCounts, summary.totalEvents),
    riskLevelDistribution: toDistribution(riskCounts, summary.totalRisks),
    priorityDistribution: toDistribution(priorityCounts, summary.totalRisks),
    statusDistribution: toDistribution(statusCounts, summary.totalRisks),
    sessionComparisons: sessionComparisons.sort((a, b) => b.eventCount - a.eventCount)
  };
}
