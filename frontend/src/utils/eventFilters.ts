import type { Event, RiskAssessment, Evidence } from '@/types/sessions';

export function filterActionableEvents(events: Event[], risks: RiskAssessment[]): Event[] {
  const highRiskEventIds = new Set<string>();
  
  risks.forEach(risk => {
    const level = risk.risk_level?.toUpperCase();
    if (level === 'HIGH' || level === 'CRITICAL') {
      if (risk.event_id) highRiskEventIds.add(risk.event_id);
      if (risk.contributing_event_ids) {
        risk.contributing_event_ids.forEach(id => highRiskEventIds.add(id));
      }
    }
  });

  const actionableEvents = events.filter(event => {
    return event.event_type === 'ZONE_ENTRY' || highRiskEventIds.has(event.event_id);
  });

  const uniqueEvents = actionableEvents.reduce((acc: Event[], current: Event) => {
    if (!acc.find(item => item.event_id === current.event_id)) {
      acc.push(current);
    }
    return acc;
  }, []);

  return uniqueEvents.sort((a, b) => b.timestamp_seconds - a.timestamp_seconds);
}

export function getHighRiskEventCount(events: Event[], risks: RiskAssessment[]): number {
  const highRiskTrackIds = new Set<string>();
  
  events.forEach(e => {
    if (e.event_type === 'ZONE_ENTRY' && e.track_id !== undefined && e.track_id !== null) {
      // Ensure this ZONE_ENTRY is actually associated with a HIGH/CRITICAL risk
      const isHighRisk = risks.some(r => {
        const level = r.risk_level?.toUpperCase();
        if (level !== 'HIGH' && level !== 'CRITICAL') return false;
        return r.event_id === e.event_id || (r.contributing_event_ids && r.contributing_event_ids.includes(e.event_id));
      });
      
      if (isHighRisk) {
        highRiskTrackIds.add(String(e.track_id));
      }
    }
  });

  return highRiskTrackIds.size;
}

export function getHighRiskEvidenceCount(evidence: Evidence[], risks: RiskAssessment[], events: Event[]): number {
  const highRiskTrackIds = new Set<string>();

  events.forEach(e => {
    if (e.event_type === 'ZONE_ENTRY' && e.track_id !== undefined && e.track_id !== null) {
      const relatedRisks = risks.filter(r => {
        const level = r.risk_level?.toUpperCase();
        if (level !== 'HIGH' && level !== 'CRITICAL') return false;
        return r.event_id === e.event_id || (r.contributing_event_ids && r.contributing_event_ids.includes(e.event_id));
      });

      if (relatedRisks.length > 0) {
        // Find if any evidence links to these assessments or events
        const hasEvidence = evidence.some(item => 
          item.event_id === e.event_id || 
          relatedRisks.some((r: any) => r.id === item.assessment_id || r.assessment_id === item.assessment_id || r.event_id === item.assessment_id)
        );
        
        if (hasEvidence) {
          highRiskTrackIds.add(String(e.track_id));
        }
      }
    }
  });

  return highRiskTrackIds.size;
}
