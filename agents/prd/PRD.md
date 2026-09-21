# Product Requirements Document

## Multi-Platform Video Uploader

### 1. Product Overview

**Product:** Multi-Platform Video Uploader

**Target platform:** Windows

**Technology stack:**

- Tauri
- Rust
- React
- TypeScript
- MUI
- Redux Toolkit

The application is a Windows desktop client for publishing videos to multiple social media and video platforms from a single interface.

Supported platforms:

- YouTube
- X
- Instagram
- TikTok

The user should be able to add a video once, configure common publication settings, select target platforms, and publish the video to all selected platforms in parallel.

The application should abstract platform-specific API differences behind a unified user experience.

---

# 2. Product Goals

The primary goals are:

1. Provide a single interface for publishing video content to multiple platforms.
2. Avoid entering the same information multiple times.
3. Upload to multiple platforms in parallel.
4. Provide independent status and progress for each platform.
5. Support scheduled publishing.
6. Use native platform scheduling when supported.
7. Fall back to local scheduling when native scheduling is unavailable and the platform permits the workflow.
8. Keep most application and business logic in the frontend.
9. Keep Rust limited to system-level functionality that benefits from native execution.
10. Make adding additional platforms straightforward.

---

# 3. Non-Goals

The MVP will not include:

- Video editing
- Video transcoding
- Subtitles editing
- AI-generated descriptions
- AI-generated hashtags
- AI-generated thumbnails
- Analytics
- Comments management
- Social media feed
- Team collaboration
- Cloud synchronization
- Mobile applications
- macOS support
- Linux support

---

# 4. Target Environment

The application targets:

**Windows 10/11**

Tauri provides the desktop application shell.

The architecture should not rely on Windows-specific APIs unless there is a clear benefit. However, Windows-native integrations may be introduced where they improve the user experience.

---

# 5. Core User Flow

The primary workflow is:

```text
Open application
      ↓
Drag & drop video
      ↓
Configure publication
      ↓
Select platforms
      ↓
Connect accounts if necessary
      ↓
Validate publication
      ↓
Click "Publish"
      ↓
Create platform tasks
      ↓
Upload in parallel
      ↓
Publish / Schedule
      ↓
Show result for each platform

```

Example:

```text
                    ┌── YouTube ──── Upload ── Publish
                    │
Video ── Prepare ───┼── X ────────── Upload ── Publish
                    │
                    ├── Instagram ── Upload ── Publish
                    │
                    └── TikTok ───── Upload ── Publish

```

A failure on one platform must not prevent other platforms from completing.

---

# 6. Main Screen

The main screen is the publication composer.

Suggested layout:

```text
┌──────────────────────────────────────────────────────────┐
│                    Video Uploader                        │
├──────────────────────────────────────────────────────────┤
│                                                          │
│              Drag & Drop Video Here                     │
│                                                          │
│              or [Choose File]                            │
│                                                          │
├──────────────────────────────────────────────────────────┤
│ Video                                                    │
│                                                          │
│ [Thumbnail]  video.mp4                                   │
│              245 MB · 1920x1080 · 00:42                  │
│                                                          │
├──────────────────────────────────────────────────────────┤
│ Title                                                    │
│ [____________________________________________________]   │
│                                                          │
│ Description                                              │
│ [____________________________________________________]   │
│ [____________________________________________________]   │
│                                                          │
│ Hashtags                                                 │
│ [ #video ] [ #tutorial ] [ #technology ]                │
│                                                          │
├──────────────────────────────────────────────────────────┤
│ Platforms                                                │
│                                                          │
│ ☑ YouTube       Connected                                │
│ ☑ X             Connected                                │
│ ☑ Instagram     Connected                                │
│ ☑ TikTok        Connected                                │
│                                                          │
├──────────────────────────────────────────────────────────┤
│ Publication                                              │
│                                                          │
│ ○ Publish now                                            │
│ ○ Schedule                                                │
│                                                          │
│                                      [ Publish ]         │
└──────────────────────────────────────────────────────────┘

```

---

# 7. Video Input

The application must support:

- Drag &amp; drop
- Windows file picker
- Removing the selected file
- Replacing the selected file

The application should display:

- File name
- File size
- MIME type
- Duration
- Resolution
- Thumbnail

Example:

```text
my-video.mp4
245 MB
1920 × 1080
00:42
MP4

```

The MVP supports one video per publication.

The architecture should allow multiple videos to be introduced later.

---

# 8. Common Publication Settings

The user should enter common information once.

## Title

```text
Title
[________________________________________]

```

## Description

```text
Description
[________________________________________]
[________________________________________]

```

## Hashtags

```text
Hashtags
[#video] [#technology] [#tutorial]

```

The application should normalize hashtag input.

The following inputs should produce the same internal representation:

```text
#video #technology #tutorial

```

and:

```text
video, technology, tutorial

```

Internal representation:

```typescript
string[]

```

Example:

```typescript
['video', 'technology', 'tutorial'];
```

Platform adapters are responsible for converting the common representation into the format required by the target API.

---

# 9. Platform Selection

The user can independently enable or disable platforms.

```text
Platforms

☑ YouTube
☑ X
☐ Instagram
☑ TikTok

```

Each platform displays its connection status.

Connected:

```text
YouTube
@channel_name

✓ Connected

```

Not connected:

```text
Instagram

Not connected

[Connect]

```

---

# 10. Platform-Specific Settings

Common settings should be shared across platforms whenever possible.

Platform-specific settings should be grouped separately.

Suggested UI:

```text
Platform Settings

[ YouTube ] [ X ] [ Instagram ] [ TikTok ]

```

Each tab exposes only settings relevant to that platform.

For example:

### YouTube

Potential settings:

- Visibility
- Category
- Made for kids
- Tags
- Playlist
- License

### X

Potential settings:

- Post text
- Media configuration
- Reply settings, where supported

### Instagram

Potential settings:

- Media type
- Caption
- Cover
- Other API-supported publication settings

### TikTok

Potential settings:

- Caption
- Privacy
- Comments
- Duet
- Stitch
- Cover
- Other API-supported publication settings

The exact set of fields must be based on the capabilities and restrictions of the official APIs.

---

# 11. Scheduling

The user can choose:

```text
Publication

○ Publish now
○ Schedule

```

For scheduled publication:

```text
Date
[ 12/09/2026 ]

Time
[ 18:00 ]

Timezone
[ Europe/Helsinki ]

```

The frontend should convert the selected local time to UTC.

Internal representation:

```typescript
scheduledAt: string;
```

Example:

```text
2026-09-12T15:00:00Z

```

The timezone should be explicitly stored or deterministically derived from the application settings.

---

# 12. Scheduling Strategy

Scheduling behavior is platform-dependent.

Each platform exposes its capabilities:

```typescript
interface PlatformCapabilities {
  scheduling: 'native' | 'local' | 'unsupported';
}
```

If native scheduling is supported:

```text
Frontend
   ↓
Platform API
   ↓
Native scheduled publication

```

If native scheduling is unavailable but local scheduling is possible:

```text
Frontend Scheduler
       ↓
Scheduled Task
       ↓
Scheduled time reached
       ↓
Upload
       ↓
Publish

```

If neither is possible:

```text
Schedule: Unsupported

```

The user should not need to understand these implementation details.

---

# 13. Platform Capability Model

The UI should be driven by platform capabilities rather than hardcoded assumptions.

Example:

```typescript
interface PlatformCapabilities {
  scheduling: 'native' | 'local' | 'unsupported';

  title: boolean;
  description: boolean;
  hashtags: boolean;

  drafts: boolean;

  maxFileSize?: number;
  supportedMimeTypes?: string[];
}
```

This allows the composer to dynamically adapt to platform limitations.

---

# 14. Domain Model

The frontend should use platform-independent domain models.

```typescript
interface VideoFile {
  id: string;
  path: string;
  name: string;
  size: number;
  duration?: number;
  width?: number;
  height?: number;
  mimeType: string;
  thumbnailPath?: string;
}
```

Publication:

```typescript
interface Publication {
  id: string;

  video: VideoFile;

  title: string;
  description: string;
  hashtags: string[];

  scheduledAt?: string;

  platforms: PlatformPublication[];
}
```

Platform-specific publication:

```typescript
interface PlatformPublication {
  platform: Platform;

  enabled: boolean;

  settings: PlatformSettings;

  status: PublicationStatus;

  progress: number;

  error?: PublicationError;
}
```

Platform:

```typescript
type Platform = 'youtube' | 'x' | 'instagram' | 'tiktok';
```

---

# 15. Publication Status

```typescript
type PublicationStatus =
  | 'idle'
  | 'validating'
  | 'preparing'
  | 'uploading'
  | 'processing'
  | 'publishing'
  | 'scheduled'
  | 'completed'
  | 'failed'
  | 'cancelled';
```

The status is maintained independently for every platform.

Example:

```text
YouTube       Completed
X             Uploading
Instagram     Failed
TikTok        Processing

```

---

# 16. Platform Adapter Architecture

Each platform must have its own adapter.

```typescript
interface PlatformAdapter {
  getCapabilities(): PlatformCapabilities;

  validate(publication: PlatformPublication): ValidationResult;

  upload(publication: PlatformPublication): Promise<UploadResult>;

  publish(publication: PlatformPublication): Promise<PublishResult>;

  schedule?(publication: PlatformPublication): Promise<ScheduleResult>;
}
```

Implementations:

```text
platforms/
├── youtube/
│   └── YouTubeAdapter
├── x/
│   └── XAdapter
├── instagram/
│   └── InstagramAdapter
└── tiktok/
    └── TikTokAdapter

```

The adapter is responsible for platform-specific API behavior.

The application layer should not contain YouTube/X/Instagram/TikTok-specific API details.

---

# 17. Upload Lifecycle

Each platform can have its own internal upload implementation, but the application should expose a common lifecycle:

```text
Validate
   ↓
Prepare
   ↓
Upload
   ↓
Process
   ↓
Publish / Schedule
   ↓
Completed

```

Important: the platform adapter must be allowed to implement a different internal lifecycle when required by its API.

The common lifecycle is an orchestration abstraction, not a restriction on platform implementations.

---

# 18. Parallel Publishing

When the user clicks `Publish`, one independent task is created for each selected platform.

Conceptually:

```typescript
const tasks = selectedPlatforms.map((platform) => publishToPlatform(platform));

const results = await Promise.allSettled(tasks);
```

`Promise.allSettled()` should be used so that a failure on one platform does not terminate the other publication tasks.

Example:

```text
YouTube       ████████████████████ 100% ✓

X             ████████████░░░░░░░░  60%
              Uploading...

Instagram     ████████████████████ 100% ✓

TikTok        ██████░░░░░░░░░░░░░░  30%
              Failed
              API error

```

---

# 19. Upload Progress

Each platform must have independent progress.

```typescript
interface UploadProgress {
  platform: Platform;

  status: PublicationStatus;

  uploadedBytes?: number;
  totalBytes?: number;

  percent?: number;
}
```

If the platform does not provide real upload progress, the UI should use an indeterminate progress indicator.

---

# 20. Redux Architecture

Redux Toolkit is the source of truth for application state.

Suggested state:

```typescript
interface AppState {
  accounts: AccountsState;
  composer: ComposerState;
  publications: PublicationsState;
  settings: SettingsState;
}
```

Composer:

```typescript
interface ComposerState {
  video?: VideoFile;

  title: string;
  description: string;
  hashtags: string[];

  scheduledAt?: string;

  selectedPlatforms: Platform[];

  platformSettings: Record<Platform, PlatformSettings>;
}
```

Publications:

```typescript
interface PublicationsState {
  items: Record<string, PublicationTask>;
}
```

---

# 21. Frontend Architecture

Suggested structure:

```text
src/
├── app/
│   ├── store/
│   ├── router/
│   └── providers/
│
├── domain/
│   ├── publication/
│   ├── platform/
│   └── video/
│
├── features/
│   ├── composer/
│   ├── accounts/
│   ├── publications/
│   └── settings/
│
├── platforms/
│   ├── youtube/
│   ├── x/
│   ├── instagram/
│   └── tiktok/
│
├── services/
│   ├── upload/
│   ├── scheduler/
│   ├── filesystem/
│   └── auth/
│
├── components/
│   ├── VideoDropZone/
│   ├── PlatformSelector/
│   ├── UploadProgress/
│   └── ...
│
└── main.tsx

```

Recommended dependency direction:

```text
React UI
   ↓
Redux
   ↓
Application Services
   ↓
Platform Adapters
   ↓
Platform APIs

```

---

# 22. Rust / Tauri Responsibilities

Rust should be intentionally thin.

Rust should handle operations such as:

- filesystem access;
- large-file operations;
- file metadata;
- thumbnail generation if native processing is required;
- secure credential storage;
- Windows-specific system integration;
- native background/scheduling integration if required;
- functionality that cannot reasonably be implemented in the WebView.

Example:

```rust
#[tauri::command]
fn get_file_metadata(
    path: String
) -> Result<FileMetadata, AppError>

```

Potential file access abstraction:

```rust
#[tauri::command]
fn read_file_chunk(
    path: String,
    offset: u64,
    size: u64
) -> Result<Vec<u8>, AppError>

```

Rust should NOT contain:

- platform business logic;
- Redux state;
- UI state;
- platform-specific validation rules;
- scheduling decisions;
- retry policy;
- platform selection logic;
- platform API mapping unless technically required.

---

# 23. Large File Handling

Video files can be several gigabytes.

The application should avoid unnecessarily loading an entire video into JavaScript memory.

The frontend should work through an abstraction such as:

```typescript
interface FileReader {
  size(): Promise<number>;

  read(offset: number, size: number): Promise<Uint8Array>;
}
```

The implementation can use Tauri/Rust when native file access is preferable.

Platform adapters should depend on the abstraction rather than directly accessing the Windows filesystem.

---

# 24. Authentication

Each platform requires an independent account connection.

Example:

```text
Connected Accounts

YouTube
@channel
✓ Connected
[Disconnect]

X
@username
✓ Connected
[Disconnect]

Instagram
Not connected
[Connect]

TikTok
@username
✓ Connected
[Disconnect]

```

Official OAuth flows must be used.

The frontend should not expose or persist sensitive credentials in Redux.

Redux should contain only non-sensitive account information:

```typescript
interface ConnectedAccount {
  id: string;
  platform: Platform;
  displayName: string;
  avatarUrl?: string;
}
```

Tokens and secrets should be stored in an appropriate secure storage mechanism.

---

# 25. Authentication Abstraction

The platform-specific authentication implementation should be isolated.

```typescript
interface PlatformAuth {
  connect(): Promise<ConnectedAccount>;

  disconnect(accountId: string): Promise<void>;

  getAccount(): Promise<ConnectedAccount>;
}
```

Each platform can implement its own OAuth flow.

---

# 26. Validation

Validation must occur before uploads start.

Global validation includes:

- Video file exists
- File is readable
- Supported format
- Valid title
- Valid description
- Valid hashtags
- Valid scheduled time
- At least one platform selected
- Required account connected

Platform validation includes:

- File size
- Duration
- Resolution
- Format
- Platform-specific fields
- Platform-specific content restrictions
- Account permissions

Example:

```text
Publication validation

YouTube       ✓
X             ✓
Instagram     ✗ Video format is not supported
TikTok        ✓

```

Validation errors should identify the exact platform and field causing the problem.

---

# 27. Error Handling

Errors should be classified:

```typescript
type ErrorType =
  | 'network'
  | 'authentication'
  | 'authorization'
  | 'validation'
  | 'rate_limit'
  | 'platform'
  | 'file'
  | 'unknown';
```

The UI should provide a human-readable error.

Example:

```text
TikTok upload failed

Your access token has expired.

[Reconnect TikTok]
[Retry]

```

Technical information can be exposed through a `Details` action.

---

# 28. Retry

Transient errors should support retry.

Examples:

- network failure;
- temporary server error;
- timeout;
- rate limit where retry is appropriate.

Retry should use exponential backoff for automatic retries.

The application should not automatically retry:

- validation errors;
- invalid credentials;
- insufficient permissions;
- permanently rejected content.

Manual retry should remain available where appropriate.

---

# 29. Cancellation

Each platform task should be independently cancellable.

Example:

```text
YouTube
Uploading — 72%

[Cancel]

```

Cancelling YouTube must not cancel:

```text
X
Instagram
TikTok

```

The application should propagate cancellation to the underlying upload operation whenever the platform API and HTTP implementation support it.

---

# 30. Publication Monitoring

After starting a publication, the UI should provide a monitoring view.

Example:

```text
Publishing

Video:
my-video.mp4

YouTube
Uploading — 73%
██████████████░░░░░░

X
Processing...

Instagram
Completed ✓

TikTok
Uploading — 31%
██████░░░░░░░░░░░░░░

```

At the end:

```text
Publication completed

YouTube       ✓ Published
X             ✓ Published
Instagram     ✓ Published
TikTok        ✗ Failed

[Retry failed]
[Done]

```

---

# 31. Publication History

The application should maintain a local history of publications.

Each entry contains:

- Thumbnail
- Video name
- Title
- Publication date
- Platforms
- Overall status

Example:

```text
History

┌────────┬──────────────────┬──────────────┐
│ Video  │ Title            │ Status       │
├────────┼──────────────────┼──────────────┤
│ image  │ My first video   │ ✓ 4/4        │
│ image  │ Product demo     │ ⚠ 3/4        │
│ image  │ Tutorial         │ ✗ 0/4        │
└────────┴──────────────────┴──────────────┘

```

Opening an entry shows the individual platform results.

---

# 32. Persistence

The application should persist:

- Application settings
- Connected account metadata
- Scheduled publications
- Publication history
- In-progress publication metadata

The original video file should not be copied into application storage unnecessarily.

The application should store the source file path.

If the file no longer exists:

```text
The source video is no longer available.

[Select File]

```

---

# 33. Local Scheduler

The local scheduler is responsible for publications that cannot be scheduled natively.

The MVP may require the application to be running when a locally scheduled publication is due.

Example:

```text
Scheduled Publication
        ↓
Local Scheduler
        ↓
Scheduled time reached
        ↓
Start upload
        ↓
Publish

```

A future version may integrate with Windows Task Scheduler or another Windows background mechanism to launch the application automatically.

This should remain isolated from platform adapters.

---

# 34. Concurrency Management

Publications should execute in parallel by default.

However, the architecture must support a configurable concurrency limit.

Example:

```typescript
maxConcurrentUploads: 4;
```

For one publication:

```text
YouTube   ────────────┐
X         ────────────┤
Instagram ────────────┤ parallel
TikTok    ────────────┘

```

For future multi-video support:

```text
Video 1 → YouTube
Video 1 → X
Video 2 → waiting
Video 3 → waiting

```

Concurrency management belongs to the frontend application layer.

---

# 35. Settings

## General

- Application language
- Theme
- Default hashtags
- Default publication settings

## Accounts

- Connected accounts
- Disconnect accounts

## Upload

- Maximum concurrent uploads
- Automatic retry count
- Chunk size
- Bandwidth limit

## Scheduler

- Timezone
- Behavior on application startup
- Windows background scheduling

---

# 36. Logging

The application should use structured logging.

Example:

```typescript
logger.info('Upload started', {
  platform,
  publicationId,
});
```

Sensitive information must never be logged.

Never log:

- Access tokens
- Refresh tokens
- Client secrets
- Authorization codes
- Cookies
- Full authorization headers

---

# 37. Security Requirements

1. OAuth credentials must not be stored in Redux.
2. Tokens must not be stored in plaintext application configuration.
3. Sensitive credentials should use Windows secure credential storage where appropriate.
4. API communication must use HTTPS.
5. Tokens must never appear in logs.
6. Disconnecting an account must remove its stored credentials.
7. Renderer-to-Rust communication should expose only the minimum required Tauri commands.
8. File-system access should be restricted to explicitly required operations.

---

# 38. Windows-Specific Requirements

The application should provide a native Windows desktop experience.

Potential Windows integrations:

- Native file picker
- Windows notifications
- Windows Task Scheduler for background scheduled publications
- Secure credential storage
- Application auto-start where explicitly enabled
- System tray integration

Windows-specific functionality should be implemented behind platform abstractions where practical so that it does not contaminate the core application layer.

---

# 39. MVP Scope

### Platforms

- YouTube
- X
- Instagram
- TikTok

### Video

- Drag &amp; drop
- Windows file picker
- Video preview
- File metadata
- Thumbnail

### Publication

- Title
- Description
- Hashtags
- Platform selection
- Immediate publishing

### Scheduling

- Date/time selection
- Timezone support
- Native scheduling where supported
- Local scheduling where required and supported

### Upload

- Parallel uploads
- Individual progress
- Individual status
- Individual errors
- Retry
- Cancellation

### Accounts

- OAuth connection
- Account information
- Disconnect

### Persistence

- Settings
- Account metadata
- Scheduled publications
- Publication history

---

# 40. Future Features

The architecture should allow adding:

- Multiple videos per publication
- Multiple accounts per platform
- Video transcoding
- Video trimming
- Thumbnail editor
- Subtitle support
- AI-generated metadata
- Analytics
- Publishing templates
- Content calendar
- Windows Task Scheduler integration
- Upload queue
- Bandwidth management
- Cloud synchronization

---

# 41. Acceptance Criteria

## Video Upload

**Given** the user is on the main screen.

**When** they drag a supported video into the drop zone.

**Then** the video appears in the composer and its metadata is displayed.

---

## Platform Selection

**Given** a video has been selected.

**When** the user selects YouTube, X, Instagram, and TikTok.

**Then** four independent publication targets are created.

---

## Publishing

**Given** the publication is valid and all selected accounts are connected.

**When** the user clicks `Publish`.

**Then** the application starts the selected platform tasks.

---

## Parallel Execution

**Given** four platforms are selected.

**When** publishing starts.

**Then** the platform upload operations execute concurrently, subject to the configured concurrency limit.

---

## Failure Isolation

**Given** Instagram returns an API error.

**When** the publication is running.

**Then** YouTube, X, and TikTok continue independently.

---

## Retry

**Given** TikTok fails due to a transient error.

**When** the user clicks `Retry`.

**Then** only the failed TikTok task is retried.

Successfully published platforms must not be published again.

---

## Scheduling

**Given** a platform supports native scheduling.

**When** the user schedules a publication.

**Then** the scheduled publication is created through the platform API.

**Given** native scheduling is unavailable but local scheduling is supported.

**When** the user schedules a publication.

**Then** the application creates a local scheduled task.

---

## Persistence

**Given** the application contains scheduled or in-progress publications.

**When** the application is restarted.

**Then** the application restores the relevant publication state and scheduled tasks.

---

# 42. Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                         React UI                            │
│                          MUI                                │
├─────────────────────────────────────────────────────────────┤
│                      Redux Toolkit                          │
│                  Application State                          │
├─────────────────────────────────────────────────────────────┤
│                    Application Layer                        │
│                                                             │
│ Composer │ Publisher │ Scheduler │ Upload Manager           │
├─────────────────────────────────────────────────────────────┤
│                      Platform Layer                         │
│                                                             │
│ YouTube │ X │ Instagram │ TikTok                            │
│                     Adapters                                │
├─────────────────────────────────────────────────────────────┤
│                       Tauri API                             │
├─────────────────────────────────────────────────────────────┤
│                          Rust                               │
│                                                             │
│ Files │ Secure Storage │ Windows APIs │ Native Operations    │
└─────────────────────────────────────────────────────────────┘

```

The key architectural principle is:

```text
Business logic
      ↓
TypeScript / React

Application state
      ↓
Redux Toolkit

Platform API integration
      ↓
TypeScript platform adapters

System-level functionality
      ↓
Rust / Tauri

```

Rust should remain a thin native layer rather than becoming a second application backend.

---

# 43. Definition of Done

The MVP is complete when a user can perform the following workflow:

```text
Launch application
        ↓
Drag video
        ↓
Enter title
        ↓
Enter description / hashtags
        ↓
Select platforms
        ↓
Connect accounts
        ↓
Select "Publish now"
        ↓
Click "Publish"
        ↓
 ┌──────┬──────┬───────────┬────────┐
 ↓      ↓      ↓           ↓
YouTube X   Instagram    TikTok
 ↓      ↓      ↓           ↓
Upload Upload Upload      Upload
 ↓      ↓      ↓           ↓
Publish Publish Publish   Publish
 └──────┴──────┴───────────┴────────┘
        ↓
Publication Result

```

The application must:

- Run on Windows.
- Support all four target platforms.
- Allow a video to be added using drag &amp; drop.
- Allow common publication settings to be entered once.
- Allow platform-specific settings.
- Authenticate through official OAuth mechanisms.
- Upload to selected platforms in parallel.
- Display independent progress and status.
- Isolate platform failures.
- Support retry and cancellation.
- Support scheduled publishing according to platform capabilities.
- Persist required application state.
- Keep sensitive credentials out of Redux and logs.
- Keep business logic primarily in TypeScript.
- Use Rust only for native/system-level responsibilities.
