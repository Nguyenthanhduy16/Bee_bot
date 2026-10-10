# Bee Bot — Các quyết định để bắt đầu thực hiện

- Ngày: 10/10/2026.
- Trạng thái: **người phụ trách đã xác nhận các phần cần chốt và yêu cầu thực hiện**; Lead bắt đầu điều phối Peer xây bản thử cục bộ. Chưa mở pilot, kết nối hoặc ghi Sheets/Zalo thật.
- Phản hồi tổng thể phê duyệt Q1–Q3 theo các chỉnh sửa đã chốt riêng: bổ sung người thay bỏ chờ duyệt nghỉ; chuyển sang bot làm đầu mối. Các quy tắc còn lại áp dụng đúng bảng dưới; đệm di chuyển bản thử là 0 phút, quy tắc thực tế chốt trước pilot.
- Q4 đã chốt: vận hành và bot đều được cập nhật D trực tiếp; bot đọc lại trước ghi và xác minh sau ghi. Chi tiết xử lý sửa đồng thời còn cần kiểm chứng.
- Môi trường được làm rõ: người phụ trách đã cài Hermes và thử ra lệnh qua Paseo. Kiểm tra tại máy xác nhận Hermes và tiến trình ACP do Paseo khởi chạy trong thư mục Bee_Bot. Đề xuất dùng Paseo làm giao diện nghiệm thu bản thử đầu tiên.
- Căn cứ: [MVP v1](MVP_V1.md), [đặc tả luồng](WORKFLOW_SPEC_V1_DRAFT.md), [kế hoạch Lead](LEAD_PLAN.md).
- Mục đích: người phụ trách quyết định phạm vi và chính sách vận hành; Lead chịu trách nhiệm chi tiết kỹ thuật, giao việc Peer agent, tích hợp và kiểm tra đầu ra.

## 1. Quyết định đã xác nhận cho đợt xây đầu tiên

### Q1 — Bắt đầu xây bản thử với dữ liệu giả

**Đề xuất:** cho phép Lead điều phối Peer agent viết mã và kiểm thử tại repo này. Bản thử đầu tiên dùng **Hermes Agent thật đã cài trên máy**, được cấu hình để xử lý hội thoại tiếng Việt và gọi công cụ nghiệp vụ Bee Bot; dữ liệu lịch và kết nối Sheets/Zalo được giả lập. Bao phủ cả nhận thay một ca, hoán đổi hai ca, nghỉ chưa có người thay, issue và tra cứu. Giao diện bàn giao đề xuất là **Paseo → Hermes qua ACP → công cụ Bee Bot**, có các phiên/danh tính thử để kiểm tra từng vai, hướng dẫn chạy và bằng chứng kiểm thử. Cần kiểm chứng công cụ Bee Bot được nạp trong phiên Paseo và danh tính thử được truyền tới công cụ.

Chưa kết nối tài khoản Zalo/Sheets thật, triển khai máy chủ hoặc ghi Sheets thật trong đợt này. Tận dụng bản cài Hermes hiện có; khi thực hiện, kiểm chứng provider/model đang dùng có thể gọi công cụ Bee Bot. Phiên chat Hermes qua Paseo đã có chưa chứng minh nghiệp vụ Bee Bot đã tích hợp. Không dùng kết quả giả lập Hermes thay cho nghiệm thu này. Việc bật pilot thật là một mốc duyệt riêng sau khi có kết quả nghiệm thu và đủ đầu vào ở mục 2.

**Đã xác nhận:** bắt đầu bản thử trong phạm vi trên; Lead điều phối Peer agent.

### Q2 — Giao Lead quyết định kỹ thuật trong phạm vi đã duyệt

**Đề xuất:** giữ Hermes Agent theo quyết định hiện có; Lead chọn chi tiết triển khai dựa trên thiết kế đã có. Hướng khởi đầu là dịch vụ nghiệp vụ Python, SQLite cho một tiến trình ghi, công cụ MCP, adapter Zalo và worker. Hermes xử lý hội thoại; dịch vụ kiểm tra danh tính, quyền, xác nhận, lịch và điều kiện ghi. Chat chữ là giao diện ban đầu; nút bấm được xem xét sau kiểm chứng nền tảng.

Lead tự chọn cấu trúc repo, thư viện, phiên bản tương thích, hợp đồng dữ liệu và bộ kiểm thử; cập nhật quyết định kỹ thuật để người phụ trách xem. Khả năng tích hợp Hermes/Zalo phải được đối chiếu tài liệu chính thức và kiểm chứng khi thực hiện; phương án trên chưa phải bằng chứng nền tảng đã hoạt động. Lựa chọn provider/model và giới hạn chi phí cần có trước khi chạy hội thoại Hermes thật trong bản thử đầu tiên; tài khoản Zalo/Sheets thật được chuẩn bị cho pilot sau đó.

**Đã xác nhận:** Lead quyết định chi tiết kỹ thuật và triển khai trong phạm vi bản thử.

### Q3 — Các quy tắc nghiệp vụ đã duyệt

Các nguyên tắc đã chốt như D/J, giờ ca, xác nhận trực tiếp, hạn lời mời và mời đồng thời được giữ theo MVP. Bảng dưới được xác nhận trong phản hồi tổng thể, cùng các sửa đổi riêng đã ghi:

| Nội dung | Quy tắc đã xác nhận |
| --- | --- |
| Hủy yêu cầu đổi ca/nghỉ | Người gửi hủy yêu cầu của mình trước bước cập nhật; vận hành hủy yêu cầu đang mở và ghi lý do. Nếu đang ghi hoặc kết quả chưa rõ, đối chiếu trước khi quyết định. Sau hoàn tất, tạo yêu cầu mới, không dùng hủy để hoàn nguyên. |
| Yêu cầu trùng một vị trí | Một yêu cầu đang mở cho mỗi vị trí phân công. Hoán đổi giữ cả hai vị trí; phát hiện yêu cầu xung đột thì hướng dẫn bổ sung yêu cầu hiện có hoặc chuyển vận hành. |
| Nghỉ bổ sung người thay sau khi đã tạo | **Đã chốt:** khi đang chờ vận hành chấp nhận, giữ cùng mã, báo vận hành đã có người dự kiến nhận thay và chuyển sang luồng nhận thay, không cần duyệt nghỉ. Người thay phải xác nhận trực tiếp và đủ điều kiện trước cập nhật lịch. |
| Người xác nhận sớm nhất | Xếp theo thứ tự hệ thống tiếp nhận và lưu phản hồi đầy đủ, rồi kiểm tra điều kiện theo thứ tự đó; nếu cùng thời điểm, dùng thứ tự sự kiện đã lưu. Thiếu xác nhận không bận thì chưa giữ vị trí. |
| Rút chấp nhận nghỉ | Vận hành được rút trước khi bắt đầu ghi, có lý do; dừng lượt tìm và vô hiệu lời mời. Nếu đang ghi hoặc chưa rõ kết quả, đối chiếu trước; sau hoàn tất dùng yêu cầu mới. |
| Không có người nhận | Báo vận hành khi không có ứng viên, mọi lời mời hết hiệu lực hoặc ca bắt đầu; không tự phát lại lượt mời. Vận hành chủ động mở lượt mới khi còn đủ điều kiện. |
| Ca sát giờ | Báo vận hành khi còn không quá 2 giờ mà chưa bố trí xong; từ lúc bắt đầu ca chuyển xử lý thủ công, không tự đổi phân công lịch sử. |
| Đệm di chuyển | Bản thử dùng 0 phút; trước pilot, ops xác nhận có cần đệm giữa cơ sở và cung cấp quy tắc nếu có. Nếu còn thiếu quy tắc thực tế, chưa bật tự ghi D cho trường hợp liên quan. |
| Issue | Vận hành cập nhật trên Sheets; khi giải quyết phải có người xác nhận, thời điểm và mô tả kết quả. Không tự gộp; tái phát tạo issue mới liên kết issue cũ. Người gửi được hủy phản ánh báo nhầm trước khi xử lý; sau đó vận hành quyết định và ghi lý do. |
| Thông báo | Nhắn riêng các bên theo sự kiện; vận hành nhận lỗi và việc cần xử lý ngay. Đề xuất tổng hợp việc tồn đọng lúc 08:00 và 16:00 mỗi ngày, múi giờ Asia/Ho_Chi_Minh; danh sách người nhận cần được ops cung cấp trước pilot. |
| Kênh tiếp nhận | **Đã chốt:** từ khi mở pilot, yêu cầu thông thường gửi qua bot Zalo; ngừng dùng Google Form/tin riêng làm kênh tiếp nhận thường lệ. Vận hành hỗ trợ khi bot lỗi hoặc có việc khẩn. |

**Đã xác nhận tổng thể:** triển khai các quy tắc trên cho bản thử; phản hồi trước đây giải thích từng thuật ngữ được giữ nguyên ý nghĩa, không mở lại quyết định đã duyệt.

### Q4 — Cách vận hành sửa D khi bật tự động

**Đã chốt:** cả vận hành và bot đều được cập nhật D trực tiếp trên Sheets. Bot kiểm tra lại lịch ngay trước khi đổi, không bắt buộc vận hành sửa qua một dịch vụ chung và không mặc định chuyển mọi cập nhật của bot thành đề xuất để vận hành ghi hộ.

Quy trình thực hiện: bot đối chiếu đúng ca/vị trí, người hiện tại ở D, thông tin ca đã được xác nhận và lịch liên quan của người nhận. Nếu phát hiện thay đổi ảnh hưởng yêu cầu hoặc điều kiện nhận ca, dừng ghi theo bản cũ, báo vận hành/người liên quan và đối chiếu lại. Thay đổi J không làm bot ghi đè J. Nếu vẫn đủ điều kiện thì bot ghi đúng ô D cần đổi, giữ nguyên J, đọc lại và chỉ báo hoàn tất khi kết quả đúng; hoán đổi cần kiểm tra cả hai vị trí.

**Giới hạn kỹ thuật cần kiểm chứng:** bước đọc và ghi tách nhau, nên vận hành vẫn có thể sửa giữa hai bước. Đọc lại sau ghi có thể phát hiện kết quả không đúng, nhưng không bảo đảm phát hiện một thay đổi của vận hành đã bị bot ghi đè. Lead phải kiểm thử tình huống này, ghi rõ giới hạn và đề xuất cách phối hợp phù hợp trước pilot; không coi đọc trước/sau là cơ chế khóa. Khi có xung đột hoặc kết quả chưa rõ, dừng, đối chiếu và báo vận hành; không tự ghi lại hoặc hoàn nguyên theo bản cũ.

Quyết định này chốt quyền cùng cập nhật và quy tắc kiểm tra; chưa phải kết quả nghiệm thu kỹ thuật hoặc quyền ghi dữ liệu thật ngay lúc này.

## 2. Đầu vào cần chuẩn bị trước tích hợp/pilot thật

Có thể bắt đầu lập trình và kiểm thử nghiệp vụ với dữ liệu giả mà chưa có tài khoản Zalo/Sheets. Riêng nghiệm thu hội thoại Hermes thật ở mốc đầu cần provider/model và môi trường chạy. Người phụ trách chỉ cần chỉ định đầu mối và thời điểm dự kiến có thể cung cấp các đầu vào còn lại.

| Đầu vào | Ai cần cung cấp / nội dung |
| --- | --- |
| Đầu mối nghiệp vụ | Người ops được quyền chấp nhận nghỉ, quyết định ngoại lệ và ký nghiệm thu; người quản lý Sheets; người quản lý tài khoản bot. Một người có thể kiêm nhiều vai trò. |
| Nguồn lịch đầy đủ | Danh mục workbook/tab/kỳ lịch lý thuyết và lab, bản sao để thử, quyền API phù hợp và quy trình thêm kỳ mới. Ops xác nhận danh mục bao phủ đủ lịch chương trình. |
| Định danh và số vị trí | Danh sách mã labcoach, vai trò, trạng thái hoạt động; xác nhận cách gắn mã ca/vị trí ổn định, xử lý tên trùng/đổi tên/dòng di chuyển và số vị trí cần cho mỗi ca. Peer dữ liệu sẽ đề xuất mẫu để ops duyệt. |
| Người dùng Zalo | Liên kết tài khoản Zalo với mã labcoach được ops xác thực, danh sách vận hành/nhận cảnh báo và cách thu hồi liên kết. |
| Môi trường Hermes cho bản thử đầu | Đã có Hermes/Paseo và người phụ trách đã thử ra lệnh. Peer tích hợp tận dụng bản cài hiện có, ghi phiên bản, cấu hình profile Bee Bot riêng và kiểm chứng model/công cụ/danh tính thử; làm rõ giới hạn chi phí khi cần. |
| Môi trường pilot | Bot Zalo thử; máy chạy và phương án HTTPS. Peer tích hợp kiểm chứng quyền nhận/gửi/nhắn chủ động và hạn mức thực tế. |

Secret được cấu hình ngoài Git bằng cơ chế phù hợp khi tích hợp. Không cần gửi token hay khóa truy cập trong câu trả lời chốt.

## 3. Lead giao việc sau khi nhận quyết định

Lead ghi chính xác quyết định được duyệt, cập nhật đặc tả liên quan và chốt hợp đồng chung trước các thay đổi phụ thuộc nhau. Tối đa ba Peer agent chạy song song cùng Lead:

| Peer | Phạm vi bàn giao |
| --- | --- |
| Nghiệp vụ | Máy trạng thái, xác thực/phân quyền, yêu cầu/lời mời/issue, giữ vị trí, xử lý hết hạn và các công cụ nghiệp vụ. |
| Dữ liệu & tích hợp | Dữ liệu giả, định danh ca/vị trí, đọc lịch, giao diện ghi và đối chiếu; nối công cụ nghiệp vụ vào Hermes thật và nghiệm thu qua Paseo; giả lập Sheets/Zalo ở mốc đầu, tích hợp hai nền tảng thật khi đủ đầu vào. |
| QA | Ma trận nghiệm thu và kiểm thử độc lập trên dữ liệu giả; kiểm tra quyền, cạnh tranh nhận ca, sự kiện lặp, lỗi ghi/hoán đổi và phục hồi. |

Lead phụ trách kiến trúc, ranh giới file, review chéo, tích hợp, hướng dẫn chạy và báo cáo điểm đạt/chưa đạt. Peer không tự thay đổi quyết định nghiệp vụ hoặc bật ghi dữ liệu thật.

## 4. Điều kiện bàn giao và mở pilot

- Bản thử chạy cục bộ theo hướng dẫn; người phụ trách chat qua Paseo với Hermes thật đã nạp công cụ Bee Bot. Năm luồng MVP có kết quả mong đợi và ca kiểm thử tương ứng trên dữ liệu giả.
- Các vai labcoach/người nhận/vận hành thử dùng phiên có danh tính cấu hình rõ từ ngoài model; câu tự khai vai trò trong chat không tự cấp quyền. Phiên Paseo thử không thay cho kiểm chứng danh tính Zalo thật.
- Có bằng chứng hội thoại tiếng Việt đi qua Hermes/model thật, gọi đúng công cụ với danh tính thử được xác định từ phiên, và diễn đạt kết quả nghiệp vụ. Giả lập Hermes có thể dùng trong kiểm thử tự động nhưng không thay bằng chứng này.
- Kiểm tra các ca trọng yếu: không xác nhận thay người khác, không lộ dữ liệu qua mã đoán được, hai người nhận chỉ một vị trí, phản hồi quá hạn, sự kiện lặp, giữ J, sửa D đồng thời, hoán đổi một phần/timeout và phục hồi sau khởi động lại.
- Ghi rõ phần đã chạy trên giả lập và phần chưa kiểm chứng với nền tảng thật; test giả lập không thay cho nghiệm thu tích hợp.
- Trước pilot: đủ đầu vào mục 2, QA đạt các ca trọng yếu trên bản sao Sheets, ops duyệt luồng và người phụ trách duyệt mức mở pilot. Tự ghi D chỉ bật khi cơ chế ghi và phục hồi được nghiệm thu.

## 5. Đầu vào đang chờ cho pilot

Người phụ trách xác nhận tự nghiệm thu và cung cấp lại link Sheets; bản xuất chỉ đọc đã được tải/chuẩn hóa riêng để kiểm thử. Chủ tài khoản Zalo cá nhân đã tạo Bot BeeCoach; Lead cấu hình token riêng, liên kết tài khoản thử với vai An và kiểm chứng tin tra cứu lịch thật qua Zalo/Hermes. Xem [hướng dẫn kết nối](ZALO_ONBOARDING.md). Phạm vi nguồn lịch và liên kết labcoach/vận hành thật tiếp tục được kiểm chứng trước pilot.
