# MVP v1 — Trợ lý vận hành Labcoach

- **Dự án:** Bee Bot.
- **Ngày đóng gói:** 10/10/2026.
- **Trạng thái:** đã chốt phạm vi nghiệp vụ MVP v1.
- **Giai đoạn:** đã xây bản thử Python/SQLite/MCP, dùng Hermes thật qua Paseo và tra cứu lịch thử qua Bot BeeCoach trên Zalo; chưa mở pilot với Sheets thật.
- **Định hướng kỹ thuật bổ sung:** người phụ trách đã xác nhận các phần cần chốt và yêu cầu Lead điều phối Peer thực hiện. Xem [hướng dẫn bản chạy](HERMES_LOCAL_SETUP.md) và [báo cáo nghiệm thu](ACCEPTANCE_REPORT_V1.md); kiến trúc pilot thật tiếp tục được kiểm chứng theo [thiết kế Hermes](HERMES_DEPLOYMENT_V1_DRAFT.md).
- **Căn cứ:** các quyết định được thống nhất trong buổi brainstorming với người phụ trách dự án.
- **Cập nhật khi tiếp tục ngày 10/10/2026:** người phụ trách chốt MVP tự động hỗ trợ cả nhận thay một ca và hoán đổi hai ca. Chi tiết thực hiện đang được đặc tả trong [bản nháp luồng và dữ liệu](WORKFLOW_SPEC_V1_DRAFT.md).
- **Bổ sung về Sheets:** người phụ trách xác nhận D là phân công chính thức, J là thông tin bận/rảnh phục vụ xếp ca, vùng B–J là nguồn chuẩn; ca sáng 09:00–13:00 và ca chiều 14:00–18:00 áp dụng cho tất cả lớp có lịch.
- **Bổ sung về định danh và lịch bận:** vận hành xác thực liên kết Zalo với từng labcoach trước khi dùng; bot kiểm tra lịch chương trình và yêu cầu người nhận tự xác nhận không có lịch bận khác trong ca nhận.
- **Bổ sung mới về nghỉ và lời mời:** lời mời hết hạn sau 24 giờ, không muộn hơn lúc ca bắt đầu; hoán đổi dùng ca bắt đầu sớm hơn. Với nghỉ chưa có người thay, sau khi vận hành chấp nhận yêu cầu, bot có thể nhắn tìm người nhận ca, lấy xác nhận trực tiếp và cập nhật lịch. Bot giữ nguyên J khi đổi người ở D; vận hành tự cập nhật J. Quyết định tìm người sau chấp nhận thay thế giới hạn không tự tìm/mời của phiên bản trước.
- **Cách tìm người đã chốt:** nhắn đồng thời các labcoach hợp lệ không trùng lịch; người nhận đủ điều kiện sớm nhất được nhận, người trả lời sau không được nhận cùng vị trí.
- **Bổ sung người thay khi đang chờ duyệt nghỉ:** nếu người gửi tự tìm được người thay và bổ sung vào yêu cầu đang chờ vận hành chấp nhận, bot báo vận hành, giữ cùng mã và chuyển sang luồng nhận thay không cần duyệt nghỉ. Vẫn cần người thay xác nhận trực tiếp và đủ điều kiện trước cập nhật lịch.
- **Kênh tiếp nhận đã chốt:** khi mở pilot, chuyển yêu cầu thông thường sang bot Zalo làm đầu mối; ngừng dùng Google Form/tin riêng làm kênh tiếp nhận thường lệ. Vận hành hỗ trợ khi bot lỗi hoặc có việc khẩn.
- **Quyền cập nhật lịch đã chốt:** vận hành và bot đều được sửa D trực tiếp. Bot kiểm tra lại lịch trước khi ghi; phát hiện thay đổi ảnh hưởng yêu cầu thì dừng và đối chiếu, còn đủ điều kiện thì cập nhật D, giữ J và xác minh kết quả. Giới hạn sửa đồng thời giữa lúc kiểm tra và ghi cần được kiểm chứng trước pilot.

## 1. Bối cảnh và mục tiêu

Team vận hành chương trình AI thực chiến 20K của VinGroup phối hợp với VinUni đã xếp lịch ban đầu cho labcoach và lưu lịch chính thức trên Google Sheets.

Labcoach hỗ trợ lớp lý thuyết và trực tiếp hướng dẫn học viên thực hiện bài lab. Sau khi công bố lịch, labcoach có thể báo nghỉ hoặc đổi ca. Hiện các yêu cầu được gửi qua Google Form hoặc nhắn riêng cho người vận hành, dẫn đến thông tin phân tán, dễ bỏ sót và phải cập nhật lịch thủ công.

MVP tạo một đầu mối chat trên Zalo để ghi nhận, xử lý và theo dõi các thay đổi lịch, đồng thời tiếp nhận sự cố phòng học. Người gửi và vận hành cần biết yêu cầu đã được ghi nhận, đang chờ ai và đã xử lý xong hay chưa.

## 2. Các quyết định đã chốt

| Nội dung | Quyết định |
| --- | --- |
| Đối tượng sử dụng | Labcoach và team vận hành; chưa mở cho giảng viên hoặc học viên trong MVP |
| Quy mô ban đầu | Khoảng 30–40 người, tính cả labcoach và vận hành; về sau có thể tăng |
| Kênh tương tác | Người dùng nhắn riêng với bot trên Zalo |
| Chuyển đổi kênh tiếp nhận | Từ pilot, yêu cầu thông thường qua bot; Google Form/tin riêng không tiếp tục là kênh thường lệ. Vận hành hỗ trợ khi bot lỗi hoặc có việc khẩn |
| Nguồn lịch chính thức | Google Sheets hiện có |
| Người được phân công | Người ở cột D là phân công chính thức nếu chưa có thay đổi |
| Cột J của lịch | Thông tin bận/rảnh dùng để xếp ca |
| J khi bot đổi người ở D | Bot giữ nguyên J; vận hành tự cập nhật |
| Quyền cập nhật D | Cả vận hành và bot sửa trực tiếp; bot kiểm tra trước ghi và xác minh sau ghi, xử lý thay đổi ảnh hưởng yêu cầu |
| Vùng thông tin làm chuẩn | B–J của bảng chính; ưu tiên bảng chính khi khác vùng thông tin lặp K–P |
| Giờ ca | Sáng 09:00–13:00; chiều 14:00–18:00, áp dụng cho tất cả lớp có lịch |
| Định danh labcoach | Dùng danh sách mã labcoach và tài khoản Zalo được vận hành xác thực trước khi sử dụng |
| Lịch bận ngoài chương trình | Bot kiểm tra lịch chương trình; người nhận ca tự xác nhận không có lịch bận khác trong khoảng ca nhận |
| Nơi vận hành theo dõi và cập nhật công việc | Google Sheets, kèm thông báo qua Zalo |
| Đổi ca/nghỉ đã có người thay | Tự xử lý khi người thay xác nhận đồng ý và không trùng lịch |
| Hoán đổi hai ca | Tự xử lý hoán đổi hai ca; chi tiết xác nhận, kiểm tra lịch sau đổi và cập nhật hai phân công được đặc tả trước khi triển khai |
| Hạn lời mời | 24 giờ từ lời mời, tối đa đến lúc ca bắt đầu; hoán đổi dùng ca bắt đầu sớm hơn |
| Nghỉ chưa có người thay | Ghi nhận và chờ vận hành chấp nhận; sau chấp nhận, bot có thể nhắn tìm người nhận ca rồi cập nhật lịch khi đủ điều kiện |
| Người gửi bổ sung người thay khi đang chờ chấp nhận nghỉ | Báo vận hành, giữ mã và chuyển sang nhận thay không cần duyệt nghỉ; người thay vẫn xác nhận trực tiếp và được kiểm tra điều kiện |
| Cách bot tìm người nhận | Nhắn đồng thời các labcoach hợp lệ không trùng lịch; người nhận đủ điều kiện sớm nhất được nhận, phản hồi sau không nhận cùng vị trí |
| Người nhận do vận hành bố trí | Bot vẫn lấy xác nhận trực tiếp và kiểm tra điều kiện trước khi cập nhật lịch |
| Báo issue | Tiếp nhận và theo dõi sự cố phòng học, cơ sở vật chất |
| Theo dõi của người gửi | Tra cứu trạng thái yêu cầu nghỉ, đổi ca và issue của mình |
| Thông báo trạng thái | Bot chủ động thông báo khi trạng thái thay đổi, đồng thời hỗ trợ hỏi lại |
| Khả năng mở rộng | Có định hướng bổ sung các công việc vận hành khác sau MVP |

Ước lượng hiện tại: mỗi tuần khoảng 3–4 trường hợp đổi ca và 4–5 trường hợp xin nghỉ; issue phát sinh không thường xuyên. Đây là ước lượng để thiết kế pilot, chưa phải số liệu đo thực tế.

## 3. Luồng nghỉ/đổi ca đã có người thay

1. Người gửi báo ca cần thay đổi và người dự kiến nhận thay.
2. Bot xác định đúng ca trên lịch và hỏi thêm thông tin nếu còn thiếu hoặc có nhiều ca phù hợp.
3. Bot lấy xác nhận trực tiếp từ người thay. Lời khẳng định của người gửi rằng người thay đã đồng ý chưa đủ để hoàn tất yêu cầu.
4. Kiểm tra người thay không trùng lịch chương trình với ca cần nhận và lấy xác nhận của họ rằng không có lịch bận khác trong khoảng ca nhận.
5. Khi đủ điều kiện, cập nhật lịch chính thức trên Google Sheets.
6. Thông báo kết quả cho các bên liên quan và vận hành; người gửi có thể tra cứu lại trạng thái.

**Quy tắc đã chốt:** bất kỳ labcoach nào cũng có thể nhận thay, miễn không trùng lịch và đã đồng ý. MVP không yêu cầu phân loại năng lực theo nội dung lab để xét người thay. Các trường hợp đáp ứng điều kiện này không cần vận hành duyệt từng yêu cầu.

**Điều kiện hoàn tất:** Google Sheets đã cập nhật thành công. Khi người thay chưa xác nhận, còn xung đột lịch hoặc việc cập nhật thất bại, bot không được báo yêu cầu đã hoàn tất.

**Bổ sung đã chốt khi tiếp tục:** MVP hỗ trợ tự động cả nhận thay một ca và hoán đổi hai ca. Luồng hoán đổi hai ca được cụ thể hóa trong bản đặc tả nháp; không coi việc chốt phạm vi này là đã duyệt cách triển khai kỹ thuật.

## 4. Luồng báo nghỉ chưa có người thay

**Nhánh đã chốt:** trong lúc chờ vận hành chấp nhận, nếu người gửi bổ sung được người thay, bot báo vận hành và chuyển cùng yêu cầu sang luồng nhận thay ở mục 3, không cần chờ duyệt nghỉ. Chỉ khi người thay xác nhận trực tiếp và đủ điều kiện thì bot mới cập nhật lịch; việc bổ sung tên chưa đồng nghĩa đã bố trí xong. Các bước dưới đây áp dụng khi vẫn chưa có người thay.

1. Người gửi báo ca cần nghỉ.
2. Bot xác định đúng ca, ghi nhận yêu cầu và cấp mã theo dõi.
3. Bot thông báo cho vận hành rằng ca đang cần bố trí người thay.
4. Vận hành xem và chấp nhận yêu cầu nghỉ trước khi bot nhắn tìm người nhận ca.
5. Vận hành có thể cung cấp người dự kiến, hoặc bot nhắn đồng thời các labcoach hợp lệ không trùng lịch sau khi yêu cầu được chấp nhận.
6. Bot lấy xác nhận trực tiếp từ người nhận rằng đồng ý và không có lịch bận khác; kiểm tra không trùng lịch chương trình.
7. Đủ điều kiện thì bot cập nhật đúng phân công ở D, giữ nguyên J, kiểm tra kết quả và thông báo các bên.
8. Nếu chưa tìm được người hoặc chưa cập nhật lịch thành công, tiếp tục theo dõi và báo vận hành; người gửi có thể tra cứu.

**Quy tắc đã chốt:** tiếp nhận yêu cầu hoặc vận hành chấp nhận nghỉ chưa đồng nghĩa ca đã được bố trí đủ người. Bot chỉ nhắn tìm người sau khi vận hành chấp nhận; nhắn đồng thời những người hợp lệ không trùng lịch. Người nhận phải xác nhận trực tiếp và không có lịch bận khác; người đủ điều kiện nhận sớm nhất được nhận, người sau không nhận cùng vị trí. Cách ghi nhận thứ tự và giữ vị trí đang được cụ thể hóa trong đặc tả.

## 5. Luồng báo issue phòng học

Các ví dụ thuộc phạm vi MVP:

- Phòng H209 thiếu thiết bị giảng dạy.
- Wi-Fi yếu hoặc không đáp ứng việc học.
- Thiếu ổ điện để học viên cắm máy tính.
- Thiết bị phòng học bị hỏng.
- Điều hòa bị hỏng.

Luồng xử lý:

1. Labcoach hoặc thành viên vận hành gửi phản ánh qua chat riêng với bot.
2. Bot thu thập phòng, mô tả vấn đề, thời điểm phát hiện và ảnh nếu có.
3. Ghi nhận issue trên Google Sheets và cấp mã theo dõi.
4. Vận hành theo dõi, phân công người phụ trách và cập nhật trạng thái/kết quả xử lý trên Sheets.
5. Bot thông báo thay đổi trạng thái cho người gửi và cung cấp thông tin khi được hỏi.
6. Tổng hợp các issue còn tồn đọng để vận hành dễ theo dõi.

**Quy tắc đã chốt:** bot hỗ trợ tiếp nhận và theo dõi; team vận hành phụ trách giải quyết. Bot chỉ báo issue đã được giải quyết khi vận hành xác nhận kết quả.

## 6. Mã yêu cầu, trạng thái và tra cứu

Mọi yêu cầu nghỉ, đổi ca và issue đều có mã theo dõi riêng. Người gửi có thể xem tình trạng các yêu cầu của mình và nhận thông báo chủ động khi trạng thái thay đổi.

| Loại | Trạng thái chính đã thống nhất |
| --- | --- |
| Đổi ca/nghỉ có người thay | Chờ người thay xác nhận → Đang cập nhật lịch → Hoàn tất |
| Nghỉ chưa có người thay | Đã ghi nhận → Chờ vận hành chấp nhận → Tìm/chờ người nhận xác nhận → Đang cập nhật lịch → Đã bố trí và cập nhật lịch |
| Issue | Đã ghi nhận → Đang xử lý → Đã giải quyết |

Các trạng thái bổ sung đã được đưa vào phạm vi: **Cần bổ sung thông tin** và **Đã hủy**. Chi tiết điều kiện chuyển trạng thái, quyền hủy và cách xử lý ngoại lệ sẽ được đặc tả trước khi lập trình.

Ví dụ cách người dùng hỏi:

- “Yêu cầu đổi ca của tôi đến đâu rồi?”
- “Issue H209 tôi báo đã xử lý chưa?”
- “Các yêu cầu đang chờ của tôi.”

Bot cần làm rõ yêu cầu nào nếu một câu hỏi có thể ứng với nhiều bản ghi. Việc truy cập dữ liệu của người gửi giới hạn ở yêu cầu của chính họ; vận hành có phạm vi theo dõi chung.

## 7. Vai trò của Google Sheets và thông báo

- Google Sheets là lịch chính thức và nơi vận hành quản lý danh sách yêu cầu, issue, trạng thái, người phụ trách và kết quả xử lý.
- Bot cập nhật lịch cho các trường hợp có người thay đã đáp ứng điều kiện.
- Vận hành chấp nhận yêu cầu nghỉ chưa có người thay, có thể đề cử người nhận; bot tìm người sau chấp nhận, lấy xác nhận và cập nhật lịch. Vận hành xử lý ngoại lệ, tự cập nhật J và cập nhật tiến độ/kết quả issue.
- Bot dùng thông tin đã ghi nhận để trả lời trạng thái và gửi thông báo thay đổi.
- Vận hành nhận thông báo và bản tổng hợp việc còn tồn đọng.

Cấu trúc lịch hiện tại đã được đọc và ý nghĩa D/J, vùng B–J làm chuẩn, giờ ca đã được người phụ trách xác nhận; xem [đối chiếu Sheets](SHEETS_MAPPING_V1_DRAFT.md). Tên tab/cột theo dõi yêu cầu và issue bổ sung, người nhận thông báo và thời điểm gửi bản tổng hợp chưa được chốt.

Đã bổ sung [Ví dụ tin nhắn cho người gửi, vận hành và người nhận ca](MESSAGE_EXAMPLES_V1_DRAFT.md) để rà soát nội dung theo từng tình huống. Đây là mẫu đề xuất; chưa chốt nút bấm hoặc chấp nhận yêu cầu ngay trong chat.

## 8. Giới hạn phạm vi MVP

MVP tập trung vào thay đổi lịch đã công bố và sự cố phòng học. Các nội dung sau nằm ngoài phạm vi hiện tại:

- Xếp lịch ban đầu hoặc tự tối ưu toàn bộ lịch labcoach.
- Tìm hoặc mời người thay cho yêu cầu nghỉ chưa có người thay khi vận hành chưa chấp nhận yêu cầu.
- Xét năng lực chuyên môn để chọn người nhận ca.
- Mở bot cho học viên hoặc giảng viên.
- Xây trang quản lý riêng thay cho Google Sheets.
- Tự giải quyết sự cố cơ sở vật chất.
- Tự động hóa thêm các nghiệp vụ vận hành khác.

## 9. Định hướng kỹ thuật và phương án tích hợp

Đã chọn Hermes Agent làm nền tảng agent và hoàn thiện thiết kế/hướng dẫn trước. Phần này giữ các phương án tích hợp đã thảo luận; lựa chọn Hermes chưa đồng nghĩa đã chốt toàn bộ backend, kênh API Zalo hoặc cách triển khai dịch vụ. Xem [thiết kế Hermes](HERMES_DEPLOYMENT_V1_DRAFT.md).

### Kết nối Zalo

Hiện team chỉ có tài khoản Zalo cá nhân và nhóm Zalo. Việc đăng ký OA riêng cho chương trình được đánh giá là khó thực hiện.

**Zalo Bot Platform** là phương án được đề xuất ưu tiên cho pilot. Tài liệu cho phép tạo bot thông qua Zalo Bot Manager và kết nối chương trình xử lý bằng API. Đây là phương án khác với việc đăng ký OA riêng cho chương trình.

Theo trang dịch vụ đã kiểm tra trong buổi brainstorming ngày 10/10/2026, gói Basic công bố tối đa 50 người dùng mỗi bot và 3.000 tin nhắn gửi mỗi tháng; gói Pro còn ghi “sắp ra mắt”. Các hạn mức và khả năng đăng ký thực tế phải được kiểm tra lại trước khi triển khai. Chưa xác nhận tài khoản dự án có thể tạo và vận hành bot thành công.

Tự động hóa tài khoản cá nhân bằng `zca-js` cũng đã được thảo luận. Đây là thư viện không chính thức; tác giả cảnh báo tài khoản có thể bị khóa. Chưa lựa chọn phương án này.

### Backend và AI

Khả năng dùng nút được lưu tại [Nghiên cứu nút bấm trên Zalo](ZALO_BUTTON_RESEARCH.md). OA có tài liệu về nút; Bot Platform có công bố tính năng ở trang tổng quan nhưng API chi tiết/SDK chưa đủ để xác minh cách triển khai. Phương án phản hồi chữ hoặc trang xác nhận có nút vẫn đang mở, chưa chốt.

- Nền tảng chat cung cấp việc nhận/gửi tin; logic nghiệp vụ cần được xây hoặc cấu hình riêng.
- Đã thảo luận hai lựa chọn: tự xây backend hoặc dùng công cụ workflow của bên thứ ba. Nay đã chọn Hermes Agent; phần dịch vụ nghiệp vụ và kết nối với Hermes được đề xuất trong thiết kế, chưa triển khai.
- Đã đề xuất dùng AI để hiểu tin nhắn và tổng hợp, còn các quyết định sửa lịch dựa trên quy tắc và xác nhận cụ thể. Đã chọn Hermes Agent; nhà cung cấp AI và chi tiết kiến trúc/công nghệ triển khai chưa chốt.
- Đã đề xuất tách phần kết nối Zalo khỏi logic nghiệp vụ để thuận tiện mở rộng. Đây là định hướng kỹ thuật, chưa phải thiết kế đã duyệt.

Nguồn tham khảo:

- [Giới thiệu Zalo Bot Platform](https://bot.zapps.me/docs).
- [Hướng dẫn tạo bot](https://bot.zapps.me/docs/create-bot/).
- [API gửi tin nhắn](https://bot.zapps.me/docs/apis/sendMessage/).
- [Gói dịch vụ và hạn mức](https://bot.zapps.me/).
- [Tích hợp Zalo OA](https://oa.zalo.me/home/documents/guides/Khoi-tao-ung-dung-va-cap-quyen_117071366476220195).
- [Chính sách tin tư vấn của OA](https://oa.zalo.me/home/documents/guides/tin-tu-van) — áp dụng cho phương án OA, không mặc định áp dụng cho Zalo Bot Platform.
- [Thư viện zca-js và cảnh báo của tác giả](https://github.com/RFS-ADRENO/zca-js).

## 10. Những điểm còn cần đặc tả

Các điểm sau còn cần làm rõ trước khi triển khai; những phần đã được xác nhận khi tiếp tục không còn là câu hỏi mở:

1. Mã ca/phân công ổn định, định danh labcoach và phạm vi các bảng lịch khác. Cấu trúc bảng, ý nghĩa D/J, giờ ca, nguồn chuẩn B–J và bot giữ nguyên J khi thay người đã chốt.
2. Quy trình thực hiện xác thực liên kết Zalo, danh sách vận hành và chi tiết phân quyền. Nguyên tắc vận hành xác thực liên kết Zalo với từng labcoach trước khi dùng đã chốt.
3. Chi tiết xác nhận và cập nhật cho hoán đổi hai ca đã nằm trong phạm vi tự động; cách xử lý yêu cầu liên quan nhiều hơn hai ca.
4. Danh mục bảng/kỳ lịch chương trình cần tích hợp và khoảng đệm di chuyển nếu có. Nguyên tắc kiểm tra lịch chương trình kết hợp người nhận tự xác nhận không có lịch bận khác đã chốt.
5. Người nhận thông báo vận hành, lịch gửi bản tổng hợp và cách ưu tiên việc khẩn/sát giờ học.
6. Chi tiết ghi nhận thứ tự, giữ vị trí, xử lý từ chối/không phản hồi/hủy và lỗi cập nhật. Đã chốt mời đồng thời, người nhận đủ điều kiện sớm nhất được nhận, hạn lời mời 24 giờ tối đa đến lúc ca bắt đầu và xác nhận trực tiếp cho người do vận hành bố trí.
7. Đã chốt cả vận hành và bot cập nhật D trực tiếp, bot kiểm tra trước ghi và xác minh sau ghi. Còn kiểm chứng giới hạn sửa đồng thời giữa hai bước, cách phối hợp/đối chiếu và xử lý lỗi cập nhật/thông báo.
8. Cách liên kết các phản ánh trùng về cùng một sự cố; tiêu chí phân biệt các sự cố trong cùng phòng.
9. Đã chốt chuyển sang bot làm đầu mối từ pilot. Còn chuẩn bị thông báo chuyển kênh, đối chiếu yêu cầu đang mở từ kênh cũ và hướng dẫn hỗ trợ khi bot lỗi hoặc có việc khẩn.
10. Chi tiết tích hợp với Hermes Agent đã chọn, cách lưu dữ liệu, vận hành hệ thống và phương án mở rộng khi vượt hạn mức nền tảng.
11. Tiêu chí đánh giá pilot và cách đo số tin nhắn, yêu cầu bị bỏ sót, thời gian xử lý, mức độ sử dụng.

## 11. Bước tiếp theo

Người phụ trách nghiệm thu bản thử qua Paseo theo [hướng dẫn](HERMES_LOCAL_SETUP.md). Lead tiếp tục nối worker hội thoại/thông báo Zalo, hoàn thiện danh tính và nguồn lịch cho pilot, rồi nghiệm thu tích hợp thật. Bản thử đã có mã và bằng chứng kỹ thuật; chưa mở pilot hoặc ghi lịch nguồn.
