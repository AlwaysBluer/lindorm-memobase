# LindormMemobase Overview

This note summarizes data structures, data flow, and basic usage for the repo.

## Data Structures

- Blob system: `BlobType`, `Blob`, `ChatBlob`, `DocBlob`, `CodeBlob`, `ImageBlob`, `TranscriptBlob`, and message units (`OpenAICompatibleMessage`, `TranscriptStamp`). `lindormmemobase/models/blob.py`
- Profile config: `ProfileConfig`, `UserProfileTopic`, `SubTopic`, `EventTag` define topics/subtopics and event tagging. `lindormmemobase/models/profile_topic.py`
- API/result models: `ProfileEntry`/`Profile` for user-facing profiles, and `ProfileData`, `ChatModalResponse`, `EventData`, `UserEventData` for storage/API responses. `lindormmemobase/models/types.py`, `lindormmemobase/models/response.py`
- Buffer storage table: `BufferStorage` schema for queued blobs with token sizes and status. `lindormmemobase/core/storage/buffers.py`
- Core tables: `UserProfiles`, `UserEvents`, `UserEventsGists` plus search/vector indices. `lindormmemobase/core/storage/user_profiles.py`, `lindormmemobase/core/storage/events.py`, `lindormmemobase/core/storage/event_gists.py`

## Data Flow

- Entry paths:
  - Direct: build `Blob` list and call `LindormMemobase.extract_memories`.
  - Buffered: `add_blob_to_buffer` -> `detect_buffer_full_or_not` -> `process_buffer`.
  `lindormmemobase/main.py`
- Extraction pipeline:
  - `process_blobs`: truncate -> `entry_chat_summary` -> parallel `process_profile_res` + `process_event_res`.
  - `process_profile_res`: `extract_topics` -> `merge_or_valid_new_profile` -> `organize_profiles` -> `re_summary`.
  `lindormmemobase/core/extraction/processor/process_blobs.py`
- Persistence:
  - `handle_session_event`, `handle_session_event_gists`, `handle_user_profile_db` write events, event gists, and profiles.
  `lindormmemobase/core/extraction/processor/process_blobs.py`
- Context retrieval:
  - `get_user_context` pulls profiles + event gists in parallel, then composes context under token budget.
  `lindormmemobase/core/search/context.py`

## Basic Usage (Short)

- Initialize: load config via `.env` + `config.yaml`, or `LindormMemobase.from_yaml_file`.
  `README.md`, `docs/API-Usage-Guide.md`
- Extract memories:
  - Create `ChatBlob` (or other blob types) and call `extract_memories(user_id, blobs)`.
  `lindormmemobase/main.py`
- Buffer processing:
  - `add_blob_to_buffer` -> `detect_buffer_full_or_not` -> `process_buffer`.
  `lindormmemobase/main.py`
- Read results:
  - `get_user_profiles` or `get_conversation_context` for downstream usage.
  `lindormmemobase/main.py`
