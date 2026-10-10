# Bee Bot — Nghiên cứu khả năng dùng nút bấm trên Zalo

- **Ngày kiểm tra:** 10/10/2026.
- **Mục tiêu:** xác định có thể gửi lời mời kèm nút Nhận ca/Từ chối và thông báo vận hành kèm nút Chấp nhận ngay trong chat hay không.
- **Trạng thái:** kết quả nghiên cứu tài liệu và SDK; chưa chọn phương án, chưa tạo bot/OA, chưa thử trên tài khoản thực tế.
- **Liên quan:** [Đặc tả nghiệp vụ](WORKFLOW_SPEC_V1_DRAFT.md), [ví dụ tin nhắn](MESSAGE_EXAMPLES_V1_DRAFT.md).

## 1. Kết luận

| Phương án | Kết quả kiểm tra | Ý nghĩa với Bee Bot |
| --- | --- | --- |
| Nút trong tin nhắn Zalo Bot Platform | Trang tổng quan công bố nút/quick reply, nhưng chưa tìm được tham số gửi và cách nhận phản hồi nút trong API chi tiết đã kiểm tra | Có dấu hiệu hỗ trợ ở mức giới thiệu; chưa đủ thông tin để cam kết triển khai hoặc khẳng định không hỗ trợ |
| Nút qua Zalo Official Account | Có tài liệu chính thức về buttons và hành động gửi phản hồi về OA | Có cơ sở kỹ thuật làm nút trong chat; cần chọn API gửi còn áp dụng và xác minh điều kiện OA, quyền gửi và thiết bị |
| Bot gửi link tới trang xác nhận có nút | Có thể thiết kế trang web do dự án xây; nút nằm trên trang đó | Phương án bổ sung về thiết kế, không phụ thuộc nút tin nhắn của Bot; cần xác minh mở link trên các thiết bị và định danh người bấm |

Không đồng nhất Zalo Bot Platform với Zalo OA. Việc OA có tham số `buttons` không chứng minh có thể gửi cùng cấu trúc đó tới API của Bot Platform.

## 2. Zalo Bot Platform: thông tin chưa đủ thống nhất

### 2.1. Trang tổng quan có nhắc nút bấm

Trang [tổng quan Zalo Bot trong Document Hub](https://docs.zaloplatforms.com/docs/BOT) liệt kê nút bấm, quick reply và form. [Trang giới thiệu sản phẩm](https://docs.zaloplatforms.com/zalo-bot) cũng nhắc tới nút và template tương tác. Vì vậy kết luận tuyệt đối “Zalo Bot không có nút” chưa được chứng minh.

### 2.2. API chi tiết chưa mô tả cách gửi nút

Trang [sendMessage trong Document Hub](https://docs.zaloplatforms.com/docs/BOT/apis/sendMessage) và [sendMessage tại bot.zapps.me](https://bot.zapps.me/docs/apis/sendMessage/) mô tả các trường `chat_id`, `text`, `parse_mode`, `text_styles`; không thấy trường tạo nút hoặc payload nút.

Các tài liệu này cho phép định dạng văn bản. Danh sách HTML được hỗ trợ không có `<button>`; tài liệu nêu các thẻ ngoài danh sách bị loại bỏ, chỉ giữ nội dung chữ. Vì vậy không thể lấy việc hỗ trợ HTML làm căn cứ chèn nút tương tác vào tin nhắn.

Trang [webhook của Zalo Bot](https://docs.zaloplatforms.com/docs/BOT/webhook) liệt kê sự kiện nhận text, ảnh, sticker, voice và loại chưa hỗ trợ; chưa thấy đặc tả phản hồi nút. Điều này không loại trừ nút có thể gửi về dưới dạng text, nhưng chưa có mô tả chính thức nối thao tác bấm nút với dữ liệu Bot nhận được.

### 2.3. Kiểm tra SDK được tài liệu Zalo giới thiệu

[Hướng dẫn Bot của Zalo](https://docs.zaloplatforms.com/docs/BOT/best-practices/build-your-bot) dẫn tới [python-zalo-bot](https://pypi.org/project/python-zalo-bot/). Đã đọc mã nguồn wheel phiên bản 0.1.9 từ PyPI, không cài đặt hoặc chạy gói.

Trong `zalo_bot/_bot.py`, `send_message` nhận `chat_id`, `text` và tùy chọn `reply_to_message_id`; dữ liệu gửi gồm nội dung text và tùy chọn trả lời tin nhắn. Hàm này không cung cấp tham số tạo nút. Đây là giới hạn của hàm SDK đã kiểm tra, không phải bằng chứng server chắc chắn không hỗ trợ tham số chưa công bố.

Đã xem thêm gói [node-zalo-bot](https://www.npmjs.com/package/node-zalo-bot) 0.1.6 từ registry npm. Mã gửi tin được làm rối và có truyền đối tượng tùy chọn; chưa đủ cơ sở xác định tham số nút nào được server chấp nhận. Không suy luận rằng có thể dùng tham số nút của Telegram hoặc OA chỉ vì SDK có cấu trúc tương tự.

**Kết luận cho Bot Platform:** cần có đặc tả payload và phản hồi nút từ Zalo, hoặc kiểm chứng bằng bot thật, trước khi chốt giao diện nút trong tin nhắn.

## 3. Zalo OA: có tài liệu nút trả lời

Tài liệu [cấu trúc tham số buttons của OA](https://docs.zaloplatforms.com/docs/OA/phu-luc/cau-truc-cua-tham-so-buttons) mô tả:

- `oa.query.show`: bấm nút gửi nội dung payload từ người dùng tới OA và hiển thị nội dung đó trong chat.
- `oa.query.hide`: bấm nút gửi nội dung payload tới OA nhưng ẩn nội dung đó trên cửa sổ chat của người dùng.
- `oa.open.url`: bấm nút mở URL trong ứng dụng Zalo.

Tài liệu này ghi nút chỉ hiển thị trên Zalo Mobile, tối đa 5 nút ở cấu trúc được mô tả. Cần thử thực tế PC/Web và giữ cách phản hồi bằng chữ hoặc Sheets cho người vận hành nếu thiết bị không hiển thị nút.

**Suy luận ứng dụng cho Bee Bot:** có thể thiết kế nút Nhận ca/Từ chối chứa mã hành động, mã lời mời và phiên bản nội dung; phía xử lý xác định đúng yêu cầu từ dữ liệu nút, không cần AI đoán ý định. Nút Chấp nhận của vận hành xử lý tương tự nhưng phải kiểm tra quyền vận hành.

### 3.1. Điều kiện gửi và tài liệu cũ cần lưu ý

Trang [điều kiện gửi tin Tư vấn](https://docs.zaloplatforms.com/docs/OA/tin-nhan/tin-tu-van/dieu-kien-gui-tin-tu-van) yêu cầu ứng dụng có quyền gửi tin qua OA và người nhận có tương tác với OA trong vòng 7 ngày. Điều này cần được đối chiếu với việc Bee Bot gửi lời mời chủ động cho nhiều labcoach. Không áp điều kiện OA này sang Bot Platform.

Trang [gửi tin giao dịch](https://docs.zaloplatforms.com/docs/OA/tin-nhan/tin-giao-dich/gui-tin-giao-dich) có ví dụ template kèm nút, nhưng cũng có thông báo dịch vụ UID Giao dịch/UID Truyền thông cá nhân dừng từ 01/03/2026 và chuyển sang ZBS Template Message. Vì vậy không dùng ví dụ endpoint giao dịch cũ làm bằng chứng có thể triển khai nguyên trạng hiện nay.

**Kết luận cho OA:** tính năng nút được tài liệu xác nhận; API gửi cụ thể còn áp dụng, điều kiện gửi và việc dự án có OA phù hợp vẫn cần xác minh. Trước đó người phụ trách đã cho biết việc đăng ký OA riêng khó thực hiện, nên đây là phương án có điều kiện, chưa phải lựa chọn của dự án.

## 4. Phương án trang xác nhận có nút — đề xuất

Bot gửi lời mời với link xem chi tiết. Người dùng mở trang có thông tin ca, nội dung xác nhận không có lịch bận khác và các nút:

- Người nhận ca: **Đồng ý nhận ca** / **Từ chối**.
- Người hoán đổi: **Đồng ý giao và nhận hai ca** / **Từ chối**.
- Vận hành: **Chấp nhận yêu cầu nghỉ**; các thao tác khác chỉ thêm khi đã chốt quyền và quy tắc.

Đây là nút trên trang web, không phải nút gắn vào tin nhắn Zalo. Phương án này cần xây thêm trang xác nhận, kiểm tra trải nghiệm mở link và chọn cách xác thực người thao tác với danh sách Zalo đã được vận hành xác minh. Link được gửi cho một người chưa đủ để chứng minh người bấm là chính người đó nếu link được chuyển tiếp.

Khi mở link chỉ hiển thị thông tin; thay đổi trạng thái xảy ra khi người dùng xác nhận thao tác. Trang phải hiển thị yêu cầu hết hạn, đã có người nhận hoặc đang giữ vị trí để người trả lời sau biết họ không được nhận ca.

## 5. Các kiểm tra cần có nếu dùng nút

Đây là yêu cầu thiết kế kế thừa nghiệp vụ đã chốt, không phải kết quả thử nghiệm nền tảng:

1. Xác định đúng người thao tác và quyền, mã lời mời, ca cùng phiên bản nội dung được xác nhận.
2. Nội dung nút nhận ca phải thể hiện đồng ý nhận ca và không có lịch bận khác; thiếu xác nhận thì hỏi bổ sung.
3. Kiểm tra hạn 24 giờ, tối đa đến lúc ca bắt đầu; hoán đổi dùng ca sớm hơn.
4. Với tìm người, chỉ phát lời mời sau khi vận hành chấp nhận; người đủ điều kiện nhận sớm nhất được giữ vị trí, người sau không được nhận cùng vị trí.
5. Kiểm tra lại lịch chương trình, xử lý bấm nhiều lần/phản hồi đồng thời và giữ vị trí trước cập nhật.
6. Chỉ báo hoàn tất khi Sheets đã cập nhật đúng; bot giữ nguyên J.

Thử nghiệm nút tối thiểu cần chứng minh: gửi được tin kèm nút, bấm nút tạo dữ liệu mà backend xử lý được, xác định được đúng người/mã/hành động, và xử lý đúng hạn/giữ vị trí khi hai người cùng nhận. Hiện chưa thực hiện thử nghiệm này vì chưa có bot/OA được chọn và cấu hình trong dự án.

## 6. Đề xuất bước tiếp theo

Ưu tiên xác minh khả năng nút của Zalo Bot Platform vì đây là phương án pilot đang cân nhắc: lấy được payload mẫu và cách nhận phản hồi nút, sau đó thử trên một bot thật. Nếu chưa xác minh được, chọn giữa phản hồi chữ và trang xác nhận có nút. Nếu lựa chọn OA khả thi, xác minh API gửi và điều kiện OA trước thiết kế chi tiết.

Nghiên cứu này không tự chốt nền tảng, triển khai website hoặc đăng ký tài khoản. Các ví dụ tin nhắn hiện có tiếp tục là nội dung nghiệp vụ, chưa cam kết nút trong chat.
