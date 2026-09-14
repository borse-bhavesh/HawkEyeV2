import { test } from 'node:test';
import assert from 'node:assert';
import { filterActionableEvents, getHighRiskEventCount, getHighRiskEvidenceCount } from '../src/utils/eventFilters';
import type { Event, RiskAssessment } from '../src/types/sessions';

test('filterActionableEvents includes ZONE_ENTRY', () => {
  const events: Event[] = [
    { event_id: '1', event_type: 'TRACK_STARTED', frame_number: 1, timestamp_seconds: 1, description: '', track_id: null, evidence: {} },
    { event_id: '2', event_type: 'ZONE_ENTRY', frame_number: 2, timestamp_seconds: 2, description: '', track_id: null, evidence: {} },
  ];
  const risks: RiskAssessment[] = [];

  const result = filterActionableEvents(events, risks);
  assert.strictEqual(result.length, 1);
  assert.strictEqual(result[0].event_type, 'ZONE_ENTRY');
});

test('filterActionableEvents excludes normal events if no risks', () => {
  const events: Event[] = [
    { event_id: '1', event_type: 'TRACK_STARTED', frame_number: 1, timestamp_seconds: 1, description: '', track_id: null, evidence: {} },
    { event_id: '2', event_type: 'TRACK_ENDED', frame_number: 2, timestamp_seconds: 2, description: '', track_id: null, evidence: {} },
  ];
  const risks: RiskAssessment[] = [];

  const result = filterActionableEvents(events, risks);
  assert.strictEqual(result.length, 0);
});

test('filterActionableEvents includes events associated with HIGH/CRITICAL risk', () => {
  const events: Event[] = [
    { event_id: '1', event_type: 'TRACK_STARTED', frame_number: 1, timestamp_seconds: 1, description: '', track_id: null, evidence: {} },
    { event_id: '2', event_type: 'PROXIMITY_ALERT', frame_number: 2, timestamp_seconds: 2, description: '', track_id: null, evidence: {} },
    { event_id: '3', event_type: 'LOITERING', frame_number: 3, timestamp_seconds: 3, description: '', track_id: null, evidence: {} },
  ];
  
  const risks: RiskAssessment[] = [
    { 
      event_id: 'risk_1', 
      contributing_event_ids: ['2'], 
      contributing_event_types: ['PROXIMITY_ALERT'], 
      risk_level: 'HIGH', 
      priority: '1',
      session_id: 's',
      policy_id: 'p',
      timestamp: 't',
      status: 's',
      evidence: []
    } as any,
    { 
      event_id: 'risk_2', 
      contributing_event_ids: ['3'], 
      contributing_event_types: ['LOITERING'], 
      risk_level: 'MEDIUM', 
      priority: '2',
      session_id: 's',
      policy_id: 'p',
      timestamp: 't',
      status: 's',
      evidence: []
    } as any
  ];

  const result = filterActionableEvents(events, risks);
  assert.strictEqual(result.length, 1);
  assert.strictEqual(result[0].event_id, '2');
});

test('filterActionableEvents deduplicates and sorts newest first', () => {
  const events: Event[] = [
    { event_id: '2', event_type: 'ZONE_ENTRY', frame_number: 2, timestamp_seconds: 2, description: '', track_id: null, evidence: {} },
    { event_id: '1', event_type: 'ZONE_ENTRY', frame_number: 1, timestamp_seconds: 1, description: '', track_id: null, evidence: {} },
    { event_id: '2', event_type: 'ZONE_ENTRY', frame_number: 2, timestamp_seconds: 2, description: '', track_id: null, evidence: {} },
  ];
  const risks: RiskAssessment[] = [];

  const result = filterActionableEvents(events, risks);
  assert.strictEqual(result.length, 2);
  assert.strictEqual(result[0].event_id, '2');
  assert.strictEqual(result[1].event_id, '1');
});

test('getHighRiskEventCount and getHighRiskEvidenceCount with no risks', () => {
  const events = [
    { event_id: 'e1', event_type: 'TRACK_STARTED' } as any,
    { event_id: 'e2', event_type: 'ZONE_ENTRY' } as any
  ];
  const evidence = [
    { evidence_id: 'ev1', event_id: 'e1' } as any,
    { evidence_id: 'ev2', event_id: 'e2' } as any
  ];
  const risks: RiskAssessment[] = [];

  assert.strictEqual(getHighRiskEventCount(events, risks), 0);
  assert.strictEqual(getHighRiskEvidenceCount(evidence, risks), 0);
});

test('getHighRiskEventCount and getHighRiskEvidenceCount with HIGH risk', () => {
  const events = [
    { event_id: 'e1' } as any
  ];
  const evidence = [
    { evidence_id: 'ev1', event_id: 'e1' } as any,
    { evidence_id: 'ev2', assessment_id: 'r1' } as any
  ];
  const risks = [
    { id: 'r1', event_id: 'e1', risk_level: 'HIGH', contributing_event_ids: [] } as any
  ];

  assert.strictEqual(getHighRiskEventCount(events, risks), 1);
  assert.strictEqual(getHighRiskEvidenceCount(evidence, risks), 2);
});

test('getHighRiskEventCount and getHighRiskEvidenceCount with CRITICAL risk and multiple contributing', () => {
  const events = [
    { event_id: 'e1' } as any,
    { event_id: 'e2' } as any,
    { event_id: 'e3' } as any
  ];
  const evidence = [
    { evidence_id: 'ev1', event_id: 'e1' } as any,
    { evidence_id: 'ev2', event_id: 'e2' } as any,
    { evidence_id: 'ev3', event_id: 'e3' } as any
  ];
  const risks = [
    { id: 'r1', event_id: 'e1', risk_level: 'CRITICAL', contributing_event_ids: ['e2', 'e3'] } as any
  ];

  assert.strictEqual(getHighRiskEventCount(events, risks), 3);
  assert.strictEqual(getHighRiskEvidenceCount(evidence, risks), 3);
});

test('getHighRiskEventCount handles duplicates', () => {
  const events = [
    { event_id: 'e1' } as any,
    { event_id: 'e2' } as any
  ];
  const risks = [
    { id: 'r1', event_id: 'e1', risk_level: 'HIGH', contributing_event_ids: ['e2'] } as any,
    { id: 'r2', event_id: 'e1', risk_level: 'CRITICAL', contributing_event_ids: ['e2'] } as any
  ];

  assert.strictEqual(getHighRiskEventCount(events, risks), 2); // e1 and e2
});
