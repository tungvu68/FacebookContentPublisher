# Facebook Content Publisher Desktop

## 1. Tổng quan

### 1.1 Mục tiêu

Xây dựng ứng dụng desktop Windows cho một người vận hành, hỗ trợ:

1. Nhập nội dung nguồn bằng tiếng Anh.
2. Chọn nhiều quốc gia và ngôn ngữ đích.
3. Dịch và bản địa hóa nội dung bằng OpenAI API.
4. Xem trước, chỉnh sửa và phê duyệt từng bản dịch.
5. Gắn ảnh hoặc video.
6. Đăng nội dung lên Facebook Page tương ứng của từng quốc gia.
7. Lưu Facebook Post ID sau khi đăng thành công.
8. Tự động comment link đúng ngôn ngữ sau khoảng thời gian cấu hình, mặc định 5 giờ 30 phút.
9. Theo dõi trạng thái, retry khi lỗi và chống đăng trùng.
10. Lưu dữ liệu chính trên máy người dùng.

### 1.2 Loại ứng dụng

- Desktop Windows, không yêu cầu web server cho chức năng chính.
- Có thể thu nhỏ xuống system tray và chạy nền khi Windows còn hoạt động.
- Đóng gói thành `.exe` bằng PyInstaller.
- MVP phục vụ một người dùng trên một máy.
- Khi máy tắt, job không thể chạy; khi mở lại, ứng dụng phải phục hồi job quá hạn.

## 2. Phạm vi MVP

MVP bắt buộc có:

- Quản lý cấu hình quốc gia/ngôn ngữ/Page/link.
- Nhập nội dung tiếng Anh và chọn nhiều quốc gia.
- Đính kèm ảnh hoặc video.
- Dịch hàng loạt bằng OpenAI Responses API.
- Review, chỉnh sửa và phê duyệt bản dịch.
- OpenAI mock mode và production mode.
- Facebook mock mode và production adapter.
- Đăng ngay hoặc lên lịch.
- Comment link sau một khoảng thời gian.
- SQLite database và migration.
- Scheduler lưu bền vững, phục hồi sau restart.
- Retry có backoff và chống đăng trùng.
- Logging có che thông tin bí mật.
- Lưu secret bằng Windows Credential Manager.
- Unit/integration tests không cần Internet.
- Script build `.exe` và README đầy đủ.

Ngoài phạm vi MVP:

- Facebook Ads Manager và tự động quản lý quảng cáo trả phí.
- Tạo/nuôi tài khoản Facebook hoặc đăng lên profile cá nhân.
- Né checkpoint, rate limit, App Review hoặc kiểm duyệt Meta.
- Web dashboard nhiều người dùng và đồng bộ nhiều máy.
- OCR/thay chữ trong ảnh, lồng tiếng hoặc burn subtitle.
- Thanh toán hoặc subscription.

## 3. Công nghệ bắt buộc

- Python 3.12.
- PySide6 cho giao diện.
- SQLite + SQLAlchemy 2.x.
- Alembic cho database migration.
- Pydantic cho validation/schema.
- OpenAI Python SDK chính thức.
- HTTPX cho HTTP client.
- APScheduler hoặc scheduler tương đương.
- Tenacity hoặc retry mechanism tương đương.
- `keyring` cho Windows Credential Manager.
- PyInstaller cho đóng gói Windows.
- Pytest cho test.
- Ruff cho lint/format.
- Mypy cho type checking nếu khả thi.

Kiến trúc phân lớp:

```text
UI
  ↓
Application / Use Cases
  ↓
Domain
  ↓
Infrastructure
```

OpenAI, Facebook, database, scheduler và secret storage phải nằm sau interface riêng để mock/test. Không đặt business logic trực tiếp trong PySide6 widget.

## 4. Cấu trúc dự án đề xuất

```text
FaceBookAutoApp/
├── src/
│   └── facebook_content_publisher/
│       ├── __init__.py
│       ├── main.py
│       ├── config.py
│       ├── domain/
│       │   ├── models/
│       │   ├── enums.py
│       │   ├── exceptions.py
│       │   └── interfaces/
│       ├── application/
│       │   ├── dto/
│       │   ├── services/
│       │   └── use_cases/
│       ├── infrastructure/
│       │   ├── database/
│       │   ├── openai/
│       │   ├── facebook/
│       │   ├── scheduler/
│       │   ├── security/
│       │   ├── media/
│       │   └── logging/
│       └── ui/
│           ├── windows/
│           ├── pages/
│           ├── dialogs/
│           ├── widgets/
│           ├── workers/
│           └── resources/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── migrations/
├── scripts/
├── resources/
├── docs/
├── .env.example
├── .gitignore
├── alembic.ini
├── pyproject.toml
├── PROJECT_REQUIREMENTS.md
└── README.md
```

Codex có thể điều chỉnh cấu trúc khi có lý do kỹ thuật rõ ràng nhưng phải giữ kiến trúc phân lớp, mockability và testability.

## 5. Người dùng

MVP chỉ có vai trò `Operator`, có thể:

- Cấu hình OpenAI và Facebook.
- Quản lý quốc gia, Page và link.
- Tạo campaign, dịch, review và phê duyệt.
- Đăng bài, lên lịch comment và retry job.
- Xem trạng thái, lỗi và activity log.

Không cần đăng nhập nội bộ trong MVP.

## 6. Mô hình dữ liệu

Tất cả ID nội bộ nên dùng UUID; timestamp lưu UTC và hiển thị theo timezone của CountryProfile.

### 6.1 CountryProfile

- `id`
- `code` duy nhất
- `country_name`
- `language_code`, ví dụ `th-TH`, `id-ID`, `pt-BR`
- `language_name`
- `timezone` theo IANA
- `facebook_page_id`, nullable
- `facebook_page_name`, nullable
- `default_link`, nullable
- `default_comment_template`
- `translation_prompt_override`, nullable
- `default_hashtags`, nullable
- `enabled`
- `created_at`, `updated_at`

Ví dụ:

```json
{
  "code": "TH",
  "country_name": "Thailand",
  "language_code": "th-TH",
  "language_name": "Thai",
  "timezone": "Asia/Bangkok",
  "default_link": "https://example.com/th",
  "default_comment_template": "ดูรายละเอียดเพิ่มเติม: {link}",
  "enabled": true
}
```

### 6.2 Campaign

- `id`, `title`
- `source_language`, mặc định `en`
- `source_text`
- `status`
- `created_at`, `updated_at`

Trạng thái: `DRAFT`, `TRANSLATING`, `READY_FOR_REVIEW`, `APPROVED`, `PUBLISHING`, `PARTIALLY_PUBLISHED`, `PUBLISHED`, `FAILED`, `ARCHIVED`.

### 6.3 MediaAsset

- `id`, `campaign_id`
- `file_name`, `absolute_path`
- `media_type`: `IMAGE` hoặc `VIDEO`
- `mime_type`, `file_size`, `sha256`
- `created_at`

Không xóa hoặc thay đổi file gốc ngoài ý muốn. Nếu quản lý bản sao, lưu trong application data directory.

### 6.4 LocalizedContent

- `id`, `campaign_id`, `country_profile_id`
- `language_code`
- `translated_text`, `comment_text`
- `hashtags`, `link_url`
- `translation_status`
- `quality_warnings`
- `prompt_version`, `model_name`
- `approved_at`, nullable
- `created_at`, `updated_at`

Trạng thái: `PENDING`, `TRANSLATING`, `TRANSLATED`, `NEEDS_REVIEW`, `APPROVED`, `REJECTED`, `FAILED`.

### 6.5 Publication

- `id`, `campaign_id`, `localized_content_id`, `country_profile_id`
- `facebook_page_id`
- `publish_mode`: `IMMEDIATE` hoặc `SCHEDULED`
- `scheduled_at_utc`, `published_at_utc`
- `facebook_post_id`, `facebook_post_url`
- `status`, `attempt_count`
- `last_error_code`, `last_error_message`
- `idempotency_key` duy nhất
- `created_at`, `updated_at`

Trạng thái: `DRAFT`, `SCHEDULED`, `RUNNING`, `PUBLISHED`, `RETRY_WAIT`, `FAILED`, `CANCELLED`, `UNKNOWN_RESULT`.

### 6.6 CommentJob

- `id`, `publication_id`
- `execute_at_utc`
- `comment_text`, `link_url`
- `facebook_comment_id`
- `status`, `attempt_count`
- `next_retry_at_utc`
- `last_error_code`, `last_error_message`
- `idempotency_key` duy nhất
- `created_at`, `updated_at`

Trạng thái: `PENDING`, `RUNNING`, `COMPLETED`, `RETRY_WAIT`, `FAILED`, `CANCELLED`, `UNKNOWN_RESULT`.

### 6.7 ActivityLog

- `id`, `level`, `event_type`
- `entity_type`, `entity_id`
- `safe_message`, `created_at`

Không lưu API key, access token, App Secret, authorization code hoặc Authorization header.

## 7. Giao diện

### 7.1 Main Window

Sidebar:

- Dashboard
- New Campaign
- Campaigns
- Scheduled Jobs
- Countries
- Facebook Pages
- Settings
- Logs

Status bar hiển thị trạng thái OpenAI, Facebook mock/production, scheduler, số job chờ và kết nối mạng.

### 7.2 Dashboard

- Campaign gần đây.
- Bài đăng hôm nay.
- Comment job đang chờ/thất bại.
- Cảnh báo token/cấu hình.
- Nút tạo campaign.

### 7.3 New Campaign

- Tên campaign.
- Nội dung tiếng Anh.
- Chọn nhiều quốc gia.
- Kéo thả ảnh/video.
- Đăng ngay hoặc lên lịch.
- Chọn thời gian comment.
- Link mặc định hoặc link riêng.
- Nút `Generate Translations`.

Validation: source text không rỗng, có ít nhất một quốc gia, media tồn tại/đọc được và cảnh báo khi thiếu link/comment template.

### 7.4 Translation Review

Hiển thị source và từng bản dịch gồm post text, comment, link, hashtag, quality warning, số ký tự và trạng thái. Có `Regenerate`, `Save`, `Approve`, `Approve All`, `Reject` và `Return to Draft`.

Mặc định không đăng nội dung chưa approve. Auto-approve chỉ hoạt động khi người dùng chủ động bật.

### 7.5 Scheduled Jobs

Hiển thị loại job, campaign, Page/quốc gia, thời gian local/UTC, trạng thái, số lần thử và lỗi gần nhất. Có `Run now`, `Retry`, `Cancel`, `Reschedule` và mở campaign liên quan.

### 7.6 Countries

CRUD CountryProfile; không cho trùng `code`.

### 7.7 Facebook Pages

Hiển thị mode, Page ID/name, quốc gia, trạng thái kết nối/quyền và lần kiểm tra. Có `Connect`, `Disconnect`, `Test connection`, `Assign country`, `Refresh Pages`.

### 7.8 Settings

- General: data directory, start with Windows, minimize to tray, comment delay, timezone.
- OpenAI: key status, model, global prompt, timeout, concurrency, test connection.
- Facebook: mock/production, App ID, App Secret status, OAuth, Graph API version.
- Retry: attempts, delays, multiplier.
- Logs: level, directory, retention.

Không hiển thị lại toàn bộ secret sau khi lưu.

## 8. OpenAI integration

### 8.1 Nguyên tắc

- Dùng OpenAI Python SDK chính thức và Responses API.
- Chỉ gọi qua service layer, không gọi trực tiếp từ UI.
- API key đọc từ Windows Credential Manager.
- Có timeout, cancellation, concurrency limit và retry.
- Ghi request ID nếu có nhưng không log secret.
- Có `MockTranslationService` và `OpenAITranslationService`.

### 8.2 Structured output

Model phải trả schema tương đương:

```json
{
  "language_code": "th-TH",
  "post_text": "string",
  "comment_text": "string",
  "hashtags": ["string"],
  "quality_warnings": ["string"]
}
```

Validate bằng Pydantic. Output sai schema được retry giới hạn; nếu vẫn sai, đánh dấu `FAILED` và không crash app.

### 8.3 Prompt mặc định

```text
You are a professional social media localization specialist.

Translate and localize the supplied English Facebook content for the
specified target country and locale.

Requirements:
- Preserve the original meaning, intent, factual claims, brand names,
  product names, URLs and calls to action.
- Write naturally for native speakers of the target locale.
- Do not invent facts, discounts, guarantees, urgency or product claims.
- Preserve required placeholders exactly.
- Adapt tone, punctuation and date/number formatting when appropriate.
- Keep the content suitable for a Facebook Page.
- Produce a separate post text and delayed comment text.
- The delayed comment may contain the supplied link.
- Do not place the link in the post unless explicitly requested.
- Return only data matching the required output schema.
```

Country prompt có thể mở rộng prompt chung nhưng không được làm sai nội dung nguồn. Lưu `prompt_version` và `model_name` cho mỗi bản dịch.

## 9. Facebook integration

### 9.1 Nguyên tắc

- Chỉ dùng Meta/Facebook Graph API chính thức.
- Không dùng Selenium/browser bot để thay thế API.
- Không lưu mật khẩu Facebook.
- Không vượt checkpoint, rate limit hoặc App Review.
- Chỉ thao tác Page mà người dùng có quyền phù hợp.
- Graph API version cấu hình tập trung, không hard-code rải rác.

### 9.2 Interface

```python
class FacebookPublisher(Protocol):
    async def list_pages(self) -> list[FacebookPage]: ...
    async def validate_page_access(self, page_id: str) -> PageAccessStatus: ...
    async def publish_text_post(self, request: PublishRequest) -> PublishResult: ...
    async def publish_photo_post(self, request: PublishRequest) -> PublishResult: ...
    async def publish_video_post(self, request: PublishRequest) -> PublishResult: ...
    async def create_comment(self, request: CommentRequest) -> CommentResult: ...
```

Implementations:

- `MockFacebookPublisher`
- `GraphApiFacebookPublisher`

### 9.3 Mock mode

- Không cần credentials.
- Sinh Page/Post/Comment ID giả.
- Mô phỏng success, timeout, rate limit, permission và auth error.
- Dùng trong automated tests.
- UI phải hiển thị rõ `MOCK MODE`, tránh hiểu nhầm đã đăng thật.

### 9.4 Production mode

- Dùng Page access token.
- Kiểm tra Page access trước khi đăng.
- Hỗ trợ text, photo, video nếu API/quyền cho phép.
- Lưu Post ID từ response và dùng để comment.
- Phân loại lỗi: authentication, permission, rate limit, network, invalid media, invalid request, server và unknown.
- Không retry vô hạn lỗi auth/permission.
- Không log token.

Các permission dự kiến gồm `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`, `pages_manage_engagement`; phải xác minh với tài liệu Meta hiện hành khi triển khai và không coi đây là bảo đảm App Review.

### 9.5 OAuth

- Mở trình duyệt hệ thống.
- Dùng `state` và PKCE nếu Meta hỗ trợ.
- Callback localhost hoặc custom URI scheme.
- Validate `state`.
- Không nhập username/password trong app.
- Không log code/token.
- Có disconnect và xóa token.

Nếu OAuth chưa hoàn tất do thiếu Meta configuration, phải hoàn thiện mock mode, interface, adapter skeleton và tài liệu setup; không hard-code token mẫu.

## 10. Luồng đăng và comment

1. Tạo campaign.
2. Chọn CountryProfile.
3. Dịch và review.
4. Approve.
5. Tạo Publication cho từng quốc gia.
6. Worker lock và nhận job.
7. Đăng bài.
8. Lưu Post ID và thời gian đăng thực tế.
9. Tạo CommentJob dựa trên `published_at_utc`.
10. Worker comment khi đến hạn.

Delay mặc định là 5 giờ 30 phút, có thể thay đổi hoặc tắt comment. Thời gian comment phải tính từ lúc đăng thành công, không phải lúc bấm nút.

### 10.1 Scheduler bền vững

- Mọi job được ghi SQLite trước khi chạy.
- Khi mở app, phục hồi job `RUNNING` bị gián đoạn và job đến hạn.
- Dùng transaction/locking để một job chỉ có một worker xử lý.
- Nếu máy tắt, khi mở lại hiển thị cảnh báo và mặc định chạy job quá hạn nếu chưa hủy.
- Nếu kết quả API không rõ do timeout, đánh dấu `UNKNOWN_RESULT` thay vì retry mù quáng.

### 10.2 Retry

Mặc định tối đa 5 lần, exponential backoff có jitter, delay đầu 30 giây và tối đa 30 phút.

Retry: timeout, mất mạng, HTTP 429, lỗi tạm thời và một số 5xx.

Không auto-retry: key/token sai, thiếu permission, media không tồn tại, request/content không hợp lệ hoặc job bị hủy.

## 11. Media

MVP hỗ trợ JPG/JPEG, PNG, WEBP nếu Meta hỗ trợ và MP4. Kiểm tra file tồn tại, quyền đọc, MIME, size, SHA-256 và giới hạn Meta hiện hành.

Không làm OCR, thay chữ, voice-over, subtitle rendering hay video compression nâng cao trong MVP. Có thể bổ sung FFmpeg sau.

## 12. Bảo mật

Secret gồm OpenAI API key, Meta App Secret, Page/User token và refresh token nếu có.

- Lưu secret bằng Windows Credential Manager qua `keyring`.
- Không lưu plaintext trong SQLite hoặc source.
- `.env` chỉ dùng development và phải nằm trong `.gitignore`.
- `.env.example` không chứa secret.
- Không hiển thị toàn bộ secret trên UI.
- Không log secret/Authorization header/query token.
- Có chức năng xóa local credential.
- Tự động redact Bearer token, API key, App Secret, auth code và sensitive header.

## 13. System tray và background

- Minimize to tray.
- Hiển thị số job chờ.
- Notification khi job thành công/thất bại.
- Menu Open, Pause Scheduler, Resume Scheduler, Exit.
- Khi Exit còn job chờ, cảnh báo app phải chạy để job thực thi.
- `Start with Windows` mặc định tắt.

## 14. Concurrency và UI responsiveness

- Không chạy API call trên UI thread.
- UI không freeze khi dịch/upload/publish.
- Có cancellation khi khả thi.
- Mặc định tối đa 3 OpenAI translations, 2 publications và 2 comments đồng thời.
- Cập nhật progress về UI thread an toàn.

## 15. Logging và dữ liệu ứng dụng

Sử dụng rotating log, correlation ID cho campaign/publication/job và trang Logs đơn giản. Background exception không được làm crash toàn app.

Dữ liệu runtime ở:

```text
%LOCALAPPDATA%\FacebookContentPublisher\
├── data\app.db
├── logs\
├── cache\
├── media\
└── backups\
```

Hỗ trợ backup SQLite thủ công và backup trước migration. Restore cần xác nhận. Secret không nằm trong backup.

## 16. Kiểm thử

### 16.1 Unit tests

- Prompt construction và structured output validation.
- Country validation.
- Timezone và comment delay.
- Retry classification.
- State transitions.
- Idempotency.
- Log redaction.
- Secret storage interface.
- Scheduler recovery.

### 16.2 Integration tests

- SQLite repositories và migrations.
- Mock OpenAI/Facebook.
- Publish → lưu Post ID → schedule comment.
- Restart và phục hồi job.
- Temporary error → retry → success.
- Permanent error → failed, không retry vô hạn.

Test mặc định không gọi OpenAI/Facebook thật, không cần API key và không cần Internet. Live tests phải được đánh dấu riêng và chỉ chạy khi người dùng chủ động bật.

## 17. Coding standards

- Type hints cho public functions.
- Docstrings cho interface và logic phức tạp.
- Không dùng global mutable state không cần thiết.
- Không swallow exception.
- Không hard-code token, Page ID, API version hoặc user path.
- Không dùng `time.sleep` trên UI thread.
- Không đặt SQL/HTTP trực tiếp trong UI.
- Dependency injection đơn giản, không over-engineer microservices.

## 18. Packaging

Dùng PyInstaller `onedir` trước; chỉ cân nhắc `onefile` sau khi ổn định.

```text
dist/
└── FacebookContentPublisher/
    └── FacebookContentPublisher.exe
```

Tạo:

- `scripts/setup.ps1`
- `scripts/run.ps1`
- `scripts/test.ps1`
- `scripts/build.ps1`

Build script phải lint, test, build, kiểm tra executable và không đóng gói `.env`, development DB hoặc secret.

## 19. README

README phải hướng dẫn môi trường, virtualenv, dependencies, migration, chạy app/mock mode, OpenAI setup, Meta setup, tests, build `.exe`, vị trí DB/log, backup, token expiry và giới hạn của app local.

## 20. Tiêu chí nghiệm thu MVP

MVP hoàn thành khi:

1. Chạy trên Windows/Python 3.12.
2. CRUD CountryProfile hoạt động.
3. Tạo campaign và chọn nhiều quốc gia.
4. Dịch qua mock và OpenAI thật khi có key.
5. Review/edit/approve hoạt động.
6. Mock Facebook tạo Post ID.
7. Publication và CommentJob lưu SQLite.
8. Comment delay tính từ lúc đăng thành công.
9. Restart không mất job.
10. Temporary error retry; permanent error không lặp vô hạn.
11. Không lộ key/token trong log/database.
12. Tests mặc định chạy offline.
13. Build được `.exe` bằng script.
14. UI không freeze khi gọi API.
15. Mock mode không thể bị nhầm là đăng thật.

Facebook production hoàn thành khi có thể kết nối Page hợp lệ, kiểm tra quyền, đăng text/photo (và video nếu hỗ trợ), lưu Post ID, tạo comment, xử lý token/permission rõ ràng và không lộ token.

## 21. Tuân thủ

Ứng dụng chỉ quản lý Page mà người dùng có quyền. Không tạo spam, né API/platform enforcement, tạo tài khoản, thu thập dữ liệu trái phép, che giấu link gây hiểu nhầm hoặc tạo claim quảng cáo sai.

Operator chịu trách nhiệm về chính sách Meta, điều kiện affiliate, disclosure, bản quyền nội dung/media và pháp luật quảng cáo tại từng quốc gia.

## 22. Dữ liệu mẫu development

```text
Thailand: TH, th-TH, Asia/Bangkok
Indonesia: ID, id-ID, Asia/Jakarta
Brazil: BR, pt-BR, America/Sao_Paulo
```

Page ID/link dùng mock value; không hard-code credentials.

## 23. Milestones cho Codex

### Milestone 1 — Bootstrap

- Git, `pyproject.toml`, src layout.
- Main window tối thiểu.
- Scripts setup/run/test.
- Mock mode mặc định.
- Chạy lint/test/smoke test.

### Milestone 2 — Domain và database

- Models, enums, SQLite/Alembic, repositories và tests.

### Milestone 3 — Country và Campaign UI

- Country CRUD, campaign form/list, media selection và validation.

### Milestone 4 — Translation

- Interface, mock/OpenAI implementation, structured output, review UI, secret storage và tests.

### Milestone 5 — Scheduler

- Publication/CommentJob, persistent worker, retry, recovery, tray và tests.

### Milestone 6 — Facebook mock

- Mock Page/publish/comment/error simulation và end-to-end mock flow.

### Milestone 7 — Facebook production

- Graph client, OAuth/token strategy, Page discovery, text/photo/video, comment và error handling. Live test chỉ khi người dùng xác nhận.

### Milestone 8 — Packaging

- PyInstaller, build script, packaged smoke test, README và acceptance checklist.

Sau mỗi milestone, Codex phải chạy formatter/linter/tests/smoke test phù hợp, sửa lỗi, cập nhật README và báo file thay đổi cùng phần còn lại.

## 24. Quy tắc dành cho Codex

- Đọc toàn bộ file này trước khi code.
- Mặc định mock mode; chưa yêu cầu credentials khi bootstrap.
- Không hard-code hoặc log secret.
- Không xóa file/thay đổi hệ thống ngoài project khi chưa được phép.
- Không tự đăng Facebook production nếu chưa có xác nhận.
- Không bỏ test để tuyên bố hoàn thành.
- Nếu Meta bị chặn bởi quyền/App Review, hoàn thành mock/interface/docs và báo blocker rõ ràng.
- Ưu tiên vertical slice chạy được trước khi mở rộng UI.
- Giữ repository luôn ở trạng thái có thể chạy/test sau mỗi milestone.

## 25. Prompt bắt đầu đề xuất

```text
Đọc toàn bộ PROJECT_REQUIREMENTS.md trước khi làm việc.

Hãy thực hiện Milestone 1: Bootstrap. Tạo một ứng dụng desktop Windows
bằng Python 3.12 và PySide6 theo đúng yêu cầu.

Yêu cầu:
- Chỉ làm Milestone 1 trong lượt này.
- Dùng src layout.
- Mặc định chạy mock mode.
- Chưa yêu cầu bất kỳ API key hoặc Facebook token nào.
- Tạo scripts PowerShell cho setup, run và test.
- Chạy kiểm tra thực tế sau khi tạo.
- Sửa mọi lỗi phát hiện được.
- Cuối cùng báo các file đã tạo, lệnh chạy app và kết quả kiểm tra.
```
