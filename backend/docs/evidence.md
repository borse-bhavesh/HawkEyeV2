# Evidence Domain

## Purpose

Evidence provides references to source video/frame material that
supports observable Events and RiskAssessments.

## Evidence Types

FRAME

VIDEO_SEGMENT

## Frame Evidence

- frame_number
- timestamp_seconds

## Video Segment Evidence

- start_frame_number
- end_frame_number
- start_timestamp_seconds
- end_timestamp_seconds

## Source

- source_id
- source_type

## Traceability

Evidence can reference:

- event_id
- assessment_id

At least one must be present.

## Storage Independence

The Step 7.1 model does not store actual media.

It does not require filesystem paths, URLs, cloud storage, or
database persistence.

## Video Time Semantics

timestamps are video-relative.

Frame numbers are source-relative.

No wall-clock timestamps are used.

## Architecture

Video/Camera
    ↓
VideoFrame
    ↓
Event
    ↓
Evidence Reference
    ↓
RiskAssessment

Clarify that this step only establishes the Evidence contract.

## Human Review Boundary

Evidence supports human review and traceability.

It does not independently establish:

- criminality
- intent
- guilt
- threat certainty
- enforcement necessity

# Step 7.2 — Evidence Capture

## Purpose

Capture metadata for an existing VideoFrame.

## Flow

VideoFrame
    ↓
EvidenceCapture
    ↓
FrameEvidence

## Metadata

The captured reference contains:

- frame_number
- timestamp_seconds

## Image Handling

The actual image is NOT stored in FrameEvidence.

VideoFrame.image remains processing data.

## Timestamp

timestamp_seconds remains video-relative.

No wall-clock timestamp is generated.

## Storage

Step 7.2 does not persist media.

No:

- filesystem
- object storage
- database
- URL

is used.

## Determinism

Same VideoFrame metadata produces equivalent FrameEvidence.

## Architecture Boundary

EvidenceCapture does not open video sources or cameras.

It operates only on an already-produced VideoFrame.

## Terminology

Step 7.2 captures a frame reference, not a JPEG/PNG or physical media file.

# Step 7.3 — Evidence Media Materialization

## Purpose

Convert a captured FrameEvidence reference and VideoFrame into an actual deterministic local image file during development/testing.

## Distinctions

- **Step 7.2 Evidence Capture**: Captures only the logical metadata (`frame_number`, `timestamp_seconds`).
- **Step 7.3 Evidence Media Materialization**: Performs the synchronous I/O to create a `.jpg` representation on the local filesystem.

## Storage Strategy

This implementation is strictly local and deterministic for development purposes. It does not implement production cloud storage, S3 buckets, object storage, database blobs, or any deletion/retention policies.

## Deterministic File Naming

Frames are stored locally without random UUIDs or wall-clock timestamps using the strict format:

`<output_directory>/frames/<source_id>/frame_<frame_number>.jpg`

Path traversal vectors (e.g. `../`) are explicitly blocked via source identity validation.

## JPEG Output

Raw processing arrays (NumPy) are converted safely to JPEG using OpenCV. Original video arrays are never mutated.

# Step 7.4 — Evidence Media Retrieval

## Purpose

Provides a safe, local, synchronous layer to look up materialized evidence files without coupling other components to specific filesystem paths.

## Flow

FrameEvidence
    ↓
EvidenceMediaRetriever
    ↓
Local materialized path / metadata

## Read-Only Boundary

Retrieval is strictly read-only. It NEVER modifies, deletes, or recreates missing evidence. If a materialized file is missing, an explicit `EvidenceMediaNotFoundError` is raised instead of silently patching over the absence.

## Path Containment

The retriever does not trust arbitrary caller-supplied paths. It explicitly recalculates the expected deterministic path from the `Evidence` reference fields and performs containment checks (`relative_to`) on the resolved output to prevent directory traversal vectors (`../`, symlink attacks) from escaping the configured evidence root.

## Architecture

This is for local development filesystem retrieval. Database APIs, cloud object retrieval (S3), and lifecycle retention policies are distinctly segregated and not a part of Step 7.4. Furthermore, Event, Risk, and detection subsystems explicitly do not depend on the retriever.

# Step 7.5 — Video Segment Materialization

## Purpose

Provides local, deterministic materialization of `VIDEO_SEGMENT` evidence using OpenCV to extract a discrete clip from a caller-supplied source video.

## Extraction Strategy

- **Frame Numbering:** `start_frame` and `end_frame` are the authoritative bounding references (inclusive).
- **Format:** The segment is written using `.mp4` container and `mp4v` codec preserving native dimensions and FPS. No resizing occurs.
- **Verification:** Ensures exactly `end_frame - start_frame + 1` frames are successfully read and encoded.

## Reliability and Safety

- **Read-Only Source:** The source video path is strictly an input; it is never modified or rewritten.
- **Fail-Safe Cleanup:** If extraction aborts (e.g., unexpected EOF), the incomplete `.tmp.mp4` file is aggressively cleaned up so callers never encounter silent partial extractions.
- **Deterministic Storage:** Writes to `<output_directory>/segments/<source_id>/segment_<start>_<end>.mp4` without introducing wall-clock constraints, generating consistent idempotent results. 

## Non-Goals

Explicitly excludes production transcoders (FFmpeg, PyAV), cloud integrations, asynchronous background task dispatch, streaming (HLS), and database persistence.

# Step 7.6 — Video Segment Retrieval

## Purpose

Provides a secure, strictly read-only local filesystem retrieval mechanism for materialized video segments matching Step 7.5 outputs.

## Architecture

Just like Step 7.4 (frames), the caller presents `VideoSegmentEvidence` metadata, and the retriever explicitly recalculates the exact expected location.
- **Path Generation:** `<output_directory>/segments/<source_id>/segment_<start>_<end>.mp4`
- **Validation:** Bypasses entirely trusting caller pathing logic and enforces root containment to block symlink/traversal breaches.

## Data Retrieval

Operates fully as a metadata locator. The returned `MaterializedVideoSegmentEvidence` model describes the successful lookup, but the `.mp4` file is emphatically **not** decoded into RAM merely for retrieval validations. Missing segments are cleanly surfaced via `EvidenceMediaNotFoundError` to distinguish lookup omissions proactively. 

## Exclusions

Production features like cloud object retrieval (signed S3 URIs), REST/API retrieval logic, database query mapping, HLS media streaming pipelines, and authentication barriers are explicitly outside this localized metadata/path resolution architecture.

# Step 7.7 — Evidence Repository Abstraction

## Purpose

Introduces an `EvidenceRepository` interface to decouple the business logic of retrieving and linking evidence metadata (e.g., retrieving all evidence associated with a specific event or assessment) from the underlying storage mechanism.

## Metadata Persistence vs. Media Storage

It is critical to distinguish between **metadata** and **media**:
- **Media files** (JPEGs, MP4s) are handled entirely and safely by the materialization and retrieval layers (Steps 7.3 - 7.6). 
- **Metadata** (identities, timestamps, boundaries, event linkages) is managed by the `EvidenceRepository`. 

Repository operations (like `delete`) **do not delete media files**. They simply unlink the metadata record, preserving deterministic isolation and keeping the architecture untangled from complex lifecycle retention logic at this stage.

## Architecture

The `EvidenceRepository` defines an abstract Python protocol/ABC. Step 7.7 delivers a thread-safe `InMemoryEvidenceRepository` specifically for testing and deterministic local development.

- **PostgreSQL Independence:** No SQLAlchemy models, ORM mappings, database drivers, or migration scripts are introduced here. 
- **Defensive Copying:** The in-memory implementation uses Pydantic's `model_copy(deep=True)` heavily to prevent callers from leaking mutable state back into the repository dictionary, mimicking the strict serialization boundaries of an actual remote database.

