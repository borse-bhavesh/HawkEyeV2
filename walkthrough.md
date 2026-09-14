
## 11.4B Bug Fix: HIGH-RISK Metrics Displaying 0
Fixed an issue where `ZONE_ENTRY` events appeared in the Results Summary but did not increment the `HIGH-RISK EVENTS` metric cards on the frontend dashboard. 
- **Investigation:** Added an end-to-end integration test (`test_zone_entry_high_risk_persistence_regression`) simulating a `ZONE_ENTRY` event passing through `RiskOrchestrator`, `EvidenceOrchestrator`, and `ProcessingPersistenceOrchestrator`.
- **Finding:** The backend pipeline correctly identifies `ZONE_ENTRY` as `HIGH` risk, links evidence properly, and persists this down the data layer without data loss. 
- **Root Cause:** The frontend `eventFilters.ts` and `HistoryDetail.tsx` components were strictly evaluating `risk_level === 'HIGH'`, whereas the backend serializes the `RiskLevel` Enum payload as lowercase (`'high'`).
- **Fix:** Added `.toUpperCase()` to the risk level comparison logic in the frontend metric aggregation and filtering functions, enabling the cards to accurately reflect backend payload values.
