# Mốc profile Hermes chung cho Zalo — 11/10/2026

## Kết quả

Worker Zalo dùng một profile Hermes `bee-zalo`. Mỗi tin được ánh xạ từ sender ID đã xác thực sang person ID; worker truyền `BEE_BOT_ACTOR_ID` và `BEE_BOT_EVENT_ID` riêng cho lần chạy Hermes. MCP nhận actor từ môi trường tin cậy và tiếp tục kiểm tra quyền ở dịch vụ nghiệp vụ. Session được giữ riêng theo sender trong `zalo_shared_sessions`; một session ID không thể gắn cho hai sender.

Profile `bee-zalo` được tạo từ lựa chọn model/provider của Hermes gốc và cấu hình/skill trong repo. Không cần profile `bee-bot-*` để vận hành kênh Zalo và không sao chép token, auth, memory hay session từ profile thử. Bảng `zalo_sessions` và các phiên `bee-zalo-<actor>` cũ được giữ nguyên. Sender đã có chat bắt đầu session mới ở profile chung khi gửi tin sau chuyển đổi.

## Kiểm chứng

- 73 kiểm thử liên quan Zalo, onboarding, MCP và nội dung thông báo đạt; một kiểm thử MCP stdio được bỏ khỏi lần chạy này vì phiên subprocess treo trong sandbox hiện tại. `git diff --check` đạt.
- Một vòng worker `--once` trên bot thử kết thúc bình thường. Sau đó worker được bật bằng user systemd service tạm `bee-bot-zalo.service`; service ở trạng thái `active/running`, giữ khóa một worker và chưa restart tại lần kiểm tra.
- Một tin tra lịch mới từ tài khoản đã liên kết được inbox ghi `completed` với actor thử `an`; giao nhận ghi `sent`. Session nằm trong profile `bee-zalo`, nguồn `zalo`, có lời gọi `mcp__bee_bot__get_bot_context` và `mcp__bee_bot__get_my_assignments`. Chủ tài khoản xác nhận đã nhìn thấy câu trả lời trên Zalo.

Lượt thử thật này xác nhận một người dùng và luồng đọc lịch qua profile chung. Việc tách session của hai sender, chặn trùng session ID và giữ lịch sử profile cũ được kiểm thử bằng dữ liệu giả; chưa nghiệm thu hai người dùng thật hoặc các thao tác thay đổi lịch qua Zalo.

## Sửa cách xưng hô trong bản thử

Sau lượt thử, chủ bot phản ánh bot gọi họ là “An”, là tên vai dữ liệu giả đang liên kết với tài khoản. Worker đã được sửa để giữ `message.from.display_name` từ Zalo, đưa tên này vào `get_bot_context` chỉ để xưng hô, và hướng dẫn Hermes xưng “mình”, gọi người chat là “bạn” hoặc tên Zalo. Tên hiển thị không cấp quyền. Profile và session cũ được sao lưu riêng; session hiện tại của sender thử được làm mới để nạp hướng dẫn mới. 77 kiểm thử liên quan đạt; lượt nhắn thật sau sửa còn chờ chủ bot xác nhận cách bot xưng hô.

## Khôi phục công cụ danh tính

Sau sửa xưng hô, lượt Zalo đầu gọi MCP thành công nhưng model trả lỗi OAuth `token_revoked`; inbox ghi `uncertain` và chưa gửi phản hồi. Người dùng sau đó mở phiên trong Hermes Desktop: tiến trình này không có actor/event do worker truyền, MCP báo `INVALID_ACTOR`, nên tìm kiếm không thấy `get_bot_context`. Một tin Zalo tiếp theo cũng ghi `uncertain` vì Hermes đã tự bổ sung `_config_version`, `model.base_url` và `model.api_mode`, làm kiểm tra cấu hình bằng phép so sánh toàn bộ từ chối profile.

Worker nay chấp nhận metadata phiên bản hợp lệ và hai trường model tự bổ sung khi khớp model Hermes gốc. Cấu hình MCP, actor/event, đường dẫn dữ liệu và toolset vẫn phải khớp; migration tên hiển thị giữ các trường Hermes đã bổ sung. Profile không bị ghi lại khi chỉ có các bổ sung tương thích.

154 kiểm thử đạt, gồm MCP stdio và các trường hợp cấu hình bị thay đổi. Chạy Hermes thật với tin hỏi danh tính đã lưu, không gửi Zalo, đã gọi `get_bot_context` thành công và trả tên hiển thị Zalo; persona An được giải thích là vai thử trên lịch giả. Không phát lại inbox `uncertain` hoặc gửi lại tin cũ.

Worker được khởi động lại lúc 14:34 ngày 11/10/2026. Tin Zalo mới “Tôi là ai” được inbox ghi `completed`, giao nhận `sent`, và tạo session mới trong profile chung. Chủ tài khoản xác nhận nhìn thấy phản hồi trên cả Zalo và Hermes: bot dùng tên hiển thị Zalo và giải thích An là vai thử, không xác nhận danh tính thật. Service tiếp tục `active/running`, không restart ngoài lần áp dụng bản sửa.

Profile chung chỉ dùng danh tính khi worker cung cấp môi trường cho từng tin. Hermes Desktop có thể xem lịch sử; gửi tiếp từ Desktop không thay thế luồng xác thực Zalo. Không đặt actor cố định trong profile chung để chữa lỗi thiếu danh tính ở Desktop.

## Nhãn người nhắn trong Hermes

Worker bổ sung nhãn `Zalo · <tên hiển thị> — <tiêu đề hội thoại>` cho session mới và session đang tiếp tục. Metadata tên/peer được lưu riêng trong `origin_json.bee_bot_zalo`; tiêu đề đánh dấu nguồn `user` để bộ đặt tiêu đề tự động của Hermes không xóa nhãn. Đây là metadata trình bày: không thay đổi `user_id`, `session_key`, nguồn/định tuyến hoặc nội dung tin. Peer đã được gắn phải khớp sender/chat của worker; tên hiển thị trùng nhau không cho phép dùng chung session.

Tên mới cập nhật theo tin Zalo. Khi tin vắng tên, giữ tên đã nhận trên cùng peer; nếu chưa có tên, dùng nhãn người dùng ổn định từ sender ID. Tiêu đề dài được giới hạn 100 ký tự theo Hermes, các tiêu đề trùng được đánh số, và topic gốc giữ trong metadata. Lỗi DB/phiên bản không tương thích khi ghi nhãn chỉ ghi cảnh báo, không phát lại thao tác nghiệp vụ hoặc bỏ phản hồi.

163 kiểm thử đạt, bao gồm tạo/tiếp tục session, tên đổi/vắng, trùng tên, chặn nhầm peer, bảo toàn metadata/quyền và DB vắng. Ba session thật đã được gắn nhãn từ liên kết inbox/result đã xác thực, gồm phiên hiện tại và hai phiên cũ trong profile chung/cũ. DB được backup riêng tại `.bee-bot/zalo-demo/backups/session-labels-20261011-144345`. Các session không có liên kết người gửi xác định được giữ nguyên. Service tạm được tạo lại và chạy với bản sửa lúc 14:43 ngày 11/10/2026.

## Vận hành đợt thử

Kiểm tra: `systemctl --user status bee-bot-zalo.service`. Dừng: `systemctl --user stop bee-bot-zalo.service`. Đây là service tạm, không tự bật sau khi máy khởi động lại. Không chạy worker thứ hai trên cùng `.bee-bot/zalo-demo`.

## Checkpoint QA và trạng thái cuối đợt offline

Worker thử đã dừng lúc 14:48 ngày 11/10; những trạng thái running ở trên là bằng chứng lịch sử. Profile đang cài chưa được chuyển đổi sang bản sửa dưới đây. Không phát lại hai inbox uncertain đã được QA xác minh không có tác động nghiệp vụ/giao tin và đã được câu trả lời mới thay thế.

QA Codex độc lập xác nhận 151 kiểm thử đạt trên snapshot Zalo `94038c08…` cộng gate MCP `b4e602ac…`; Lead chấp nhận phạm vi sửa offline. Profile mới chỉ dùng `bee_bot`, tắt memory/user-profile, ghim config/SOUL và không tải skill chung. Lỗi xử lý lưu stage/code đã che dữ liệu; session chứng minh bị mất được làm mới trước khi chạy model. Mọi tool thay đổi state, gồm reconcile/maintenance, cần context event worker trên kênh Zalo. Profile cũ phải chuyển đổi tường minh với backup qua `--migrate-profile` trước khi chạy bản mới.

Mốc này chưa nghiệm thu Hermes/Zalo hai sender thật hay Sheets. Test stdio/toàn bộ suite còn chờ tích hợp Core/Google ổn định. [Báo cáo QA](QA_REVIEW_2026-10-11.md) giữ hash và giới hạn kiểm chứng.
