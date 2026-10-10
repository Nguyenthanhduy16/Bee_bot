# Bee Bot — Trợ lý vận hành Labcoach

Dự án hỗ trợ team vận hành chương trình AI thực chiến 20K của VinGroup phối hợp với VinUni, tập trung vào thay đổi lịch labcoach và theo dõi sự cố phòng học.

**Trạng thái:** đã chốt phạm vi nghiệp vụ MVP v1; chưa triển khai phần mềm.

Tài liệu chính: [Phạm vi và quyết định MVP v1](docs/MVP_V1.md).

Bước tiếp theo đã được cụ thể hóa trong [Đặc tả luồng và dữ liệu MVP v1 — bản nháp](docs/WORKFLOW_SPEC_V1_DRAFT.md): hội thoại, trạng thái, cấu trúc dữ liệu Sheets, ngoại lệ và kịch bản nghiệm thu. Bản nháp cần rà soát; các đề xuất mới chưa phải quyết định đã chốt.

Đã ghi nhận phạm vi tự động nhận thay một ca và hoán đổi hai ca. [Đối chiếu Google Sheets — bản nháp](docs/SHEETS_MAPPING_V1_DRAFT.md) đã cập nhật theo xác nhận: D là phân công chính thức, J phục vụ xếp ca, B–J là nguồn chuẩn, ca sáng 09:00–13:00 và chiều 14:00–18:00. Quy tắc đọc/ghi, định danh và xử lý ngoại lệ tiếp tục được rà soát.

Đã chốt vận hành xác thực liên kết Zalo với mã labcoach trước khi dùng; bot kiểm tra lịch chương trình và người nhận tự xác nhận không có lịch bận khác trong ca nhận. Các luồng nhận thay/hoán đổi và kịch bản nghiệm thu đã được cập nhật theo hai quy tắc này.

Đã bổ sung tìm người nhận ca sau khi vận hành chấp nhận yêu cầu nghỉ: bot nhắn đồng thời các labcoach hợp lệ không trùng lịch, người xác nhận đầy đủ và đủ điều kiện sớm nhất được nhận, người sau không nhận cùng vị trí. Người do vận hành bố trí vẫn xác nhận trực tiếp với bot. Lời mời hết hạn sau 24 giờ, không muộn hơn lúc ca bắt đầu; bot giữ nguyên J khi đổi D để vận hành tự cập nhật.

Tài liệu này lưu các quyết định đã thống nhất, quy tắc xử lý và những câu hỏi còn cần làm rõ. Các phương án kỹ thuật đang cân nhắc được đánh dấu riêng, không coi là quyết định đã chốt.
# Bee_bot
