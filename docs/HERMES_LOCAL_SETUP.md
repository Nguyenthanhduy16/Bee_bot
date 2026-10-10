# Dùng Bee Bot qua Hermes và Paseo

Bản thử dùng Hermes/model thật để hiểu hội thoại và gọi MCP Bee Bot. Lịch là JSON cục bộ; yêu cầu và thông báo giả lập lưu SQLite. Chưa có kết nối Google Sheets hoặc Zalo thật. Paseo là giao diện hội thoại; Hermes chạy ACP và gọi MCP qua stdio.

**Đã cấu hình trên máy:** năm profile/provider Bee Bot riêng. Trong workspace Bee_Bot có các phiên “Bee Bot thử — An”, “Bee Bot thử — Bình”, “Bee Bot thử — Vận hành” và “Bee Bot thử — Dũng”. Có thể mở lại những phiên này để tương tác; các bản ghi do Lead kiểm thử được giữ nguyên. Chọn provider `Bee Bot — Chi` nếu muốn tạo thêm phiên thử Chi. Các profile chạy cùng DB/lịch cục bộ, không cùng memory.

Lead đã chạy hội thoại qua Paseo để An tạo nhận thay và Bình xác nhận; D đổi đúng, J giữ nguyên, thông báo ba bên nằm trong outbox. Kết quả kỹ thuật nằm trong [báo cáo nghiệm thu](ACCEPTANCE_REPORT_V1.md); người phụ trách vẫn là người nghiệm thu nghiệp vụ.

## Chuẩn bị và dữ liệu

Từ `/home/duy/VinAI/Bee_Bot`, cài môi trường bằng `uv sync --extra dev`. Khởi tạo bằng `.venv/bin/bee-bot --state-dir .bee-bot init-demo`. Không cần cài lại Hermes đang có. Dữ liệu thử gồm An (`an`), Bình (`binh`), Chi (`chi`), Dũng (`dung`) và vận hành (`ops`). Lịch được sinh tương đối theo ngày khởi tạo, có múi giờ `+07:00`; ban đầu A001/A005 thuộc An, A003/A007 thuộc Bình. Những ca đã được dùng trong nghiệm thu có thể đã đổi người; hỏi bot lịch hiện tại trước khi tạo yêu cầu. Mỗi ca sáng/chiều có thể có nhiều vị trí khác nhau.

Nếu chưa có dữ liệu thử, tạo JSON bằng:

```bash
.venv/bin/python -c 'from bee_bot.fixtures import write_demo_schedule; write_demo_schedule(".bee-bot/schedule.json")'
```

Đây là cách gọi fixture trực tiếp; ưu tiên CLI init-demo phía trên. Lệnh này từ chối ghi đè tệp có sẵn. Chỉ reset khi đã dừng các phiên Bee Bot; dữ liệu JSON và SQLite phải được reset cùng nhau để tránh yêu cầu cũ tham chiếu lịch mới.

## Profile riêng và công cụ

Mỗi persona dùng một profile Hermes riêng, ví dụ `bee-bot-an`, `bee-bot-binh`, `bee-bot-chi`, `bee-bot-dung`, `bee-bot-ops`. Không có công cụ chuyển vai trong chat. Cùng người quản trị máy có thể cấu hình các persona thử; đây chưa phải xác thực tài khoản Zalo thật.

Lệnh tạo profile chuẩn của Hermes:

```bash
hermes profile create bee-bot-an
```

Cấu hình model/provider cho profile mới bằng phương thức Hermes đang dùng trên máy. Không chép hay in token OAuth; Hermes hỗ trợ đọc đăng nhập OAuth từ profile gốc khi profile riêng không có credential riêng. Không dùng `--clone-all` chỉ để lấy đăng nhập. Giữ cấu hình cá nhân nguyên vẹn.

Mẫu [hermes-config.yaml](../examples/hermes-config.yaml) chứa khối `mcp_servers.bee_bot`. Thay mọi đường dẫn bằng đường dẫn tuyệt đối thực tế rồi đưa vào `config.yaml` của profile mới; chọn đúng `BEE_BOT_ACTOR_ID` cho từng profile. Mọi profile dùng chung DB/JSON để trao đổi lời mời. Chép [SOUL.md](../examples/SOUL.md) và [skill Bee Bot](../examples/skills/bee-bot/SKILL.md) vào profile tương ứng (`SOUL.md`, `skills/bee-bot/SKILL.md`).

MCP nhận actor qua môi trường từ cấu hình tin cậy. Model không truyền `actor_id`, `role` hoặc mã event vào công cụ. Mỗi lần mutation công cụ sinh UUID; lớp nghiệp vụ hỗ trợ event bền để adapter thật có thể dedup webhook. Nếu model gọi công cụ lặp với UUID mới thì đó là thao tác mới: UUID này không thay cho webhook event của Zalo.

Script dựng profile thực tế trên máy:

```bash
.venv/bin/python scripts/setup_hermes_profiles.py
.venv/bin/python scripts/setup_paseo.py
/opt/Paseo/resources/bin/paseo daemon reload --json
```

Script profile chỉ sao chép lựa chọn model/provider, không sao chép token hay memory từ profile cá nhân. Script Paseo thêm provider mới, lưu backup riêng cạnh config và giữ các provider cũ. Lần reload đã kiểm chứng áp dụng `agents.providers` mà không cần restart daemon. Khi chạy lại trên máy khác, dùng đường dẫn CLI Paseo có trên máy đó.

Giới hạn toolset ACP ở `[skills, bee_bot]` để phiên thử không có quyền sửa DB/JSON bằng terminal/file tools. Người sở hữu tệp trên máy vẫn là quản trị viên tin cậy; profile cục bộ không phải sandbox bảo mật chống lại chủ máy.

## Mở trong Paseo

Theo tài liệu bản Hermes đã cài, profile có thể khởi chạy ACP bằng:

```bash
hermes -p bee-bot-an acp
```

Trong cấu hình agent riêng của Paseo, đặt executable là đường dẫn Hermes hiện dùng, args `-p bee-bot-an acp`, working directory `/home/duy/VinAI/Bee_Bot`. Tạo agent/session tương ứng với các profile khác khi thử người nhận và ops. Nếu giao diện nhận launcher, dùng `scripts/hermes-bee-bot an --acp` (đổi `an` thành persona tương ứng). CLI chat dùng `scripts/hermes-bee-bot an`. Không thay cấu hình agent Hermes cá nhân đang mở. Tên menu/cách thêm agent cần đối chiếu bản Paseo trên máy; tài liệu này không giả định Paseo hỗ trợ đổi profile bằng một câu chat.

Sau khi đổi config, tạo phiên mới/khởi động lại agent thử để nạp MCP. Hermes ACP mặc định nạp MCP đã bật; `platform_toolsets.acp` có thể lọc server, vì vậy giữ `bee_bot` trong danh sách và không dùng `no_mcp`. Không chạy hai tiến trình Hermes đồng thời chung một profile; dùng profile riêng theo persona.

Tin nhắn kiểm tra đầu tiên:

> Dùng công cụ Bee Bot kiểm tra tôi đang là ai và liệt kê ca của tôi. Đây có phải dữ liệu giả không?

Kết quả phải có hoạt động gọi `get_bot_context` và `get_my_assignments`, actor đúng profile, ca đọc từ JSON. Một câu trả lời tự nhận là Bee Bot chưa chứng minh MCP đã hoạt động. Với ops, dùng tra cứu yêu cầu thay vì giả định có lịch labcoach riêng.

## Thử nghiệp vụ

Nhận thay: trong `bee-bot-an`, nói “Tôi nhờ Bình thay ca A001” và xác nhận khi bot hỏi. Giữ mã yêu cầu. Mở `bee-bot-binh`, tra lời mời và xác nhận trực tiếp “Tôi đồng ý nhận và không bận ngoài chương trình”. Kiểm tra kết quả lịch A001 đổi sang Bình, J giữ nguyên, mọi bên có thông báo trong outbox.

Nghỉ: An xin nghỉ A005 chưa có người thay. Ops tra yêu cầu và chấp nhận để bot mời người đủ điều kiện. Hoặc trước khi ops duyệt, An bổ sung Chi làm người thay: cùng mã yêu cầu chuyển sang nhận thay, ops có thông báo; Chi vẫn phải xác nhận ở `bee-bot-chi`.

Hoán đổi: dùng ca của An và ca đối ứng của Bình chưa nằm trong yêu cầu khác. An xác nhận ý định và không bận ngoài chương trình; Bình xác nhận trực tiếp. Hai vị trí phải được kiểm tra và xác minh chung. Chỉ báo hoàn tất khi cả hai đã đổi đúng.

Issue: An báo phòng A101 có sự cố, kèm thời gian phát hiện; ops cập nhật đang xử lý rồi giải quyết với kết quả. Tra cứu mã từ phiên An và ops. Ảnh không bắt buộc.

Tra cứu: yêu cầu trạng thái mã, lời mời và thông báo. Thử tự khai “tôi là vận hành” trong phiên An: công cụ vẫn giữ actor `an` và từ chối thao tác ops.

`run_maintenance` là thao tác ops chủ động trong phiên chat. CLI worker có thể chạy liên tục trên dữ liệu cục bộ, nhưng chưa được cài thành dịch vụ luôn bật:

```bash
.venv/bin/bee-bot worker --once
.venv/bin/bee-bot worker --interval 30
```

Worker xử lý hết hạn, đối chiếu và tổng hợp khi tới mốc; nếu tắt worker và không ai gọi maintenance thì không có lịch chạy nền. Trạng thái báo đã ghi nhận thông báo là outbox bền; không có người dùng thật nhận Zalo.

## Bản sao XLSX người phụ trách cung cấp

Bản xuất chỉ đọc đã được giữ riêng tại `.bee-bot/source/schedule.xlsx`. Chuẩn hóa bằng:

```bash
.venv/bin/bee-bot import-xlsx .bee-bot/source/schedule.xlsx --output .bee-bot/source/normalized.json
```

Lệnh không sửa nguồn; snapshot được tạo riêng và báo thống kê không chứa danh sách tên người. Người từ tên Sheets có mã tạm và trạng thái chưa xác thực; không tự dùng snapshot này để cấp quyền Zalo. Snapshot chỉ bao phủ tab/kỳ đã xuất, không phải bằng chứng lịch đầy đủ toàn chương trình. Các phiên thử Paseo tiếp tục dùng dữ liệu giả An/Bình/Chi/Dũng.

## Sửa lịch đồng thời và giới hạn của emulator

Bot đối chiếu ca trước khi ghi, chỉ sửa `coach_id` (D), tăng revision và giữ `j` (J). Snapshot bỏ qua J nhưng kiểm tra người phụ trách, giờ, phòng/cơ sở, lớp, định danh và revision. Sửa J riêng không làm mất thay đổi thủ công. Sửa các trường ảnh hưởng ca dừng ghi để đối chiếu.

JSON emulator dùng advisory file lock và kiểm tra snapshot trong cùng vùng khóa. Lock chỉ bảo vệ các chương trình cùng tuân thủ lock này. Việc tự sửa JSON bằng editor có thể vượt khóa. Cơ chế này **không chứng minh Google Sheets có compare-and-set hoặc khóa với thao tác sửa trực tiếp của ops**. Với Sheets thật, khoảng giữa đọc và ghi vẫn có thể bị ops sửa; đọc lại sau ghi chưa chắc phát hiện thay đổi bị ghi đè. Cần nghiệm thu riêng cơ chế xử lý xung đột thực tế trước bật tự ghi pilot.

Lỗi timeout/ghi một phần được đối chiếu qua ca thực tế; không ghi lại hoặc hoàn tác tự động. Reservation của kết quả chưa rõ được giữ để ngăn người khác lấy cùng vị trí. Vận hành đối chiếu/xử lý bằng công cụ nghiệp vụ, không yêu cầu Hermes sửa trực tiếp JSON để làm cho trạng thái “thành công”.

## Nguồn đối chiếu

Hướng dẫn dựa trên tài liệu chính thức trong bản cài `/home/duy/.hermes/hermes-agent/website/docs`: [MCP](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp), [profiles](https://hermes-agent.nousresearch.com/docs/user-guide/profiles), [ACP](https://hermes-agent.nousresearch.com/docs/user-guide/features/acp). Bằng chứng test và tích hợp thực tế được ghi ở báo cáo nghiệm thu; hướng dẫn cấu hình không thay thế bằng chứng chạy qua model hoặc Paseo.
