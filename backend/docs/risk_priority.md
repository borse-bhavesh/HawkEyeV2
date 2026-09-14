# Risk & Priority

### Purpose
Risk/Priority converts observable events into a structured decision-support assessment.

### Separation
Event ≠ Risk Assessment.
- **Event**: "What objectively observable condition occurred?"
- **Risk/Priority**: "How urgently should this observable condition be reviewed?"

### RiskLevel
Represents a normalized category assessed by the configured policy.
Levels: LOW / MEDIUM / HIGH / CRITICAL.

### Priority
Represents the operational urgency category for human review.
Levels: LOW / MEDIUM / HIGH / CRITICAL.

### Traceability
Assessments retain event IDs and event types natively, ensuring every assessment maps explicitly back to its objective source observation(s).

### Explanation
Every assessment must have a non-empty `reason`.

### Human review
Risk/Priority does not authorize autonomous enforcement.
The system does NOT:
- automatically dispatch personnel
- automatically classify people as threats
- automatically identify criminals
- automatically take enforcement action

Human review remains strictly required.

### Configuration
Risk configuration (`RiskConfig`) is completely independent from detection, tracking, and event-intelligence configuration.

## Step 6.2 — Configurable Risk Policy

### Policy model
`EventType` → `RiskPolicyRule`

### Default policy
The default policy is a configurable operational baseline, not a claim that a particular event type is inherently dangerous or unlawful.

| Event Type | Default Risk | Default Priority |
|------------|--------------|------------------|
| TRACK_STARTED | LOW | LOW |
| TRACK_ENDED | LOW | LOW |
| ZONE_ENTRY | MEDIUM | MEDIUM |
| ZONE_EXIT | LOW | LOW |
| LOITERING | HIGH | HIGH |
| RAPID_MOVEMENT | MEDIUM | HIGH |
| DIRECTION_CHANGE | MEDIUM | MEDIUM |
| MULTIPLE_OBJECT_PROXIMITY | MEDIUM | MEDIUM |

### RiskLevel
LOW / MEDIUM / HIGH / CRITICAL

### Priority
LOW / MEDIUM / HIGH / CRITICAL

### Explainability
Every assessment derives from an explicit configured rule.

### Traceability
Event ID and EventType are preserved securely from the incoming `Event` object to the outgoing `RiskAssessment` object.

### Batch behavior
One input Event produces exactly one RiskAssessment. Input order is strictly preserved.

### No aggregation
Multiple-event escalation is deferred to a later step.

### No numeric score
Step 6.2 intentionally uses categorical policy rather than an arbitrary numerical risk score.

### Human review
Risk assessments are exclusively decision-support outputs. They do not constitute objective claims of suspicion.

## Step 6.3 — Multi-Event Risk Correlation

### Purpose
Correlate multiple observable events under explicit policy.

### Correlation rule
EventType set → RiskLevel + Priority + explanation.

### Track awareness
Events are correlated only when they can be established as belonging to the same tracked entity.

### Temporal window
Default 30 seconds.

### Matching
All required EventTypes must be present. Additional events do not prevent a match.

### Multiple matching rules
Each matched rule produces its own RiskAssessment.

### Traceability
All contributing event IDs and types are preserved securely.

### Statelessness
The engine evaluates only the supplied event batch.

### No numeric score
Risk level and priority come directly from policy.

### Human review
Correlation remains a decision-support mechanism. Default rules are configurable operational baselines and do not establish intent or threat.

### Default Correlation Table
| Correlation | Default Risk | Default Priority |
|---|---|---|
| ZONE_ENTRY + LOITERING | HIGH | HIGH |
| ZONE_ENTRY + RAPID_MOVEMENT | HIGH | HIGH |
| RAPID_MOVEMENT + DIRECTION_CHANGE | HIGH | HIGH |
| MULTIPLE_OBJECT_PROXIMITY + LOITERING | HIGH | HIGH |

These are policy defaults only.

## Step 6.4A — Risk Assessment Lifecycle

### Risk Level vs Lifecycle Status
**RiskLevel**: LOW / MEDIUM / HIGH / CRITICAL
**Priority**: LOW / MEDIUM / HIGH / CRITICAL
**Status**: OPEN / ACKNOWLEDGED / RESOLVED

These represent different concepts. Risk and priority describe the assessment itself, whereas status describes what has happened to that assessment during human review / system processing.

### Lifecycle
```
OPEN
  ↓
ACKNOWLEDGED
  ↓
RESOLVED
```
Backward transitions are rejected. Same-state transitions are idempotent.

### Human Review Boundary
ACKNOWLEDGED and RESOLVED describe workflow state only. They do not establish intent, criminality, guilt, threat confirmation, or enforcement action.

### No Automatic Escalation Yet
Step 6.4A introduces only lifecycle state. Automatic escalation/de-escalation is NOT implemented yet.

## Step 6.4B — Policy-Based Escalation and De-escalation

### Escalation
Existing assessment + explicit observable event pattern → configured categorical escalation.

### De-escalation
Existing assessment + configured quiet period → configured categorical de-escalation.

### No Numeric Scoring
No arithmetic score is calculated.

### Temporal Semantics
Event timestamps are used strictly. Frame-numbers and system clocks are ignored.

### Track Semantics
Events from unrelated tracks are not combined. Recurrence is restricted strictly to track continuity.

### Status Semantics
RiskLevel/Priority may change, but RiskAssessmentStatus does not automatically change.

### Resolved Assessments
RESOLVED assessments are explicitly excluded from automatic changes.

### Conflict Policy
Escalation takes precedence when escalation and de-escalation conditions both match an assessment.

### Multiple Matching Rules
Each matched configured rule produces its own updated assessment.

### Human Review Boundary
Escalation/de-escalation describes configured operational review policy. It does not establish intent, criminality, guilt, or threat certainty.

## Step 6.4C — Risk Assessment Deduplication

### Purpose
Remove repeated logical RiskAssessment instances from an assessment batch without modifying Events.

### Identity
Identity is based on stable logical assessment fields via a deterministic standard library digest.

### Included Fields
- `event_id`
- `contributing_event_ids` (order-normalized)
- `contributing_event_types` (order-normalized)
- `risk_level` (configurable)
- `priority` (configurable)

### Excluded Fields
- `status`
- `reason`
- timestamps
- object identity

### Ordering
First occurrence wins. Input order is preserved exactly.

### Disabled Mode
When disabled, all assessments pass through completely unchanged.

### No Time Window
Step 6.4C does not implement temporal suppression or time-window logic.

### No Event Suppression
Deduplication affects only RiskAssessment output. Events remain untouched.

### Human Review Boundary
Deduplication does not determine whether an event or assessment is valid, dangerous, criminal, or intentional.

## Step 6.4D — Structured Risk Assessment Evidence

### Purpose
Every newly generated assessment may carry structured, machine-readable policy evidence to strengthen explainability.

### Evidence fields
- `source_type`: Engine layer that produced the assessment (POLICY, CORRELATION, ESCALATION, DEESCALATION).
- `policy_identifier`: Deterministic identifier of the applied configured rule.
- `contributing_event_ids`: Events explicitly matched by the rule.
- `contributing_event_types`: EventTypes matched by the rule.
- `explanation`: Factual, policy-based explanation.
- `details`: Optional structured metrics supporting the rule.

### Sources
- POLICY
- CORRELATION
- ESCALATION
- DEESCALATION

### Traceability
Evidence supplements, rather than replaces, existing assessment traceability.

### Deduplication
Evidence does not participate in logical assessment identity.

### Lifecycle
Status transitions do not alter evidence.

### Human Review Boundary
Evidence explains configured operational policy. It does not establish intent, criminality, guilt, threat certainty, or enforcement necessity.
