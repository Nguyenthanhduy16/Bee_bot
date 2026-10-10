# Bee Bot — Ví dụ tin nhắn MVP v1

- **Trạng thái:** mẫu nội dung đề xuất để rà soát, chưa phải tin nhắn đã gửi hoặc giao diện đã triển khai.
- **Căn cứ:** [Phạm vi đã chốt](MVP_V1.md) và [đặc tả luồng nghiệp vụ](WORKFLOW_SPEC_V1_DRAFT.md).
- **Người gửi** trong tài liệu này là người tạo yêu cầu nghỉ/đổi ca hoặc báo issue. **Người nhận ca** là người được bot mời nhận thay hoặc hoán đổi.

Tên An, Lan, Bình, lớp, phòng, mã và thời điểm bên dưới là dữ liệu minh họa; không đại diện cho phân công thực tế trong Sheets. Mỗi tình huống thể hiện trạng thái tại lúc gửi; các nhánh thành công, hết hạn, từ chối và lỗi là những ví dụ độc lập.

## 1. Cách dùng mẫu

Mỗi tin cần nêu rõ mã theo dõi, ca/phòng liên quan, trạng thái và việc cần làm tiếp. Ngày giờ phải đầy đủ; sáng là 09:00–13:00, chiều là 14:00–18:00. Các thời điểm ví dụ dùng giờ Việt Nam; đây là quy ước đề xuất của đặc tả.

Nội dung lời mời và kết quả phải lấy từ thông tin đã đối chiếu với lịch, không điền theo suy đoán. Tin gửi vận hành đi tới danh sách người có quyền được cấu hình; danh sách cụ thể chưa chốt. Giờ gửi tổng hợp và việc gửi tin tiến độ cho vận hành ở từng bước còn cần rà soát.

Các mẫu dùng văn bản để dễ xem, chưa quyết định phải dùng nút hay gõ chữ. Câu trả lời ngắn kèm mã, đặc biệt lệnh chấp nhận của vận hành trong chat, là **đề xuất tương tác**, chưa được duyệt. Google Sheets tiếp tục là nơi vận hành theo dõi công việc.

Đã bổ sung [nghiên cứu khả năng nút trên Zalo](ZALO_BUTTON_RESEARCH.md): OA có tài liệu nút trả lời; Bot Platform có giới thiệu nút nhưng chưa xác minh được cách triển khai qua API chi tiết. Phương án trang xác nhận có nút cũng được ghi riêng để cân nhắc, chưa được chọn.

## 2. Thiếu thông tin hoặc chưa xác định được ca

**Gửi người tạo yêu cầu:**

> Mình chưa xác định được ca bạn muốn nghỉ. Bạn cho biết ngày và buổi Sáng/Chiều nhé. Nếu nhớ lớp hoặc phòng, bạn gửi thêm để mình tìm đúng ca.

Nếu có nhiều ca phù hợp:

> Mình tìm thấy hai phân công của bạn ngày 12/10/2026:
> 1. Track 1 / CS3 — H201 — 09:00–13:00.
> 2. Track 3B / CS4 — H205 — 14:00–18:00.
>
> Bạn muốn thay đổi ca nào?

**Gửi vận hành:** chưa cần gửi chỉ vì bot đang hỏi bổ sung. Nếu vẫn không đối chiếu được với lịch, đề xuất thông báo:

> **Cần đối chiếu lịch**
> Labcoach An báo nghỉ sáng 12/10/2026, phòng H201, nhưng bot chưa tìm được phân công phù hợp.
> Nhờ vận hành kiểm tra lịch và giúp xác định đúng ca. Bot chưa thay đổi lịch.

Chưa có mã yêu cầu thì không tự ghi một mã như thể đã lưu bản ghi thành công.

## 3. Nghỉ chưa có người thay — đã ghi nhận, chờ chấp nhận

**Gửi người tạo yêu cầu:**

> **Đã ghi nhận yêu cầu nghỉ — YC-000123**
> Ca: Track 1 / CS3 — H201.
> Thời gian: 12/10/2026, 09:00–13:00.
> Trạng thái: Chờ vận hành chấp nhận.
> Sau khi được chấp nhận, bot sẽ nhắn tìm người nhận ca. Hiện chưa có người thay và lịch chưa được cập nhật.
> Bạn có thể hỏi “YC-000123 đến đâu rồi?” để xem tiến độ.

**Gửi vận hành:**

> **Cần chấp nhận yêu cầu nghỉ — YC-000123**
> Người gửi: An.
> Ca: Track 1 / CS3 — H201.
> Thời gian: 12/10/2026, 09:00–13:00.
> Chưa có người thay.
> Nhờ vận hành xem yêu cầu và ghi nhận quyết định chấp nhận. Bot chỉ nhắn tìm người sau khi quyết định được ghi nhận.

Nếu chọn hỗ trợ chấp nhận qua chat, có thể thêm dòng sau vào tin vận hành:

> Trả lời “Chấp nhận YC-000123” để cho bot bắt đầu tìm người nhận ca.

Dòng này là đề xuất, không khẳng định lệnh chat đã được duyệt. Nếu dùng cách chấp nhận trên Sheets, tin phải hướng dẫn cập nhật đúng bản ghi/cột được chọn khi triển khai. Dù dùng cách nào, phải xác định đúng người có quyền và đúng mã yêu cầu.

## 4. Vận hành đã chấp nhận — bot bắt đầu tìm người

**Gửi người tạo yêu cầu:**

> **Yêu cầu nghỉ đã được chấp nhận — YC-000123**
> Ca: Track 1 / CS3 — H201, 12/10/2026, 09:00–13:00.
> Bot đang nhắn đồng thời cho các labcoach hợp lệ, không trùng lịch để tìm người nhận ca.
> Hiện đang chờ người nhận xác nhận; lịch chưa được thay đổi.

**Gửi vận hành — mẫu xác nhận tiến độ đề xuất:**

> **Đang tìm người nhận ca — YC-000123**
> Đã ghi nhận việc chấp nhận yêu cầu nghỉ của An.
> Bot đang gửi lời mời cho các labcoach hợp lệ, không trùng lịch.
> Người xác nhận đầy đủ và đủ điều kiện sớm nhất được nhận ca. Bot sẽ thông báo khi cập nhật lịch thành công hoặc cần vận hành xử lý.

## 5. Có người nhận đầu tiên — đang cập nhật lịch

Chỉ gửi sau khi người nhận đã xác nhận đầy đủ, vượt qua kiểm tra và được giữ vị trí.

**Gửi người tạo yêu cầu:**

> **Đang cập nhật lịch — YC-000123**
> Lan là người đầu tiên xác nhận đầy đủ và đủ điều kiện nhận ca Track 1 / CS3 — H201, 12/10/2026, 09:00–13:00.
> Bot đang cập nhật lịch. Yêu cầu chưa hoàn tất; mình sẽ báo kết quả sau khi kiểm tra.

**Gửi vận hành — mẫu tiến độ đề xuất:**

> **Đang cập nhật lịch — YC-000123**
> Người nhận đang được giữ vị trí: Lan, thay An.
> Ca: Track 1 / CS3 — H201, 12/10/2026, 09:00–13:00.
> Bot đang cập nhật phân công. Các phản hồi đến sau không được nhận cùng vị trí này.
> Chưa xác nhận lịch đã cập nhật thành công.

## 6. Nhận thay thành công

Áp dụng cho cả ca đã có người dự kiến và ca tìm được người sau chấp nhận. Chỉ gửi khi lịch đã cập nhật đúng và được kiểm tra.

**Gửi người tạo yêu cầu:**

> **Đã bố trí người thay và cập nhật lịch — YC-000123**
> Lan đã nhận thay ca của bạn: Track 1 / CS3 — H201.
> Thời gian: 12/10/2026, 09:00–13:00.
> Lịch chính thức đã ghi Lan thay An tại phân công này.
> Yêu cầu đã hoàn tất.

**Gửi vận hành:**

> **Đã cập nhật lịch — YC-000123**
> Ca: Track 1 / CS3 — H201, 12/10/2026, 09:00–13:00.
> Thay đổi: An → Lan.
> Đã xác nhận trực tiếp, kiểm tra lịch và đối chiếu kết quả cập nhật thành công.
> Bot giữ nguyên cột J; vận hành cập nhật J nếu cần.

Nếu là nhận thay đã có người dự kiến, có thể dùng tiêu đề “Nhận thay thành công”; không nói yêu cầu đã được vận hành chấp nhận khi luồng đó không có bước chấp nhận.

## 7. Hết hạn tìm người hoặc không có người nhận

Ví dụ ca sáng 12/10/2026 đã tới 09:00 mà chưa có người nhận đủ điều kiện. Nếu lời mời mới gửi lúc 10:00 ngày 11/10, hạn là 09:00 ngày 12/10.

**Gửi người tạo yêu cầu:**

> **Chưa bố trí được người thay — YC-000123**
> Ca: Track 1 / CS3 — H201, 12/10/2026, 09:00–13:00.
> Các lời mời đã hết hạn và chưa có người nhận đủ điều kiện. Bot đã báo vận hành xử lý.
> Yêu cầu chưa hoàn tất; bot chưa cập nhật người thay lên lịch.

**Gửi vận hành:**

> **Cần xử lý ca chưa có người thay — YC-000123**
> Người báo nghỉ: An.
> Ca: Track 1 / CS3 — H201, 12/10/2026, 09:00–13:00.
> Đã hết hạn lời mời, chưa có người nhận đủ điều kiện và ca đã đến giờ bắt đầu.
> Bot dừng tìm tự động. Nhờ vận hành bố trí và xử lý tình huống ca đang thiếu người.

Nếu không có ứng viên ngay từ đầu, thay lý do bằng “Không có labcoach hợp lệ, không trùng lịch để gửi lời mời”. Một người từ chối trong khi những lời mời khác còn hiệu lực không đủ để gửi thông báo “không có người nhận”.

## 8. Nhận thay đã có người dự kiến — chờ xác nhận

**Gửi người tạo yêu cầu:**

> **Đã ghi nhận yêu cầu nhận thay — YC-000124**
> Bạn đề nghị Bình nhận thay ca Track 2 / CS4 — H209, 13/10/2026, 14:00–18:00.
> Bot đã gửi lời mời, đang chờ Bình xác nhận nhận ca và không có lịch bận khác.
> Hạn trả lời: 13/10/2026, 10:00.
> Lịch chưa được thay đổi.

Hạn trên áp dụng khi lời mời được phát hành lúc 10:00 ngày 12/10: sau 24 giờ vẫn sớm hơn lúc ca bắt đầu.

**Gửi vận hành — mẫu theo dõi đề xuất:**

> **Đang chờ người nhận xác nhận — YC-000124**
> An đề nghị Bình nhận thay ca Track 2 / CS4 — H209, 13/10/2026, 14:00–18:00.
> Hạn lời mời: 13/10/2026, 10:00. Lịch chưa đổi.
> Đây là luồng đã có người dự kiến; đủ điều kiện thì bot tự cập nhật, không cần vận hành duyệt từng yêu cầu.

## 9. Người được đề nghị từ chối hoặc bị trùng lịch

**Gửi người tạo yêu cầu:**

> **Cần chọn bước tiếp theo — YC-000124**
> Bình đã từ chối nhận ca Track 2 / CS4 — H209, 13/10/2026, 14:00–18:00.
> Lịch chưa được thay đổi.
> Bạn có thể đề nghị người khác, đề nghị chuyển sang vận hành xử lý hoặc hủy yêu cầu.

Nếu người nhận bị trùng lịch, thay lý do bằng “Bình chưa thể nhận ca vì trùng một phân công khác trong lịch chương trình”; không gửi lịch cá nhân chi tiết của Bình cho người tạo yêu cầu.

**Gửi vận hành — khi cần can thiệp:**

> **Cần hỗ trợ yêu cầu nhận thay — YC-000124**
> Người gửi: An. Người dự kiến nhận: Bình.
> Ca: Track 2 / CS4 — H209, 13/10/2026, 14:00–18:00.
> Bình đã từ chối. Người gửi đề nghị vận hành hỗ trợ bố trí.
> Chưa có người thay và lịch chưa đổi. Nếu chuyển sang tìm người bằng bot, cần ghi nhận chấp nhận yêu cầu trước khi phát lời mời.

Chỉ gửi mẫu can thiệp này khi có lý do chuyển vận hành, không tự khẳng định người gửi đã đề nghị hỗ trợ nếu họ chưa chọn bước đó.

## 10. Hoán đổi hai ca

### 10.1. Đang chờ xác nhận

**Gửi người tạo yêu cầu:**

> **Đã ghi nhận hoán đổi — YC-000125**
> Bạn giao cho Bình: Track 1 / CS3 — H201, 12/10/2026, 09:00–13:00.
> Bạn nhận từ Bình: Track 2 / CS4 — H209, 13/10/2026, 14:00–18:00.
> Bạn đã xác nhận; bot đang chờ Bình xác nhận đầy đủ.
> Hạn lời mời: 12/10/2026, 09:00. Cả hai phân công chưa được thay đổi.

Mẫu này giả định người gửi đã xác nhận cả giao/nhận và không có lịch bận khác ở ca nhận về; lời mời cho Bình được phát hành lúc 10:00 ngày 11/10.

**Gửi vận hành — mẫu theo dõi đề xuất:**

> **Đang chờ xác nhận hoán đổi — YC-000125**
> An giao ca sáng 12/10/2026 ở H201 cho Bình.
> Bình giao ca chiều 13/10/2026 ở H209 cho An.
> Đã có xác nhận đầy đủ của An, đang chờ Bình. Lịch chưa đổi.
> Đủ xác nhận và không trùng lịch sau đổi thì bot tự cập nhật cả hai phân công.

### 10.2. Hoán đổi hoàn tất

**Gửi người tạo yêu cầu:**

> **Hoán đổi thành công — YC-000125**
> Bình phụ trách Track 1 / CS3 — H201, 12/10/2026, 09:00–13:00.
> Bạn phụ trách Track 2 / CS4 — H209, 13/10/2026, 14:00–18:00.
> Cả hai phân công đã được cập nhật và kiểm tra trên lịch chính thức.
> Yêu cầu đã hoàn tất.

**Gửi vận hành:**

> **Hoán đổi đã hoàn tất — YC-000125**
> Track 1 / CS3 — H201, 12/10/2026, 09:00–13:00: An → Bình.
> Track 2 / CS4 — H209, 13/10/2026, 14:00–18:00: Bình → An.
> Đã xác nhận và kiểm tra thành công cả hai thay đổi.
> Bot giữ nguyên J ở cả hai dòng; vận hành cập nhật J nếu cần.

Nếu một người từ chối hoặc lời mời hết hạn, tin phải nói hoán đổi chưa thực hiện; không dùng mẫu hoàn tất cho một ca riêng lẻ.

## 11. Báo issue phòng học

### 11.1. Đã ghi nhận

**Gửi người báo issue:**

> **Đã ghi nhận issue — IS-000045**
> Phòng: H209.
> Vấn đề: Wi-Fi yếu, ảnh hưởng việc làm lab.
> Thời điểm phát hiện: 12/10/2026, 08:45.
> Bot đã báo vận hành. Trạng thái: Đã ghi nhận.
> Bạn có thể hỏi “IS-000045 xử lý đến đâu rồi?” để xem tiến độ.

**Gửi vận hành:**

> **Issue mới — IS-000045**
> Người báo: An. Phòng: H209.
> Vấn đề: Wi-Fi yếu, ảnh hưởng việc làm lab.
> Phát hiện lúc 08:45 ngày 12/10/2026.
> Nhờ vận hành phân công người phụ trách và cập nhật tiến độ trên Sheets.

Nếu có ảnh đã được người báo gửi, kèm ảnh hoặc tham chiếu ảnh theo cách nền tảng hỗ trợ; không yêu cầu ảnh để ghi nhận issue.

### 11.2. Đang xử lý

**Gửi người báo issue, sau khi vận hành cập nhật:**

> **Issue đang được xử lý — IS-000045**
> Wi-Fi phòng H209.
> Vận hành đã ghi nhận đang kiểm tra đường truyền và thiết bị mạng.
> Cập nhật lúc 09:15 ngày 12/10/2026. Hiện chưa có xác nhận giải quyết xong.

**Gửi vận hành — mẫu xác nhận cập nhật đề xuất:**

> **Đã ghi nhận tiến độ — IS-000045**
> Trạng thái: Đang xử lý.
> Nội dung: Kiểm tra đường truyền và thiết bị mạng.
> Bot đã thông báo tiến độ cho người báo issue.

Dòng “đã thông báo” chỉ dùng khi gửi tin thành công; nếu gửi chưa thành công, ghi “Thông báo cho người báo đang chờ gửi lại”.

### 11.3. Đã giải quyết

**Gửi người báo issue, sau khi vận hành xác nhận kết quả:**

> **Issue đã được giải quyết — IS-000045**
> Wi-Fi phòng H209.
> Vận hành xác nhận đã xử lý thiết bị mạng và kiểm tra lại kết nối.
> Thời điểm xác nhận: 12/10/2026, 10:20.
> Trạng thái: Đã giải quyết.

**Gửi vận hành — mẫu xác nhận kết quả đề xuất:**

> **Đã ghi nhận kết quả xử lý — IS-000045**
> Phòng H209: Đã giải quyết.
> Kết quả: Xử lý thiết bị mạng, kiểm tra lại kết nối.
> Kết quả đã được lưu; bot sẽ thông báo cho người báo issue.

Không tự suy ra “đã giải quyết” từ ghi chú đang kiểm tra hoặc lời đoán của bot.

## 12. Lỗi cập nhật lịch — cần vận hành xử lý

### 12.1. Chưa xác định được việc ghi lịch có thành công không

**Gửi người tạo yêu cầu:**

> **Đang kiểm tra kết quả cập nhật — YC-000123**
> Bot đã chọn Lan nhận ca nhưng chưa xác định được kết quả cập nhật lịch.
> Yêu cầu chưa được báo hoàn tất. Bot đang đối chiếu lịch và đã báo vận hành.
> Vị trí đang giữ cho Lan; phản hồi đến sau chưa được nhận ca này.

**Gửi vận hành:**

> **Cần đối chiếu kết quả cập nhật — YC-000123**
> Ca: Track 1 / CS3 — H201, 12/10/2026, 09:00–13:00.
> Người được chọn: Lan, thay An.
> Lần ghi không trả kết quả rõ ràng; chưa biết phân công đã đổi hay chưa.
> Nhờ vận hành kiểm tra cùng bot. Chưa giao vị trí này cho người khác trước khi xác định kết quả.

### 12.2. Hoán đổi mới cập nhật được một ca

**Gửi người tạo yêu cầu:**

> **Hoán đổi chưa hoàn tất — YC-000125**
> Bot phát hiện hai phân công chưa được cập nhật đầy đủ.
> Yêu cầu đang được đối chiếu và đã báo vận hành xử lý. Mình sẽ báo lại khi xác định được kết quả của cả hai ca.

**Gửi vận hành:**

> **Cần xử lý hoán đổi cập nhật một phần — YC-000125**
> Ca sáng 12/10/2026 ở H201 đã đổi An → Bình.
> Ca chiều 13/10/2026 ở H209 chưa đổi Bình → An.
> Hoán đổi chưa hoàn tất. Nhờ vận hành đối chiếu cả hai phân công và xử lý theo quy trình phục hồi.
> Không thực hiện lại toàn bộ hoán đổi khi chưa kiểm tra kết quả hiện tại.

Mẫu vận hành này chỉ dùng khi đã đọc lại và biết rõ kết quả từng ca; nếu chưa biết, phải ghi “chưa xác định” thay vì khẳng định đã đổi/chưa đổi.

## 13. Hủy yêu cầu trước khi cập nhật

Quyền và điều kiện hủy chi tiết vẫn là đề xuất trong đặc tả. Các mẫu dưới đây áp dụng khi đã xác minh hủy hợp lệ và ghi nhận hủy thành công.

**Gửi người tạo yêu cầu:**

> **Đã hủy yêu cầu — YC-000123**
> Ca: Track 1 / CS3 — H201, 12/10/2026, 09:00–13:00.
> Lượt tìm người đã dừng và các lời mời còn mở đã bị vô hiệu.
> Bot chưa cập nhật người thay cho yêu cầu này.

**Gửi vận hành:**

> **Yêu cầu đã hủy — YC-000123**
> Người yêu cầu hủy: An.
> Ca: Track 1 / CS3 — H201, 12/10/2026, 09:00–13:00.
> Đã hủy trước khi cập nhật lịch; bot dừng tìm người và vô hiệu lời mời còn mở.

Không dùng mẫu này khi đang ghi, kết quả ghi chưa rõ hoặc yêu cầu đã hoàn tất; phải đối chiếu lịch trước khi xử lý.

## 14. Trả lời tra cứu và tổng hợp cho vận hành

**Người tạo yêu cầu hỏi “YC-000123 đến đâu rồi?” — bot trả lời:**

> **YC-000123 — Đang tìm người nhận ca**
> Ca: Track 1 / CS3 — H201, 12/10/2026, 09:00–13:00.
> Vận hành đã chấp nhận; đang chờ labcoach xác nhận nhận ca.
> Chưa bố trí được người thay và lịch chưa cập nhật.
> Cập nhật gần nhất: 11/10/2026, 10:30.

Bot trả trạng thái thực tế tại lúc hỏi, không dùng câu cố định ở mọi trạng thái. Khi người gửi có nhiều yêu cầu phù hợp, hỏi chọn mã trước khi trả chi tiết.

**Gửi vận hành — bản tổng hợp minh họa:**

> **Các việc đang chờ — cập nhật lúc 11/10/2026, 17:00**
> • YC-000126: An nghỉ ca sáng 13/10 ở H201 — chờ vận hành chấp nhận.
> • YC-000127: Ca chiều 13/10 ở H209 — đang tìm người nhận.
> • YC-000128: Ca sáng 14/10 ở H205 — cần đối chiếu kết quả cập nhật.
> • IS-000046: Thiếu ổ điện H209 — đang xử lý, chưa có kết quả giải quyết.
> Nhờ vận hành kiểm tra các bản ghi tương ứng trên Sheets.

17:00 chỉ là giờ ví dụ, không phải giờ gửi đã chốt. Bản tổng hợp chỉ lấy việc còn mở và trạng thái đã ghi nhận. Không gửi danh sách công việc chung này cho labcoach không có quyền vận hành.

## 15. Bổ sung: lời mời và kết quả gửi cho người nhận ca

Phần này làm rõ nội dung mà người nhận xác nhận, để các tin gửi người tạo yêu cầu/vận hành ở trên có căn cứ.

**Lời mời gửi đồng thời cho từng ứng viên sau chấp nhận:**

> **Mời nhận ca — YC-000123**
> Ca: Track 1 / CS3 — H201.
> Thời gian: 12/10/2026, 09:00–13:00.
> Hạn phản hồi: 12/10/2026, 09:00.
> Bạn có đồng ý nhận ca và xác nhận không có lịch bận khác trong khoảng giờ này không?
> Người xác nhận đầy đủ và đủ điều kiện sớm nhất sẽ được nhận.

Nếu chọn dùng câu trả lời ngắn, đề xuất thêm:

> Trả lời “Nhận YC-000123” nghĩa là đồng ý nhận ca và xác nhận không có lịch bận khác trong khoảng giờ trên.
> Trả lời “Từ chối YC-000123” nếu không nhận.

Bot chỉ xử lý cho đúng người được mời và đúng lời mời còn hiệu lực. Với câu trả lời như “ok” chưa rõ đủ ý, hỏi bổ sung; không tự suy ra xác nhận lịch bận khác.

**Gửi người được giữ vị trí đầu tiên:**

> **Đang cập nhật lịch — YC-000123**
> Bạn là người đầu tiên xác nhận đầy đủ và đủ điều kiện; vị trí nhận ca đang được giữ cho bạn.
> Bot đang cập nhật lịch và sẽ báo khi kiểm tra xong. Hiện chưa xác nhận hoàn tất.

**Gửi người trả lời sau khi vị trí đang được giữ:**

> **Vị trí đang được xử lý cho người khác — YC-000123**
> Đã có người đủ điều kiện xác nhận trước bạn. Bạn không được nhận vị trí này.
> Bot đang kiểm tra kết quả cập nhật cho người đã được chọn.

**Gửi người nhận khi cập nhật thành công:**

> **Bạn đã nhận ca thành công — YC-000123**
> Track 1 / CS3 — H201, 12/10/2026, 09:00–13:00.
> Lịch chính thức đã ghi bạn nhận thay An tại phân công này.

**Gửi ứng viên còn lời mời sau khi ca đã có người:**

> **Ca đã có người nhận — YC-000123**
> Ca Track 1 / CS3 — H201, 12/10/2026, 09:00–13:00 đã được cập nhật cho người nhận.
> Lời mời gửi bạn đã đóng; bạn không được phân công ca này.

## 16. Điểm cần rà soát trước khi đưa mẫu vào bot

- Chọn cách phản hồi lời mời và cách vận hành chấp nhận: text trong chat, thao tác trên Sheets hoặc phương án khác được duyệt; chưa cam kết nút bấm trong Zalo.
- Chốt danh sách người nhận thông báo vận hành, giờ tổng hợp và các tin tiến độ nào cần gửi ngay.
- Mã, tên, ca, trạng thái, hạn và kết quả phải lấy từ bản ghi đã xác thực; mẫu không thay thế các kiểm tra của đặc tả.
- “Đã gửi”, “đã lưu”, “đã cập nhật”, “đã hủy” chỉ dùng khi có kết quả tương ứng. Gửi tin thất bại thì theo dõi gửi lại, không thực hiện lại thay đổi lịch.
