# Kế hoạch thực thi của Lead — Bee Bot MVP v1

- **Ngày lập:** 10/10/2026.
- **Trạng thái:** bản thử cục bộ đã được ba Peer triển khai và Lead tích hợp vào Hermes/Paseo; đã kiểm chứng hội thoại nghiệp vụ trên dữ liệu giả. Chưa mở pilot thật.
- **Owner chung:** Lead dự án Bee Bot. Các owner bên dưới là vai trò cần được Lead gắn với người cụ thể trong team.

Các quyết định được xác nhận và cách phân công Peer agent được cụ thể hóa trong [Các quyết định để bắt đầu thực hiện](DECISIONS_TO_START_V1.md). [Hợp đồng triển khai](IMPLEMENTATION_CONTRACT_V1.md) thống nhất giao diện giữa các Peer. Bản thử được phép bắt đầu; pilot thật là mốc nghiệm thu sau.

Đầu ra đợt xây đầu tiên: chat thử **qua Paseo với Hermes thật đã cài trên máy** và công cụ nghiệp vụ Bee Bot, dùng lịch/outbox cục bộ. Lead đã kiểm chứng các phiên riêng An/Bình/Dũng/vận hành, đọc danh tính, nhận thay, nghỉ, hoán đổi, issue và tra cứu. [Báo cáo kỹ thuật](ACCEPTANCE_REPORT_V1.md) phân biệt bằng chứng này với phần Zalo/Sheets thật chưa nghiệm thu.

## 1. Tiến độ và ranh giới quyết định

MVP đã chốt phạm vi nghiệp vụ: chat riêng trên Zalo cho labcoach và vận hành; nhận thay một ca, hoán đổi hai ca, nghỉ chưa có người thay, báo issue và tra cứu trạng thái. Google Sheets là lịch chính thức; D là người được phân công, J là thông tin xếp ca do vận hành cập nhật, B–J là nguồn chuẩn; ca sáng 09:00–13:00, chiều 14:00–18:00. Bot giữ nguyên J khi đổi D. Vận hành xác thực liên kết Zalo với mã labcoach; người nhận xác nhận trực tiếp và tự xác nhận không bận ngoài chương trình, bot kiểm tra lịch chương trình. Với nghỉ chưa có người thay, vận hành chấp nhận trước khi bot mời đồng thời người hợp lệ; người đủ điều kiện sớm nhất nhận vị trí. Lời mời hết hạn sau tối đa 24 giờ và không muộn hơn lúc ca bắt đầu.

Đã chọn **Hermes Agent** làm nền tảng agent; dịch vụ nghiệp vụ SQLite/MCP, JSON schedule và công cụ Hermes đã chạy cục bộ. **Bot BeeCoach** đã được tạo, token lưu riêng, tài khoản chủ bot liên kết thử với An. Tin thật “Xem lịch của tôi” đã nhận qua polling, xử lý bằng Hermes/công cụ và API xác nhận gửi phản hồi đúng lịch giả. Nghiệp vụ đổi lịch, gửi lời mời chủ động, hạn mức và webhook thật vẫn cần kiểm chứng. Bản đọc Sheets đã chuẩn hóa 390 vị trí từ một tab/kỳ lịch, chưa chứng minh bao phủ toàn bộ chương trình. Người phụ trách nghiệm thu là chủ dự án; phát triển bot/tích hợp là trách nhiệm Lead và Peer. Worker lần thử Zalo đang chạy local với lịch giả riêng `.bee-bot/zalo-demo` theo [hướng dẫn](ZALO_ONBOARDING.md).

## 2. Phân công và thứ tự thực hiện

| Thứ tự | Owner / việc giao | Đầu ra cần bàn giao | Tiêu chí hoàn tất |
| --- | --- | --- | --- |
| **1 — ngay, không cần tài khoản/secret** | **Lead** chủ trì buổi rà soát với **nghiệp vụ/ops**; ghi quyết định còn mở và người chịu trách nhiệm | Một bảng quyết định có trạng thái, người chốt, ngày chốt; phiên bản đặc tả luồng được ops duyệt hoặc ghi rõ ngoại lệ chưa duyệt | Luồng nhận thay, hoán đổi, nghỉ, issue và hủy có người quyết định; các tình huống trong [kịch bản nghiệm thu](WORKFLOW_SPEC_V1_DRAFT.md#8-kịch-bản-nghiệm-thu-nghiệp-vụ-đề-xuất) có kết quả mong đợi thống nhất |
| **1 — song song** | **Dữ liệu Sheets** cùng **ops** lập mẫu dữ liệu phi cá nhân từ bản xuất đã đọc: mã người, mã ca/vị trí, phạm vi workbook/tab/kỳ lịch, quyền sửa D/J và tab theo dõi | Bảng ánh xạ cột và mã ổn định, danh mục nguồn lịch cần đọc, quy tắc cập nhật D giữ J, quy trình vận hành khi có sửa đồng thời | Đối chiếu được ca có nhiều labcoach, ô gộp, tên trùng và dòng di chuyển; xác nhận đủ nguồn để kiểm tra trùng lịch; không ghi lên Sheets nguồn |
| **1 — song song** | **QA** chuyển kịch bản nghiệp vụ hiện có thành ma trận nghiệm thu trên dữ liệu giả | Ca kiểm thử, dữ liệu đầu vào, trạng thái Sheets trước/sau và thông báo mong đợi cho từng luồng/ngoại lệ | Bao gồm hai người nhận gần nhau, phản hồi thiếu xác nhận, hết hạn, ghi hai ô thất bại một phần, sự kiện lặp, quyền tra cứu và J được giữ nguyên |
| **2 — sau khi ops duyệt luồng và ánh xạ dữ liệu** | **Lead + tích hợp Zalo/Hermes** chốt giao diện giữa adapter, Hermes và dịch vụ nghiệp vụ; làm thí nghiệm cô lập khi có môi trường dev | Sơ đồ luồng danh tính đến công cụ, hợp đồng công cụ, ghi nhận phiên bản Hermes; biên bản kiểm chứng Bot Platform và phương án trả lời chữ/nút | Công cụ không tin vai trò do model tự điền; xác minh được cách nhận/gửi tin, ID người gửi và nhắn chủ động trên bot thử; nếu chưa có bot, ghi rõ phép thử còn chờ |
| **3 — chỉ sau các điều kiện pilot ở mục 3** | **Tích hợp Zalo/Hermes + dữ liệu Sheets**, **QA** nghiệm thu; **ops** vận hành thử; **Lead** quyết định mở từng mức | Bản thử với dữ liệu giả/bản sao Sheets, nhật ký thử, quy trình xử lý lỗi và báo cáo pilot | Đi từ đọc/ghi nhận sang tự ghi D theo cổng nghiệm thu; đọc lại Sheets trước khi báo hoàn tất; không báo thành công khi kết quả ghi chưa rõ; các ca QA quan trọng đạt và ops ký nhận |

Lead theo dõi phụ thuộc và chốt một nguồn quyết định. Ops quyết định quy trình chấp nhận nghỉ, hủy, xử lý issue và người nhận thông báo; đội tích hợp không tự suy diễn các quyền này. Kênh tiếp nhận đã chốt: từ pilot, yêu cầu thông thường qua bot; vận hành hỗ trợ khi bot lỗi hoặc có việc khẩn. QA tham gia từ bước 1 để phản biện điều kiện nghiệm thu trước khi xây.

## 3. Điều kiện cần từ người phụ trách để mở pilot

1. Chỉ định người làm Lead/ops, người quản lý Sheets và người chịu trách nhiệm bot; duyệt đặc tả nghiệp vụ và tiêu chí pilot. Chuẩn bị thông báo chuyển sang bot, đối chiếu yêu cầu đang mở từ Google Form/tin riêng và hướng dẫn hỗ trợ khi bot lỗi hoặc có việc khẩn.
2. Cung cấp danh mục **đầy đủ** workbook/tab/kỳ lịch lý thuyết và lab, bản sao thử nghiệm, quyền API phù hợp; chốt mã labcoach, mã ca/vị trí ổn định và số vị trí cần bố trí. Quyền D đã chốt: vận hành và bot đều cập nhật trực tiếp; cần kiểm chứng kiểm tra trước ghi/xác minh sau ghi và cách xử lý sửa đồng thời giữa hai bước. Danh sách tên người và dữ liệu truy cập không đưa vào Git.
3. Vận hành lập và xác thực danh sách mã labcoach ↔ tài khoản Zalo, quyền vận hành, người nhận cảnh báo và quy trình thu hồi liên kết; chốt đệm di chuyển nếu cần, cách xử lý ca sát giờ và lịch tổng hợp.
4. Có bot Zalo thử tạo được với token và quyền nhận/gửi/nhắn chủ động đã kiểm chứng; xác nhận hạn mức thực tế. Có provider/model cho Hermes, máy chạy và HTTPS webhook khi thử tích hợp thật. Secret được cấu hình ngoài repo.
5. Chốt cách xử lý ghi Sheets đồng thời, phục hồi khi hoán đổi cập nhật một phần hoặc kết quả ghi không rõ; QA và ops chấp thuận kiểm thử trước khi bật tự ghi D.

## 4. Điểm lệch tài liệu đã đồng bộ

[MVP v1](MVP_V1.md), [WORKFLOW_SPEC](WORKFLOW_SPEC_V1_DRAFT.md) và [bản thiết kế Hermes](HERMES_DEPLOYMENT_V1_DRAFT.md) phân biệt: bản thử nghiệp vụ/Hermes đã hoạt động cục bộ; triển khai Zalo/Sheets thật tiếp tục cần kiểm chứng, tài khoản và nghiệm thu riêng. Quyền cùng sửa D và bước kiểm tra trước/sau đã chốt, không đặt lại thành yêu cầu bắt buộc đi qua dịch vụ ghi chung.
