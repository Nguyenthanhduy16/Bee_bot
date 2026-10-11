# Adapter Zalo Bot — chuẩn bị tích hợp

`bee_bot.zalo` là thư viện transport/ingress đã kiểm thử offline; `bee_bot.zalo_webhook` cung cấp HTTP endpoint chạy được ở local, xác thực và lưu inbox bền trước khi trả acknowledgment. `bee_bot.zalo_worker` có worker polling nối Hermes thật bằng CLI. Token đã cấu hình riêng và tài khoản chủ bot liên kết với vai An: tin thật “Xem lịch của tôi” được xử lý và API xác nhận gửi phản hồi đúng hai ca thử. Chưa mở webhook công khai, nghiệm thu đổi lịch trên Zalo hoặc ghi Sheets thật. Bản thử dùng lịch JSON giả. Không gọi phần này là pilot Zalo đã hoàn tất.

## Đã có trong mã

- `ZaloBotClient(token, transport=None)` gọi `get_me`, `get_updates`, `get_webhook_info`, `set_webhook`, `delete_webhook`, `send_message` qua HTTPS. Token được truyền chủ động từ cấu hình ngoài Git; không tự đọc credential. Không log URL chứa token và không tự retry thao tác gửi timeout.
- `parse_update(payload)` chuẩn hóa tin nhắn văn bản riêng, hỗ trợ envelope `ok/result` trong tài liệu hoặc `result` đã bóc tách. Dùng sender/chat/message ID để tạo event ID ổn định, không dùng tên hiển thị.
- `ZaloIngress(db_path, identities=..., webhook_secret=...)` kiểm tra secret webhook bằng so sánh constant-time, ánh xạ Zalo sender ID qua danh sách quản trị viên cấu hình, lưu inbox SQLite chống lặp.
- `receive_webhook(payload, secret_header)` xác thực trước xử lý; `receive_polled(payload)` chỉ dùng với nguồn polling đã được transport xác thực. Tin nhóm, media, người chưa liên kết và event không hỗ trợ bị từ chối. Không tự cấp quyền theo câu “tôi là vận hành”.
- `process(event_id, handler)` giao event cho callback tin cậy một lần. Kết quả `completed` trong inbox nghĩa callback đã trả kết quả lưu được, không nghĩa lịch đã cập nhật hay tin đã giao. Callback lỗi hoặc worker chết sau claim cần đối chiếu, không tự chạy lại.
- `create_app(ingress)` tạo ứng dụng Starlette: `POST /zalo/webhook` và `GET /health`. Wrong secret/unknown user nhận 403, nhóm/event không hỗ trợ nhận 422, JSON không hợp lệ nhận 400, duplicate khác nội dung nhận 409. Ack 200 chỉ sau commit SQLite; webhook không chạy callback hội thoại trong request. Phản hồi không echo ID hoặc nội dung tin nhắn.

## Chạy endpoint local, chưa cần bot token

Cài môi trường `uv sync`. Dùng [mẫu biến môi trường](zalo.env.example) để chuẩn bị cấu hình riêng ngoài Git. Mẫu chỉ chứa tên biến; không chứa token hay secret thật. Tệp `BEE_BOT_ZALO_IDENTITIES` là JSON do quản trị viên quản lý, ví dụ `{"sender-an":"an"}` trong bài thử. File này liên kết sender ID với person ID; role lấy từ danh mục người được duyệt, không dùng role trong lời nhắn.

Khi đã export `ZALO_WEBHOOK_SECRET`, `BEE_BOT_ZALO_IDENTITIES`, `BEE_BOT_ZALO_INBOX`, chạy:

```bash
.venv/bin/uvicorn bee_bot.zalo_webhook:app_from_env --factory --host 127.0.0.1 --port 8765
```

`ZALO_BOT_TOKEN` không cần cho endpoint nhận. Gửi HTTP POST nội bộ tới `http://127.0.0.1:8765/zalo/webhook` bằng payload theo [tài liệu webhook](https://docs.zaloplatforms.com/docs/BOT/webhook) và header secret đúng. Đây là request thử từ local, chưa phải sự kiện từ Zalo thật. `GET /health` chỉ xác nhận tiến trình HTTP trả lời, không xác nhận DB, Hermes, token hoặc Zalo hoạt động.

Worker phải chạy riêng, đọc event đã lưu và gọi `ZaloIngress.process(event_id, handler)`. Event còn `pending` sau ack là trạng thái đúng ở bước nhận này. Worker polling bên dưới dành bài thử development; chưa có worker production riêng để chạy song song với webhook đã đăng ký. Không đặt callback nền tự chạy trong webhook để tránh ack trước khi lưu bền hoặc gọi nghiệp vụ lặp do webhook retry.

## Thử chat Zalo qua Hermes bằng polling

Sau khi tài khoản chủ bot [tạo bot](../docs/ZALO_ONBOARDING.md), cấu hình token ngoài Git cùng các biến trong mẫu env. Danh sách ánh xạ phải **mỗi person ID đúng một sender ID Zalo**. Worker tạo một profile `bee-zalo` từ lựa chọn model/provider của Hermes gốc cùng MCP Bee Bot và SOUL quản lý chứa hướng dẫn nghiệp vụ từ repo; không cần tạo các profile demo `bee-bot-*` để chạy Zalo. Không chép `.env`, `auth.json`, session hoặc memory; OAuth gốc sử dụng cơ chế Hermes đã có. Không mở profile `bee-zalo` trong Paseo cùng lúc worker đang xử lý tin.

`--env-file` đọc riêng tệp bạn chỉ định, chỉ lấy bốn biến `ZALO_BOT_TOKEN`, `ZALO_WEBHOOK_SECRET`, `BEE_BOT_ZALO_IDENTITIES`, `BEE_BOT_ZALO_INBOX`; không nội suy biến hoặc chạy lệnh trong tệp. Không tự đọc tệp env khi thiếu cờ này. Có thể dùng cách export môi trường thay thế. Tệp Zalo không thay `HOME`, `HERMES_HOME` hay cấu hình model/provider cá nhân.

Chạy một vòng hoặc chạy đến khi Ctrl-C:

```bash
.venv/bin/python -m bee_bot.zalo_worker --state-dir .bee-bot --env-file .bee-bot/zalo.env --once
.venv/bin/python -m bee_bot.zalo_worker --state-dir .bee-bot --env-file .bee-bot/zalo.env
```

Worker không chạy khi thiếu token/danh sách danh tính; kiểm tra danh mục người đang hoạt động và profile trước khi polling. Chỉ polling khi API xác nhận không có webhook, không xóa webhook tự động. MCP profile Zalo dùng đúng DB/JSON của `--state-dir`; nếu profile đã tồn tại với cấu hình khác thì dừng để đối chiếu, không âm thầm ghi đè. Một file lock chặn hai worker cùng thư mục trạng thái.

Kiểm tra bot mới ngày 10/10/2026 cho thấy `getWebhookInfo` trả HTTP 200 với `ok=false`, mã API `404`, mô tả `Not Found` khi chưa cấu hình webhook, thay vì result có URL trống. Client chuẩn hóa **đúng envelope này riêng cho getWebhookInfo** thành URL trống. HTTP status 404, lỗi token/quyền, mô tả khác, hoặc API khác vẫn là lỗi. Đây là hành vi đã quan sát trên bot thử; [trang getWebhookInfo](https://bot.zapps.me/docs/apis/getWebhookInfo/) chỉ minh họa trường hợp có cấu hình, không tài liệu hóa trạng thái bot mới đó.

Trên cùng bot thử, long poll `getUpdates` hết hạn khi không có tin trả HTTP 200, `ok=false`, mã API `408`, mô tả đúng `Request timeout`. Client chuẩn hóa riêng tổ hợp này thành `None` để worker tiếp tục chờ. Timeout kết nối HTTP, status HTTP 408, lỗi token/quota, mô tả khác và lỗi gửi tin không bị bỏ qua. [Bảng mã lỗi chính thức](https://bot.zapps.me/docs/error-code/) liệt kê 408 là timeout; ý nghĩa idle poll ở đây được kiểm chứng thêm bằng API thật.

Người dùng đã liên kết nhắn riêng bot. Worker lưu event, gọi `hermes -p bee-zalo chat --oneshot --source zalo --format stream-json` với stdin giữ nguyên nội dung, và `--resume` session bền của sender. Worker đặt `BEE_BOT_ACTOR_ID` từ ánh xạ sender đã xác thực và `BEE_BOT_EVENT_ID` từ event; profile MCP khai báo `${BEE_BOT_ACTOR_ID}` và `${BEE_BOT_EVENT_ID}` rõ ràng vì Hermes lọc môi trường subprocess. Lớp MCP sinh event ID ổn định từ event gốc, tên mutation và arguments để gọi lại cùng thao tác cùng event không tạo lần ghi mới. Danh tính thiếu hoặc không hợp lệ khiến MCP không khởi động; thiếu context event khiến mutation bị từ chối.

Payload tin nhắn Zalo có `message.from.display_name` theo [đặc tả webhook](https://docs.zaloplatforms.com/docs/BOT/webhook); worker chỉ dùng tên này để bot xưng “mình”, gọi người dùng là “bạn” hoặc tên hiển thị. Tên Zalo không cấp quyền, không chứng minh người đang chat là persona An/Bình/… trong lịch giả. Khi được hỏi danh tính, bot phải tách tên hiển thị Zalo khỏi vai thử hiện được liên kết. Nếu tên vắng mặt, dùng “bạn”.

Khi nâng từ worker profile riêng, bảng `zalo_sessions` cũ và các phiên Hermes cũ được giữ nguyên. Worker dùng bảng `zalo_shared_sessions` mới, mang sang sender/actor/chat đã ghi nhận nhưng không dùng lại session ID của profile cũ. Vì vậy tin đầu tiên sau nâng cấp bắt đầu một phiên Hermes mới; các tin tiếp theo của cùng sender tiếp tục phiên đó. Dừng worker cũ trước khi khởi chạy bản mới để tránh hai tiến trình đọc cùng bot.

Hermes Desktop trong bản cài hiện tại bỏ `source=oneshot` khỏi cây project, dù phiên vẫn tồn tại ở danh sách/API sessions. Worker gắn `--source zalo` cho phiên mới để hiển thị đúng nguồn Zalo và xuất hiện trong cây project của profile tương ứng. Phiên đã tạo trước sửa này vẫn giữ source cũ khi resume; chỉ thêm cờ không tự đổi metadata phiên cũ. Việc sửa một phiên cũ cần thao tác quản trị riêng sau sao lưu và dừng worker; không tạo lại hoặc phát lại tin người dùng chỉ để hiện lịch sử.

Worker gửi phản hồi và các notification của người đã liên kết/có chat xác minh. Người nhận thử nên nhắn bot trước để backend biết chat ID; chỉ có tên hoặc mapping sender ID chưa chứng minh bot gửi được tới họ. Không gửi tới tài khoản chưa liên kết. Đây là gửi bằng API Bot chính thức, không điều khiển session Zalo cá nhân.

Inbox `processing/uncertain` và delivery `sending/uncertain` không tự retry sau lỗi hoặc restart. Sender session được giữ qua các tin. Trạng thái `sent` nghĩa API xác nhận gửi, chưa chứng minh người nhận đọc. Notification dùng câu tiếng Việt, mã yêu cầu/sự cố và bước tiếp theo; lời mời có ca, phòng, giờ, hạn xác nhận và yêu cầu đủ hai xác nhận. Nội dung đọc qua service theo quyền người nhận; không gửi metadata JSON hay lý do nghỉ cho ứng viên. Chưa có dashboard đối chiếu delivery.

Trong bài thử, thứ tự nhận ca là thứ tự lời xác nhận đầy đủ **đến công cụ nghiệp vụ**, chưa chứng minh thứ tự thời gian tin nhắn Zalo trên toàn nền tảng. Cần nghiệm thu ordering/queue trước production. Chưa có timeout recovery tự động cho session đang xử lý hoặc outbox chưa rõ; vận hành cần đối chiếu trước quyết định chạy lại.

Kiểm thử worker không cần token/model thật:

```bash
.venv/bin/pytest -q tests/test_zalo_worker.py
```

Kiểm thử HTTP local không cần mở server công khai:

```bash
.venv/bin/pytest -q tests/test_zalo.py tests/test_zalo_webhook.py
```

## Phần cần nối trước pilot

1. Tạo bot qua Zalo Bot Manager → Zalo Bot Creator trong ứng dụng Zalo, nhận token. Phần này cần thao tác trong tài khoản chủ bot; mã nguồn không tự tạo danh tính bot.
2. Liên kết sender ID Zalo với labcoach/ops có thẩm quyền. Kiểm chứng qua danh sách được duyệt, không chỉ dựa vào tên hiển thị.
3. Nghiệm thu callback Hermes đã có trong worker polling: session theo sender, actor từ danh tính xác thực, event key ổn định theo từng mutation. Với webhook production cần worker hàng đợi riêng, chưa dùng worker polling để chạy khi có webhook.
4. Nghiệm thu worker gửi outbox bền đã có trong polling; bổ sung vận hành đối chiếu cho `sending/uncertain`. `send_message` timeout chưa chứng minh chưa gửi, không retry mù. Chưa có API idempotency/tra kết quả giao được chứng minh ở phần mã này.
5. Chọn polling phát triển hoặc webhook HTTPS công khai. API `getUpdates` không hoạt động khi đã thiết lập webhook. Không tự gọi `delete_webhook` khi khởi chạy polling vì thao tác đó thay cấu hình bot.
6. Nghiệm thu round trip bằng bot thử và người dùng cho phép, cùng cơ chế xung đột Sheets thật. Những kiểm thử offline không chứng minh token, quota, quyền chat, JSON thực tế của nền tảng hoặc webhook công khai hoạt động.

## Nguồn chính thức đã kiểm tra 10/10/2026

- [Tạo bot](https://docs.zaloplatforms.com/docs/BOT/create_bot): thao tác qua tài khoản Zalo và nhận token.
- [Xác thực](https://bot.zapps.me/docs/authorize/) và [gọi API](https://bot.zapps.me/docs/call-api/): endpoint HTTPS có token trong path, envelope phản hồi `ok/result`.
- [Webhook](https://docs.zaloplatforms.com/docs/BOT/webhook): header `X-Bot-Api-Secret-Token`, sender/chat ID và chat type.
- [getUpdates](https://bot.zapps.me/docs/apis/getUpdates/): long polling dành phát triển, timeout chuỗi, không có offset Telegram được tài liệu hóa.
- [sendMessage](https://bot.zapps.me/docs/apis/sendMessage/): chat ID, nội dung 1–2000 ký tự.
- [setWebhook](https://bot.zapps.me/docs/apis/setWebhook/): URL HTTPS công khai và secret 8–256 ký tự. Thành công đăng ký không tự chứng minh endpoint đã xác minh thành công.
