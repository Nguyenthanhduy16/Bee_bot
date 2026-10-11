# Checklist vận hành worker và đầu vào pilot

Tài liệu chuẩn bị vận hành; chưa cài service bền hoặc mở pilot. Luồng hiện tại
là polling với Hermes thật, lịch JSON thử. Worker đã dừng lúc 14:48 ngày
11/10/2026. Ngày 12/10 worker được bật tạm cho lượt thử Zalo với bạn giả lập
Hermes, rồi dừng sau hai tin. Chưa có service chạy thường trực.

Backend đích là Google Sheets API Python phía sau SheetsScheduleAdapter.
Hermes chỉ gọi Bee Bot MCP; không cấp tool Sheets update/append tổng quát cho
model. ChatGPT Drive connector không nằm trong đường vận hành. Credential
Google (OAuth token có refresh hoặc service account thích hợp) được cấu hình
riêng cho dịch vụ; tái sử dụng setup/token Google Workspace của Hermes khi phù
hợp, với phạm vi Sheets cần thiết và không phụ thuộc phiên ChatGPT.

## Trước khi bật worker thử

- Xác nhận code candidate đã review/test và cấu hình profile `bee-zalo` trỏ
  đúng DB/lịch. Giữ riêng dữ liệu thử và dữ liệu pilot, backup SQLite bằng
  SQLite backup API, không copy riêng file DB đang có WAL.
- Kiểm tra token/provider theo cơ chế riêng ngoài Git. Không đặt token vào
  command line, unit file, log hay báo cáo. Danh tính Zalo do admin xác thực;
  display_name chỉ để trình bày.
- Chỉ một worker cho cùng state-dir; kiểm tra tiến trình/service và file lock.
  Polling cần webhook vắng. Không tự xóa webhook để khởi chạy polling.
- Kiểm tra pending/processing/uncertain inbox và sending/uncertain delivery
  chỉ đọc trước khởi động. Restart không chứng minh thao tác trước chưa ghi
  hoặc chưa gửi. Không đổi hàng loạt trạng thái thành pending để thử lại.

## Phân biệt profile, worker và tài khoản Zalo trong lượt thử

- Profile Hermes là cấu hình/session của agent, **không** phải một bot Zalo mới.
  `bee-zalo` cũ ghim vào state dir `.bee-bot/zalo-demo` và vai An; lượt thử
  Duy/Bình dùng profile `bee-zalo-duy-binh-test` với state dir JSON/SQLite
  riêng. Bình giả lập dùng `bee-bot-binh-duy-test` trên cùng state dir, không
  có tài khoản Zalo thứ hai. Không đổi đường dẫn DB/lịch của profile cũ để
  khớp bài thử mới: kiểm tra cấu hình sẽ từ chối drift ngoài migration được
  hỗ trợ, và các session/inbox cũ cần được giữ để đối chiếu.
- Profile tồn tại không có nghĩa là worker đang nghe Zalo. Lệnh `--once` nhận
  một lượt rồi thoát; nếu người thử nhắn khi worker dừng thì inbox cục bộ
  không tự có tin đó. Zalo `getUpdates` không có offset được tài liệu hóa;
  không giả định tin gửi lúc offline sẽ được phát lại. Bật worker thử **trước**
  khi người thử nhắn, đối chiếu `completed` và delivery `sent` trong inbox,
  rồi dừng có kiểm soát. Nếu cần trả lời liên tục, triển khai service bền và
  theo dõi ở mục dưới, thay vì dựa vào một lệnh `--once`.
- Xác nhận của Bình trong lượt 12/10 là hành động của persona giả lập qua
  Hermes/MCP trên lịch JSON. Kết quả đó không xác thực danh tính hay việc rảnh
  của một labcoach thật, và không mở quyền ghi Sheets.

## Service thường trực cần kiểm chứng

- Chọn máy/tài khoản vận hành, Python/Hermes và đường dẫn tuyệt đối. Dùng user
  service được quản lý bền với WorkingDirectory/PATH rõ, env riêng quyền 0600.
  Kiểm chứng enable/start sau reboot thay vì dựa vào transient systemd-run.
- Restart có backoff/rate limit cho lỗi tiến trình; phân biệt khởi động lại
  worker với replay event/gửi lại outbox. Lock ngăn hai worker cùng chạy.
- Theo dõi tuổi pending, số uncertain, lỗi OAuth/provider, lỗi MCP, lỗi nhãn
  session và giao nhận; báo đầu mối ops. Health HTTP hiện chỉ chứng minh endpoint
  trả lời, chưa chứng minh Hermes/DB/Zalo sẵn sàng.
- Quy trình OAuth hết hiệu lực phải khôi phục quyền theo tài khoản chủ máy,
  giữ secret riêng và thử lượt đọc mới; không dùng lỗi model để phát lại
  thao tác mutation cũ.
- Có worker bảo trì/scheduler cho hạn lời mời và tổng hợp 08:00/16:00; kiểm tra
  restart/dedup mốc. Polling chat hiện không thay thế scheduler nghiệp vụ.
- Nếu chọn webhook production: HTTPS/secret, lưu bền trước ACK, queue worker
  riêng, ordering và claim/dedup được nghiệm thu; không chạy polling đồng thời.

## Đối chiếu kết quả chưa rõ

1. Ops/Lead đối chiếu event với session/tool results, trạng thái yêu cầu,
   lịch thực tế và delivery record qua giao diện/DB chỉ đọc phù hợp.
2. Ghi rõ đã ghi, đã gửi, chưa rõ hoặc thất bại có bằng chứng; `sent` là API
   xác nhận thao tác gửi, không tự chứng minh người dùng đọc.
3. Với ghi lịch chưa rõ, dùng công cụ reconciliation để đọc/xác minh tất cả
   vị trí, giữ reservation khi partial. Không tự ghi lại hoặc hoàn nguyên.
4. Với gửi tin chưa rõ, xác nhận khả năng tra giao nhận/idempotency trước
   quyết định retry; không giả định timeout nghĩa chưa gửi.
5. Mỗi ngoại lệ có owner, evidence và quyết định cụ thể. Không sửa DB thủ công
   để làm trạng thái trông như thành công.

## Đầu vào/cổng pilot

- Tài khoản Zalo thử thứ hai, liên kết sender ↔ labcoach và chat nhận tin do
  ops xác thực. Thử riêng người gửi/người nhận và ops với quyền đúng.
- Workbook bản sao + danh mục đầy đủ nguồn lịch; người/mã ca/vị trí ổn định,
  quy tắc nhận diện khi dòng di chuyển và API access được cung cấp riêng.
- Workbook thử đã được chủ dự án xác nhận và cho phép ghi. Cấu hình riêng
  dùng owner_confirmed_copy=true, allowlist/pin workbook + tab/gid; source ID
  chưa biết được để trống, không bịa copy_of. Denylist nguồn đã biết luôn thắng
  allowlist. Không xin lại URL hoặc tính chất bản sao đã được xác nhận.
- Giữ các quy tắc nghiệp vụ đã chốt trong DECISIONS_TO_START_V1. Trước pilot
  kiểm chứng thực tế sửa D đồng thời và partial/timeout (API không có CAS),
  chốt đầu mối nhận cảnh báo, máy/service bền và danh mục lịch đầy đủ.
- QA nghiệm thu live hai sender, nghiệp vụ, quota/nhắn chủ động, lỗi/restart
  trên dữ liệu thử. Xác nhận giữ J và kiểm tra lại cả hai ô hoán đổi.
- Lead chấp nhận candidate kỹ thuật; chủ dự án quyết định phạm vi pilot và
  mức ghi thật. Cơ chế fake lock/CAS không chứng minh Sheets có khóa/CAS với ops.
