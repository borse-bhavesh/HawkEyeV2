# HAWKEYE V2

AI-Based Intelligent Video Analytics Platform for Border Surveillance.

## Problem Statement

SIH26187 — AI-Based Intelligent Video Analytics Platform for Border Surveillance using Existing CCTV Infrastructure.

## Team

DebugDemons

---

## Current Phase

### Phase 1 — Foundation

HAWKEYE V2 is being developed as a modular, deployable surveillance analytics platform that adds an AI intelligence layer to existing CCTV infrastructure.

### Implemented

- FastAPI backend
- Application configuration
- Environment-based configuration
- Logging
- PostgreSQL database connection
- Docker PostgreSQL container
- Root API
- Health API

### Not Yet Implemented

- Video ingestion
- YOLO detection
- ByteTrack tracking
- Event intelligence
- Alert engine
- Evidence service
- React dashboard
- RTSP integration
- Authentication/RBAC
- ANPR/OCR
- Blockchain audit trail

---

## Architecture

```text
Existing CCTV
      |
      v
Video Ingestion
      |
      v
AI Analytics
      |
      v
Event Intelligence
      |
      v
Alert + Evidence
      |
      v
FastAPI
      |
      +------ PostgreSQL
      |
      +------ React Dashboard