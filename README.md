# Bee Bot — Trợ lý vận hành Labcoach

Dự án hỗ trợ team vận hành chương trình AI thực chiến 20K của VinGroup phối hợp với VinUni, tập trung vào thay đổi lịch labcoach và theo dõi sự cố phòng học.

**Trạng thái:** đã xây bản thử cục bộ và nối công cụ Bee Bot vào Hermes thật qua Paseo. Chưa mở pilot Zalo hoặc ghi Google Sheets thật. Người phụ trách dự án là người nghiệm thu nghiệp vụ.

**Bản thử:** 18 công cụ MCP; dịch vụ nghiệp vụ Python/SQLite cho nhận thay, hoán đổi, nghỉ, issue và tra cứu; lịch JSON và outbox cục bộ. Đã thử nhận thay qua hai phiên Hermes/Paseo riêng và đối chiếu D/J sau ghi. Xem [hướng dẫn dùng ngay](docs/HERMES_LOCAL_SETUP.md) và [báo cáo nghiệm thu kỹ thuật](docs/ACCEPTANCE_REPORT_V1.md).

**Trong Paseo:** đã thêm các provider `Bee Bot — An`, `Bee Bot — Bình`, `Bee Bot — Chi`, `Bee Bot — Dũng`, `Bee Bot — Vận hành`, dùng profile Hermes riêng và danh tính giả cố định. Các phiên “Bee Bot thử — …” trong workspace là hội thoại nghiệm thu trên dữ liệu giả. Không tự khai đổi vai trong chat.

**Nguồn Sheets được cung cấp:** đã tải bản xuất XLSX chỉ đọc và chuẩn hóa riêng 390 vị trí (346 có người, 44 trống); bản sao chứa dữ liệu cá nhân được giữ trong `.bee-bot/source/`, ngoài Git. Tên người từ Sheets chưa thay cho liên kết Zalo đã xác thực và một tab chưa chứng minh bao phủ toàn lịch chương trình.

**Zalo:** đã có API client, xác thực danh tính/inbox, endpoint webhook lưu bền trước ack và worker polling nối Hermes/gửi thông báo. **Bot BeeCoach** đã nhận tin “Xem lịch của tôi” từ tài khoản chủ bot, gọi Hermes/công cụ Bee Bot và được API xác nhận gửi phản hồi đúng lịch thử. Người phụ trách dùng tài khoản Zalo cá nhân quản lý bot, không cần sở hữu OA riêng. Chưa nghiệm thu nghiệp vụ đổi lịch trên Zalo hoặc ghi Sheets thật. Xem [hướng dẫn kết nối](docs/ZALO_ONBOARDING.md) và [cách chạy adapter](examples/ZALO_ADAPTER.md).

Token được lưu trong tệp riêng `.bee-bot/zalo.env`; đã kiểm chứng hồ sơ bot và trạng thái chưa có webhook. Tài khoản chủ bot liên kết với vai An trên lịch giả mới tại `.bee-bot/zalo-demo`; worker local đang chạy, cần máy tiếp tục hoạt động và có mạng.

Chạy lại trên máy này:

```bash
uv sync --extra dev
.venv/bin/bee-bot init-demo
scripts/hermes-bee-bot an
.venv/bin/python -m pytest -q
```

`init-demo` giữ lịch đã có; dùng thư mục state mới nếu muốn kịch bản sạch. Các lệnh chat CLI không chạy đồng thời cùng profile đang mở trong Paseo. Để tạo lại cấu hình riêng: `.venv/bin/python scripts/setup_hermes_profiles.py`; thêm provider vào Paseo bằng `scripts/setup_paseo.py`, rồi reload config qua CLI Paseo. Hướng dẫn chi tiết ở tài liệu dùng Hermes.

Tài liệu chính: [Phạm vi và quyết định MVP v1](docs/MVP_V1.md).

Bản thử thực hiện các quyết định đã xác nhận trong [bảng quyết định](docs/DECISIONS_TO_START_V1.md). [Đặc tả luồng và dữ liệu](docs/WORKFLOW_SPEC_V1_DRAFT.md) lưu hội thoại, trạng thái, cấu trúc Sheets, ngoại lệ và kịch bản nghiệm thu; tên tab/cột pilot và chi tiết kỹ thuật chưa được kiểm chứng vẫn được ghi là đề xuất.

[Ví dụ tin nhắn MVP v1](docs/MESSAGE_EXAMPLES_V1_DRAFT.md) bổ sung các mẫu gửi người tạo yêu cầu, người vận hành và người nhận ca, gồm nghỉ, nhận thay, hoán đổi, issue, tra cứu và ngoại lệ.

[Nghiên cứu nút bấm trên Zalo](docs/ZALO_BUTTON_RESEARCH.md) đối chiếu Bot Platform, OA và phương án trang xác nhận có nút; phân biệt khả năng được tài liệu mô tả với phần chưa thử nghiệm thực tế.

Đã ghi nhận phạm vi tự động nhận thay một ca và hoán đổi hai ca. [Đối chiếu Google Sheets — bản nháp](docs/SHEETS_MAPPING_V1_DRAFT.md) đã cập nhật theo xác nhận: D là phân công chính thức, J phục vụ xếp ca, B–J là nguồn chuẩn, ca sáng 09:00–13:00 và chiều 14:00–18:00. Quy tắc đọc/ghi, định danh và xử lý ngoại lệ tiếp tục được rà soát.

Đã chốt vận hành xác thực liên kết Zalo với mã labcoach trước khi dùng; bot kiểm tra lịch chương trình và người nhận tự xác nhận không có lịch bận khác trong ca nhận. Các luồng nhận thay/hoán đổi và kịch bản nghiệm thu đã được cập nhật theo hai quy tắc này.

Đã bổ sung tìm người nhận ca sau khi vận hành chấp nhận yêu cầu nghỉ: bot nhắn đồng thời các labcoach hợp lệ không trùng lịch, người xác nhận đầy đủ và đủ điều kiện sớm nhất được nhận, người sau không nhận cùng vị trí. Người do vận hành bố trí vẫn xác nhận trực tiếp với bot. Lời mời hết hạn sau 24 giờ, không muộn hơn lúc ca bắt đầu; bot giữ nguyên J khi đổi D để vận hành tự cập nhật.

Đã chốt thêm: người gửi bổ sung người thay khi yêu cầu nghỉ đang chờ vận hành chấp nhận thì bot báo vận hành, giữ mã và chuyển sang luồng nhận thay không cần duyệt nghỉ; vẫn lấy xác nhận trực tiếp của người thay và kiểm tra đủ điều kiện trước cập nhật lịch.

Đã chốt chuyển sang bot Zalo làm đầu mối nhận yêu cầu thông thường từ khi mở pilot; ngừng dùng Google Form/tin riêng làm kênh tiếp nhận thường lệ. Vận hành hỗ trợ khi bot lỗi hoặc có việc khẩn.

Đã chốt vận hành và bot đều được sửa D trực tiếp. Bot đọc lại để kiểm tra trước ghi, dừng và đối chiếu nếu phát hiện thay đổi ảnh hưởng yêu cầu; đủ điều kiện thì cập nhật đúng D, giữ J và xác minh sau ghi. Giới hạn khi có sửa đồng thời giữa lúc đọc và ghi vẫn cần kiểm chứng trước pilot.

Tài liệu này lưu các quyết định đã thống nhất, quy tắc xử lý và những câu hỏi còn cần làm rõ. Các phương án kỹ thuật đang cân nhắc được đánh dấu riêng, không coi là quyết định đã chốt.
