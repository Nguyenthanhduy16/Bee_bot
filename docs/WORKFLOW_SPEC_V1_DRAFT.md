# Bee Bot — Đặc tả luồng và dữ liệu MVP v1 (bản nháp)

- **Ngày soạn:** 10/10/2026.
- **Căn cứ:** [Phạm vi và quyết định MVP v1](MVP_V1.md).
- **Mục đích:** đặc tả nghiệp vụ và căn cứ nghiệm thu bản thử/pilot.
- **Trạng thái:** người phụ trách đã xác nhận quy tắc trong [bảng quyết định](DECISIONS_TO_START_V1.md) và yêu cầu thực hiện; bản thử đã được xây. Tên tab/cột pilot và các chi tiết chưa kiểm chứng vẫn là đề xuất.

Các quy tắc ghi **Đã chốt** kế thừa tài liệu phạm vi. Tên tab/cột, mã trạng thái, điều kiện ngoại lệ, mẫu hội thoại và cách tổ chức dữ liệu dưới đây là **Đề xuất**. Không coi bản nháp này là quyết định chọn kiến trúc, nền tảng hay nhà cung cấp AI.

Đã đọc Sheets người phụ trách cung cấp; xem [đối chiếu cấu trúc và quy tắc đọc/ghi đề xuất](SHEETS_MAPPING_V1_DRAFT.md). Đã xác nhận D là phân công chính thức, J phục vụ xếp ca theo bận/rảnh, B–J là nguồn chuẩn; ca sáng 09:00–13:00 và chiều 14:00–18:00 áp dụng cho tất cả lớp có lịch. Phạm vi tự động nhận thay/hoán đổi, vận hành xác thực liên kết Zalo với mã labcoach và kiểm tra lịch chương trình kết hợp tự xác nhận lịch bận khác đã chốt; quy trình thực hiện cụ thể vẫn là đề xuất để rà soát.

## 1. Quy tắc xuyên suốt

| Quy tắc | Mức quyết định |
| --- | --- |
| Lịch chính thức nằm trên Google Sheets | Đã chốt |
| Từ pilot, yêu cầu thông thường gửi qua bot Zalo; vận hành hỗ trợ khi bot lỗi hoặc có việc khẩn, không duy trì Google Form/tin riêng làm kênh thường lệ | Đã chốt khi tiếp tục |
| Cột D là phân công chính thức; J là thông tin khả dụng phục vụ xếp ca | Đã chốt khi tiếp tục |
| Khi bot đổi người ở D, giữ nguyên J để vận hành tự cập nhật | Đã chốt khi tiếp tục |
| Vận hành và bot đều được cập nhật D trực tiếp; bot đọc lại để kiểm tra trước ghi và xác minh kết quả sau ghi | Đã chốt khi tiếp tục; giới hạn sửa đồng thời còn cần kiểm chứng |
| B–J là vùng nguồn chuẩn khi khác K–P | Đã chốt khi tiếp tục |
| Mọi lớp có lịch dùng ca sáng 09:00–13:00 và chiều 14:00–18:00 | Đã chốt khi tiếp tục |
| Liên kết tài khoản Zalo với mã labcoach được vận hành xác thực trước khi dùng | Đã chốt khi tiếp tục |
| Bot kiểm tra lịch chương trình; người nhận tự xác nhận không có lịch bận khác trong ca nhận | Đã chốt khi tiếp tục |
| Người thay phải trực tiếp xác nhận; lời người gửi không thay cho xác nhận này | Đã chốt |
| Bất kỳ labcoach nào cũng có thể nhận thay nếu đồng ý và không trùng lịch | Đã chốt |
| Trường hợp đủ điều kiện tự cập nhật lịch, không cần vận hành duyệt từng yêu cầu | Đã chốt |
| Tự động hỗ trợ cả nhận thay một ca và hoán đổi hai ca | Đã chốt khi tiếp tục |
| Chỉ báo hoàn tất thay ca khi lịch đã cập nhật thành công | Đã chốt |
| Nghỉ chưa có người thay: chờ vận hành chấp nhận, sau đó bot có thể nhắn tìm người nhận ca | Đã chốt khi tiếp tục, thay thế giới hạn trước |
| Người gửi bổ sung người thay khi đang chờ vận hành chấp nhận: báo vận hành, giữ mã yêu cầu và chuyển sang nhận thay không cần duyệt nghỉ | Đã chốt khi tiếp tục |
| Nhắn đồng thời các labcoach hợp lệ không trùng lịch; người nhận đủ điều kiện sớm nhất được nhận, người sau không nhận cùng vị trí | Đã chốt khi tiếp tục |
| Người do vận hành bố trí vẫn phải trực tiếp xác nhận với bot trước cập nhật lịch | Đã chốt khi tiếp tục |
| Lời mời hết hạn sau 24 giờ, tối đa đến lúc ca bắt đầu; hoán đổi dùng ca sớm hơn | Đã chốt khi tiếp tục |
| Issue chỉ được báo đã giải quyết khi vận hành xác nhận kết quả | Đã chốt |
| Người gửi tra cứu yêu cầu của mình; vận hành có phạm vi theo dõi chung | Đã chốt |
| AI có thể hỗ trợ hiểu câu nói; quyền sửa lịch dựa trên định danh, xác nhận và điều kiện nghiệp vụ | Đề xuất |
| Nhận thay gắn với một phân công; hoán đổi gắn với hai phân công thuộc hai người khác nhau | Đề xuất |
| Chỉ xác nhận thao tác trên yêu cầu đã xác định rõ bằng mã và nội dung | Đề xuất |

## 2. Định danh và quyền thao tác

**Đã chốt:** dùng danh sách mã labcoach và tài khoản Zalo được vận hành xác thực trước khi sử dụng.

**Quy trình thực hiện đề xuất:** vận hành lập danh sách người dùng được phép sử dụng, đối chiếu đúng mã/tên labcoach với tài khoản Zalo và ghi ai xác thực, thời điểm xác thực. Chỉ liên kết đã được xác thực và còn hoạt động mới được dùng để tra cứu lịch cá nhân, gửi yêu cầu hoặc xác nhận nhận ca. Không tự cấp quyền chỉ từ tên hiển thị hoặc lời tự giới thiệu.

| Người thao tác | Quyền đề xuất |
| --- | --- |
| Labcoach gửi yêu cầu | Báo thay đổi phân công của mình; báo issue; xem yêu cầu của mình; đề nghị hủy yêu cầu của mình |
| Labcoach được mời nhận thay | Xem nội dung ca cần nhận và xác nhận/từ chối đúng lời mời gửi cho mình |
| Vận hành | Theo dõi chung; chấp nhận yêu cầu nghỉ, đề cử người thay; tự cập nhật J; phân công/cập nhật issue; xử lý ngoại lệ và quản lý liên kết người dùng |
| Bot | Ghi nhận; nhắn tìm người cho yêu cầu nghỉ đã được vận hành chấp nhận; lấy xác nhận, kiểm tra điều kiện, cập nhật phân công đủ điều kiện; thông báo và trả lời tra cứu |

Người nhận thay cần xem được ca, người đang phụ trách và mã lời mời, nhưng không cần thấy lý do nghỉ hay toàn bộ lịch sử yêu cầu của người gửi. Quyền này là đề xuất bổ sung để thực hiện luồng xác nhận đã chốt.

Tài khoản chưa liên kết nhận hướng dẫn liên hệ vận hành; bot không cung cấp lịch cá nhân hoặc nhận xác nhận thay ca có hiệu lực từ tài khoản đó. Nguyên tắc xác thực đã chốt; cách thu thập mã tài khoản Zalo, tổ chức danh sách và cấp quyền vận hành sẽ hoàn thiện trong thiết kế triển khai.

### 2.1. Danh sách liên kết và vòng đời — đề xuất

Mỗi người có `person_id`, tên dùng trên lịch, tên/biến thể để đối chiếu nếu có, vai trò, trạng thái hoạt động và tài khoản Zalo đã xác thực. Các tên giống nhau phải được gắn đúng mã người; một tài khoản Zalo không được đồng thời đại diện cho hai mã người đang hoạt động.

Vận hành xác thực bằng thông tin đã có trong team, rồi ghi `linked_by` và `linked_at`; không yêu cầu labcoach gửi lịch bận cá nhân để chứng minh danh tính. Cách trao đổi hoặc mã liên kết cụ thể chưa chọn.

Nếu đổi tài khoản hoặc ngừng tham gia, vận hành cập nhật liên kết và trạng thái. Đề xuất vô hiệu quyền của tài khoản cũ và đối chiếu lại lời mời đang chờ; trước khi sửa lịch, kiểm tra tài khoản xác nhận vẫn liên kết đúng người và còn hoạt động. Lịch sử xác nhận cũ vẫn được giữ để truy vết, không chuyển sang người khác chỉ vì đổi tên hiển thị.

## 3. Các luồng hội thoại

Các câu bên dưới là mẫu nội dung, không yêu cầu nền tảng có nút bấm. Mọi ngày giờ khi xác nhận phải ghi đầy đủ ngày, năm và giờ theo múi giờ vận hành được thống nhất. Đề xuất dùng Asia/Ho_Chi_Minh; chỉ diễn giải từ như “mai” khi xác định được thời điểm gửi, rồi nhắc lại bằng ngày cụ thể.

Khả năng dùng nút trong lời mời/chấp nhận được phân tích tại [Nghiên cứu nút bấm trên Zalo](ZALO_BUTTON_RESEARCH.md). Kết quả nghiên cứu chưa thay đổi các điều kiện xác nhận, quyền, hạn hoặc thứ tự nhận ca, và chưa phải quyết định chọn giao diện.

Thông tin ca lấy từ tiêu đề ngày ở A và vùng bảng chính B–J, giải đúng ô gộp. Sáng hiển thị 09:00–13:00, chiều 14:00–18:00. Người đang phụ trách lấy từ D; nhãn Rảnh ở J không thay cho xác nhận trực tiếp hoặc kiểm tra phân công trùng lịch.

### 3.1. Nhận thay một ca đã có người dự kiến

1. Người gửi: “Tôi nghỉ ca H209 sáng mai, nhờ Lan thay.”
2. Bot nhận diện người gửi và tìm các phân công phù hợp. Không thấy ca: hỏi lại ngày/lớp/giờ. Nhiều ca: liệt kê lựa chọn đủ thông tin, chưa tự chọn.
3. Nếu tên Lan ứng với nhiều người, yêu cầu chọn đúng người bằng mã/tên trong danh sách được phép.
4. Bot nhắc lại: “Bạn đề nghị Lan nhận thay ca [Track/Session], phòng H209, ngày [dd/mm/yyyy], Sáng 09:00–13:00. Xác nhận gửi yêu cầu?”
5. Sau xác nhận của người gửi, ghi yêu cầu có mã, ví dụ YC-000123. Chỉ báo “đã ghi nhận” sau khi bản ghi đã lưu thành công.
6. Bot gửi trực tiếp cho Lan: “YC-000123: [người gửi] nhờ bạn nhận ca [thông tin đầy đủ]. Bạn có đồng ý nhận ca và xác nhận không có lịch bận khác trong khoảng giờ này không?” Việc tự xác nhận lịch bận khác đã chốt; mẫu câu là đề xuất.
7. Bot chỉ nhận phản hồi từ đúng tài khoản Lan đã liên kết, cho đúng yêu cầu còn hiệu lực. Nếu “đồng ý” có thể ứng với nhiều lời mời, hỏi lại mã.
8. Khi Lan đồng ý nhận ca và xác nhận không có lịch bận khác, đọc lại lịch chương trình và kiểm tra xung đột, hiệu lực yêu cầu, liên kết người dùng, người đang được phân công và thông tin ca trước khi sửa. Nếu Lan chỉ nói đã đồng ý mà chưa rõ xác nhận lịch bận khác, bot hỏi bổ sung, giữ yêu cầu chưa hoàn tất.
9. Đủ điều kiện: chuyển sang đang cập nhật lịch, thực hiện cập nhật và kiểm tra kết quả. Chỉ sau khi xác nhận lịch đúng mới chuyển hoàn tất.
10. Gửi kết quả cho người gửi, người thay và vận hành. Nếu gửi thông báo thất bại, theo dõi gửi lại; trạng thái hoàn tất dựa trên lịch đã cập nhật.

Không yêu cầu lý do nghỉ nếu không cần cho xử lý. Nhận thay cùng ca cho chính mình không tạo thay đổi; bot giải thích và yêu cầu chọn người khác.

### 3.2. Nghỉ chưa có người thay

1. Người gửi báo ca nghỉ; bot xác định phân công và hỏi lại khi thiếu thông tin.
2. Bot nhắc lại ca và nêu rõ: “Yêu cầu sẽ được gửi cho vận hành xem và chấp nhận. Sau chấp nhận, bot có thể tìm người nhận ca. Ca chưa có người thay cho đến khi người nhận xác nhận và lịch được cập nhật.”
3. Người gửi xác nhận; bot lưu yêu cầu, cấp mã và thông báo vận hành.
4. Nếu vẫn chưa có người thay, vận hành xác định đúng mã/ca và chấp nhận yêu cầu trước khi bot phát lời mời tìm người. Ghi người chấp nhận, thời điểm và nội dung ca được chấp nhận. Nếu người gửi bổ sung người thay trong lúc chờ chấp nhận, chuyển sang nhánh nhận thay bên dưới.
5. Nếu vận hành đề cử người nhận, bot lấy xác nhận trực tiếp của người đó như luồng 3.1. Nếu chưa có người đề cử, bot nhắn tìm người nhận sau chấp nhận theo mục 3.2.1. Không yêu cầu thêm một lần duyệt chỉ để bắt đầu tìm người cho cùng nội dung đã chấp nhận.
6. Người nhận xác nhận nhận ca và không có lịch bận khác; bot đọc lại lịch, kiểm tra tài khoản, hiệu lực lời mời, phân công gốc và không trùng lịch chương trình.
7. Đủ điều kiện thì bot cập nhật đúng D, giữ nguyên J và kiểm tra kết quả. Chỉ sau khi lịch đúng mới báo “Đã bố trí và cập nhật lịch”, thông báo người gửi, người nhận và vận hành.
8. Nếu chưa có người, lời mời hết hạn hoặc cập nhật thất bại, giữ chưa hoàn tất, báo lý do và chuyển vận hành xử lý theo ngoại lệ.

**Đã chốt:** người do vận hành bố trí vẫn phải trực tiếp xác nhận với bot; bot có thể nhắn tìm người sau khi vận hành chấp nhận yêu cầu nghỉ. Đây là mở rộng thay thế giới hạn không tìm/mời người của bản trước.

**Đã chốt — bổ sung người thay khi đang chờ vận hành chấp nhận:** bot cập nhật cùng mã yêu cầu, báo vận hành rằng người gửi đã tìm được người dự kiến nhận thay và chuyển yêu cầu sang luồng nhận thay ở mục 3.1; không cần chờ vận hành chấp nhận nghỉ. Người thay vẫn phải xác nhận trực tiếp việc nhận ca và không có lịch bận khác; bot kiểm tra lịch chương trình và các điều kiện trước khi cập nhật D, giữ nguyên J. Thông báo đã tìm được người dự kiến không đồng nghĩa ca đã được bố trí hoặc yêu cầu đã hoàn tất.

Mẫu báo vận hành: “YC-000123: An đã bổ sung Bình làm người dự kiến nhận thay ca [thông tin]. Yêu cầu chuyển sang chờ Bình xác nhận theo luồng nhận thay; không còn cần duyệt nghỉ. Lịch chưa thay đổi.” Nếu Bình từ chối, hết hạn hoặc không đủ điều kiện, yêu cầu chưa hoàn tất và xử lý theo ngoại lệ của luồng nhận thay.

Chi tiết đề xuất: ghi lịch sử chuyển nhánh và không dùng phản hồi chấp nhận nghỉ đến muộn để phát thêm lượt tìm người cho yêu cầu đã chuyển sang nhận thay. Quy tắc chuyển nhánh khi đã bắt đầu mời đồng thời hoặc đang giữ vị trí/ghi lịch chưa được chốt bởi quyết định này.

### 3.2.1. Tìm người nhận sau chấp nhận

**Đã chốt:** nhắn đồng thời tất cả labcoach hợp lệ không trùng lịch; người đủ điều kiện nhận sớm nhất được nhận và người sau không được nhận cùng vị trí. **Chi tiết thực hiện đề xuất:**

- Chấp nhận gắn với đúng yêu cầu, ca và phân công. Nếu nội dung ca/người đang phụ trách thay đổi, đề xuất dừng vòng tìm và đưa nội dung mới cho vận hành đối chiếu/chấp nhận lại.
- Ứng viên là labcoach đang hoạt động, có liên kết Zalo đã xác thực, không phải người xin nghỉ, chưa có phân công trùng lịch chương trình. J không phải bằng chứng họ còn rảnh; từng người vẫn phải tự xác nhận lịch bận khác khi nhận lời mời. Không xét năng lực chuyên môn vì MVP đã chốt không dùng điều kiện này.
- Bot tạo một lượt tìm và phát lời mời đồng thời cho danh sách ứng viên hợp lệ, theo dõi trạng thái/hạn riêng của từng lời mời.
- Lời mời nêu mã, ca/giờ/phòng, hạn phản hồi và hỏi đồng ý nhận ca cùng xác nhận không có lịch bận khác. Không chia sẻ lý do nghỉ hoặc nội dung riêng của người gửi cho ứng viên.
- Đề xuất “người nhận sớm nhất” là người có phản hồi đầy đủ đồng ý nhận ca và không có lịch bận khác được hệ thống ghi nhận sớm nhất, rồi vượt qua kiểm tra tài khoản/lời mời/lịch mới nhất. Chỉ nói “đồng ý” mà thiếu xác nhận lịch bận khác thì hỏi bổ sung; chưa được giữ vị trí. Phản hồi trùng cùng sự kiện không tạo lần nhận mới.
- Các phản hồi đủ thông tin được xử lý theo thứ tự ghi nhận có lưu bằng chứng. Nếu cùng mốc thời gian, dùng thứ tự sự kiện được hệ thống lưu để phân định ổn định. Ứng viên không còn đủ điều kiện không được giữ vị trí và được báo chưa nhận thành công.
- Khi phản hồi đầu tiên đủ điều kiện được xử lý, giữ vị trí cho đúng một người trước khi ghi Sheets. Việc giữ vị trí phải bảo đảm chỉ một người cho cùng phân công, kể cả hai phản hồi đến gần nhau. Các phản hồi sau nhận “Ca đang được xử lý cho người khác; bạn chưa được nhận ca này”, không ghi đè hoặc báo đã nhận thành công.
- Sau khi giữ vị trí, đọc lại và cập nhật lịch; chỉ báo nhận ca thành công cho người đã được ghi đúng lên lịch. Nếu ghi lỗi hoặc kết quả chưa rõ, vẫn giữ vị trí và chuyển đối chiếu/xử lý lỗi, không giao cho người sau trong lúc chưa biết kết quả. Việc mở lại tìm người chỉ thực hiện sau xử lý rõ người đang giữ vị trí và vô hiệu lời mời cũ; quy trình can thiệp này là đề xuất cho vận hành.
- Khi hoàn tất, vô hiệu các lời mời còn mở và thông báo ca đã có người nhận cho những người đã được mời. Khi hủy/rút chấp nhận trước ghi, dừng lượt tìm và vô hiệu lời mời; nếu đã ghi hoặc chưa rõ kết quả thì đối chiếu trước xử lý.
- Không có ứng viên, mọi lời mời đều từ chối/hết hạn hoặc đã tới lúc ca bắt đầu mà chưa có người: giữ yêu cầu chưa hoàn tất và báo vận hành; không tự phát lại lượt mời. 24 giờ là hạn từng lời mời, không phải hạn mặc định của toàn bộ yêu cầu.

Vận hành chấp nhận nghỉ chỉ mở bước tìm người, không tự xóa tên ở D hoặc đồng nghĩa đã bố trí đủ ca. Mẫu phản hồi: “YC-000123 đã được vận hành chấp nhận; đang tìm người nhận ca [thông tin]. Lịch chưa được thay đổi.”

Mẫu trả lời khi đang giữ vị trí: “Bạn là người xác nhận đầy đủ đầu tiên đủ điều kiện. Bot đang cập nhật lịch, sẽ báo kết quả sau khi kiểm tra.” Mẫu cho người trả lời sau khi đã hoàn tất: “Ca của YC-000123 đã có người nhận; bạn không được phân công ca này.” Tránh báo “đã có người nhận thành công” khi Sheets chưa được xác minh.

### 3.3. Hoán đổi hai ca

**Phạm vi đã chốt:** tự động hỗ trợ hoán đổi hai ca. **Chi tiết luồng đề xuất:**

1. An báo muốn đổi phân công A của mình lấy phân công B của Bình. Bot xác định chính xác hai ca và hai phân công; hỏi lại nếu thiếu hoặc có nhiều lựa chọn.
2. Kiểm tra An đang phụ trách A, Bình đang phụ trách B, cả hai là labcoach hợp lệ, hai phân công khác nhau và chưa có yêu cầu đang mở xung đột. Một lớp có nhiều labcoach thì chọn đúng vị trí của An/Bình, giữ các vị trí còn lại.
3. Bot trình bày đầy đủ: “An chuyển ca A cho Bình; Bình chuyển ca B cho An”, kèm lớp, ngày/giờ, cơ sở/phòng của cả hai ca. An xác nhận rõ đồng ý giao A, nhận B và không có lịch bận khác trong khoảng ca B nhận về. Lưu một mã yêu cầu chung và hai dòng phân công liên quan.
4. Bot gửi trực tiếp cho Bình cùng nội dung hai ca, yêu cầu xác nhận giao B, nhận A và không có lịch bận khác trong khoảng ca A nhận về. Xác nhận đầy đủ của An ở bước 3 là xác nhận trực tiếp của An; không cần mời lại trừ khi nội dung đổi thay đổi. Thiếu xác nhận lịch bận khác của một trong hai người thì hỏi bổ sung, chưa thực hiện hoán đổi.
5. Sau khi Bình đồng ý, đọc lại thông tin hai ca và lịch của cả hai. Bot tính thử lịch sau khi đổi: An phụ trách ca B thay cho ca A, Bình phụ trách ca A thay cho ca B. Sau đó kiểm tra ca nhận về của mỗi người có trùng với các ca khác mà người đó vẫn phụ trách hay không. Đây chỉ là bước kiểm tra; chưa sửa lịch trên Sheets.
6. Nếu có xung đột, xác nhận hết hiệu lực, phân công gốc thay đổi hoặc nội dung ca đã đổi, giữ yêu cầu chưa hoàn tất và hỏi lại/chuyển vận hành theo lý do. Không tự đổi riêng một ca.
7. Khi đủ điều kiện, chuyển một yêu cầu chung sang đang cập nhật lịch và thực hiện cả hai thay đổi. Kiểm tra kết quả: A thuộc Bình và B thuộc An, thông tin ca cùng các phân công khác vẫn đúng.
8. Chỉ chuyển hoàn tất khi cả hai phân công đã phản ánh đúng trên lịch chính thức. Gửi một kết quả chung cho An, Bình và vận hành, thể hiện rõ ca mỗi người nhận sau đổi.

Một người từ chối thì toàn bộ hoán đổi chưa được thực hiện. Đề xuất quyền hủy thuộc người gửi hoặc vận hành theo phần 4; người còn lại có thể từ chối lời mời của mình. Nếu sửa bất kỳ ca/người nào trong đề nghị, vô hiệu xác nhận cũ của cả hai và lấy xác nhận lại cho nội dung mới.

Nếu chỉ cập nhật thành công một phân công hoặc chưa biết kết quả, giữ đang cập nhật với lý do cần đối chiếu, cảnh báo vận hành ngay và theo dõi cả hai phân công. Không báo hoàn tất, tự coi hủy là hoàn nguyên hoặc thử lại mà chưa đọc kết quả thực tế. Thiết kế kỹ thuật phải quy định cách phục hồi hoặc hoàn nguyên có kiểm tra; chỉ bật tự động hoán đổi khi bảo đảm xử lý được trường hợp này.

**Nhiều hơn hai ca:** phạm vi chưa chốt. Đề xuất ghi nhận đủ các ca và chuyển vận hành; không tự tách một yêu cầu thành nhiều thay đổi độc lập.

### 3.4. Báo issue phòng học

1. Người gửi: “Wi-Fi H209 yếu.”
2. Bot hỏi các thông tin còn thiếu: cơ sở/phòng nếu chưa rõ, mô tả, thời điểm phát hiện; ảnh là tùy chọn. Không chặn ghi nhận vì thiếu ảnh.
3. Bot tóm tắt để người gửi xác nhận, lưu issue và cấp mã, ví dụ IS-000045.
4. Vận hành nhận thông báo, phân công người phụ trách và cập nhật tiến độ trên Sheets.
5. Khi vận hành ghi đã giải quyết cùng kết quả xử lý, bot cập nhật trạng thái và thông báo người gửi.

**Đề xuất về phản ánh trùng:** cùng phòng không đủ để kết luận cùng sự cố. Bot chỉ gợi ý các issue đang mở có cùng hiện tượng để người gửi chọn. Nếu chưa rõ, ghi issue riêng; vận hành có thể liên kết bằng mã sự cố chung, giữ nguyên mã theo dõi và người gửi của từng phản ánh.

Việc liên kết không tự đóng các phản ánh. Khi vận hành xác nhận kết quả cho sự cố chung, cần ghi nhận sự chuyển trạng thái cho từng issue liên quan và thông báo từng người gửi.

### 3.5. Tra cứu, bổ sung và hủy

- “Các yêu cầu đang chờ của tôi”: trả danh sách mã, loại, ca/phòng, trạng thái và người/bên đang chờ; không trả dữ liệu của người khác.
- “YC-000123 đến đâu rồi?”: trả trạng thái đã ghi nhận, thời điểm cập nhật gần nhất và bước còn lại. Không suy diễn hoàn tất từ câu “Lan đồng ý”.
- “Issue H209 xử lý chưa?”: nếu có nhiều issue của người gửi, cho chọn mã hoặc hiện tượng.
- “Đổi người thay sang Minh”: đề xuất vô hiệu lời mời cũ, lấy xác nhận mới; phản hồi cũ của Lan không còn hiệu lực.
- “Hủy YC-000123”: nhắc lại đúng yêu cầu và xin xác nhận hủy theo các điều kiện ở phần 4. Không tự hủy yêu cầu khác chỉ vì nội dung tương tự.

## 4. Trạng thái và điều kiện chuyển

Các tên trạng thái nghiệp vụ chính kế thừa MVP. Mã máy và các nhánh dưới đây là đề xuất. Mỗi chuyển trạng thái lưu ai thực hiện, thời điểm, trạng thái trước/sau và lý do.

### 4.1. Thay đổi lịch

| Mã đề xuất | Trạng thái hiển thị | Điều kiện vào / bước tiếp theo |
| --- | --- | --- |
| NEEDS_INFO | Cần bổ sung thông tin | Thiếu hoặc chưa xác định được ca/người; bổ sung xong quay lại bước phù hợp |
| AWAITING_SUBSTITUTE | Chờ người thay xác nhận | Đã lưu yêu cầu nhận thay hoặc hoán đổi, xác định đúng các bên và ca; chờ đủ xác nhận trực tiếp |
| RECORDED | Đã ghi nhận | Đã lưu yêu cầu nghỉ chưa có người thay hoặc yêu cầu cần vận hành xử lý |
| AWAITING_OPS_APPROVAL | Chờ vận hành chấp nhận | Yêu cầu nghỉ chưa có người thay đang chờ chấp nhận; chưa phát lời mời tìm người. Người gửi bổ sung người thay thì báo vận hành và chuyển AWAITING_SUBSTITUTE, không cần duyệt nghỉ |
| SEARCHING_SUBSTITUTE | Đang tìm người nhận ca | Yêu cầu nghỉ đã được chấp nhận và chưa có người nhận đủ điều kiện; từng lời mời được theo dõi riêng |
| SUBSTITUTE_RESERVED | Đã giữ vị trí cho người nhận | Một người xác nhận đầy đủ và đủ điều kiện đầu tiên đã được giữ vị trí; chặn người sau, chưa báo hoàn tất |
| AWAITING_OPS | Chờ vận hành bố trí/xử lý | Vận hành cần bố trí, xử lý xung đột hoặc ngoại lệ; lý do chờ ghi riêng |
| UPDATING_SCHEDULE | Đang cập nhật lịch | Đủ xác nhận nhận ca và không có lịch bận khác, tài khoản đã xác thực còn hợp lệ, lịch chương trình sau thay đổi không xung đột và các phân công gốc vẫn phù hợp; giữ trạng thái này nếu cập nhật một phần cần phục hồi |
| COMPLETED | Hoàn tất / Đã bố trí và cập nhật lịch | Đã kiểm tra lịch chính thức phản ánh đúng toàn bộ kết quả; hoán đổi phải đúng cả hai phân công; lưu thời điểm và phân công sau thay đổi |
| CANCELLED | Đã hủy | Hủy hợp lệ trước khi thực hiện thay đổi; lưu người và lý do hủy |

Đề xuất ghi `waiting_reason` riêng cho từ chối, hết hạn xác nhận, trùng lịch hoặc lỗi cập nhật, tránh coi các lý do này là đã hoàn tất. Không chuyển sang `CANCELLED` chỉ vì người thay từ chối; thông báo người gửi để chọn người khác, chuyển vận hành hoặc hủy.

**Quyền hủy đề xuất:** người gửi được hủy yêu cầu của mình trước bước cập nhật; vận hành được hủy yêu cầu đang mở và ghi lý do. Khi đang cập nhật hoặc chưa biết kết quả ghi, phải kiểm tra kết quả trước khi xử lý hủy. Sau hoàn tất, tạo yêu cầu thay đổi mới dựa trên lịch hiện tại; hủy không tự hoàn nguyên lịch.

**Thời hạn đã chốt:** `expires_at = min(invited_at + 24 giờ, starts_at)`. Hoán đổi dùng thời điểm bắt đầu sớm hơn của hai ca. Đề xuất `invited_at` là thời điểm phát hành lời mời; ghi rõ hạn cho người nhận. Tại hoặc sau hạn, phản hồi không có hiệu lực sửa lịch; phải đối chiếu và phát lời mời mới nếu vẫn còn đủ thời gian/điều kiện. Hết hạn không tự đổi lịch hoặc tự hủy yêu cầu.

Ví dụ: mời lúc 10:00 ngày 12/10 cho ca sáng 09:00 ngày 13/10 thì hạn là 09:00 ngày 13/10; mời cùng thời điểm cho ca chiều 14:00 ngày 13/10 thì hạn là 10:00 ngày 13/10. Hoán đổi một ca sáng và một ca chiều ngày 13/10 dùng mốc ca sáng 09:00. Múi giờ theo quy ước vận hành của đặc tả.

Với tìm người, mời đồng thời và áp dụng hạn cho từng lời mời theo quy tắc trên; không có bước chờ để chuyển ứng viên. Khi một người được giữ vị trí, các phản hồi sau không thể nhận cùng vị trí dù lời mời của họ chưa tới hạn. Không mặc định toàn yêu cầu tìm người hết hạn sau 24 giờ. Khi ca bắt đầu mà chưa có người, dừng tự động và báo vận hành.

### 4.2. Issue

| Mã đề xuất | Trạng thái | Điều kiện |
| --- | --- | --- |
| NEEDS_INFO | Cần bổ sung thông tin | Thiếu phòng/vị trí hoặc mô tả để xác định vấn đề |
| RECORDED | Đã ghi nhận | Issue đã lưu và có mã theo dõi |
| IN_PROGRESS | Đang xử lý | Vận hành xác nhận đang xử lý; đề xuất ghi người phụ trách |
| RESOLVED | Đã giải quyết | Vận hành xác nhận kết quả; đề xuất bắt buộc ghi mô tả kết quả |
| CANCELLED | Đã hủy | Báo nhầm hoặc yêu cầu hủy hợp lệ, có lý do; không dùng cho issue trùng còn cần xử lý |

Đề xuất cho phép chuyển thẳng đã ghi nhận → đã giải quyết nếu vận hành xử lý ngay và ghi kết quả. Nếu sự cố xuất hiện lại, tạo phản ánh mới liên kết issue trước để giữ lịch sử; quy tắc mở lại còn cần chốt.

### 4.3. Ba quy tắc đã nhận phản hồi

Các lựa chọn dưới đây đã được người phụ trách chốt; những chi tiết được đánh dấu đề xuất ở các mục khác vẫn cần rà soát:

| Nội dung | Quyết định đã chốt | Cách áp dụng |
| --- | --- | --- |
| Hạn lời mời | 24 giờ, tối đa đến lúc ca bắt đầu | Tính theo phần 4.1; hoán đổi dùng ca bắt đầu sớm hơn |
| Nghỉ chưa có người thay | Bot lấy xác nhận trực tiếp, nhắn đồng thời người hợp lệ không trùng lịch sau khi vận hành chấp nhận | Theo luồng 3.2; người đủ điều kiện nhận sớm nhất được giữ vị trí, người sau không được nhận |
| J sau đổi người | Giữ nguyên J; vận hành tự cập nhật | Bot chỉ sửa phân công D, lưu xác nhận riêng; không ghi Rảnh vào J từ xác nhận nhận ca |

Các trường hợp vận hành tự sửa lịch vẫn cần đối chiếu nguồn chính thức và quy tắc xử lý sửa đồng thời.

## 5. Mô hình dữ liệu để đối chiếu Google Sheets

Đây là tên logic đề xuất. Shifts/Assignments biểu diễn ca và vị trí đọc từ bảng lịch hiện tại, chưa phải quyết định tạo thêm lịch chính thức. Ánh xạ cột thực tế được trình bày trong tài liệu đối chiếu Sheets; các tab theo dõi khác là đề xuất bổ sung. Không dùng số dòng làm mã ổn định vì vận hành có thể sắp xếp/chèn dòng.

| Tab logic đề xuất | Mỗi dòng đại diện cho | Trường chính |
| --- | --- | --- |
| People | Một người được phép sử dụng | person_id, display_name, role, active, zalo_user_id, linked_by, linked_at |
| Shifts | Một ca học | shift_id, class_id, site, room, starts_at, ends_at, shift_status |
| Assignments | Một vị trí phân công trong ca | assignment_id, shift_id, coach_id, revision, updated_at, updated_by |
| ScheduleRequests | Một yêu cầu thay đổi lịch | request_id, requester_id, request_kind, status, waiting_reason, ops_decision, accepted_by, accepted_at, accepted_details, search_state, selected_coach_id, selected_confirmation_id, reserved_at, created_at, updated_at, result_note |
| RequestAssignments | Một phân công liên quan đến yêu cầu | request_id, assignment_id, original_coach_id, proposed_coach_id, expected_revision, confirmed_details |
| Confirmations | Một xác nhận trực tiếp của một bên, gồm xác nhận gửi yêu cầu và phản hồi lời mời | confirmation_id, request_id, recipient_id, confirmation_role, invitation_version, confirmed_details, invited_at, response, external_availability_confirmed, responded_at, valid_until |
| Issues | Một phản ánh của một người gửi | issue_id, reporter_id, site, room, description, observed_at, attachment_refs, status, owner_id, incident_id, resolution_note, resolved_by, resolved_at, created_at, updated_at |
| ActivityLog | Một thay đổi hoặc kết quả thao tác | event_id, entity_type, entity_id, actor_id, occurred_at, from_status, to_status, event_type, details |

Tách ca và phân công để xử lý lớp có nhiều labcoach: nhận thay một người không ghi đè các người còn lại. Nếu lịch hiện có chỉ có một người mỗi ca, vẫn cần mã phân công ổn định hoặc quy tắc ánh xạ tương đương. `request_kind` đề xuất gồm nhận thay, nghỉ chưa có người thay và hoán đổi hai ca. Hoán đổi có hai dòng `RequestAssignments`, cùng mã yêu cầu: An → Bình tại A và Bình → An tại B; có xác nhận trực tiếp của cả An và Bình cho cùng phiên bản đề nghị.

`confirmed_details` lưu nội dung đã xác nhận, gồm ngày/giờ, địa điểm, lớp và người gốc; hoán đổi lưu cả hai ca cùng chiều giao/nhận. Nếu các chi tiết này thay đổi, xác nhận cũ không đủ để thực hiện phiên bản mới.

`external_availability_confirmed` đề xuất ghi xác nhận không có lịch bận khác cho đúng khoảng ca nhận và phiên bản nội dung; không lưu chi tiết lịch cá nhân. Xác nhận từ người gửi rằng người thay rảnh không thay thế xác nhận trực tiếp của người nhận. Với hoán đổi, phải có xác nhận tương ứng của cả hai bên.

`accepted_details` đề xuất lưu nội dung ca/phân công được vận hành chấp nhận cho yêu cầu nghỉ. Mỗi lời mời tìm người có người nhận, phiên bản, trạng thái và `valid_until` riêng trong Confirmations; không dùng một hạn 24 giờ ở cấp ScheduleRequests để thay hạn từng lời mời. `selected_coach_id` chưa phải bằng chứng hoàn tất cho đến khi đối chiếu lịch đúng.

`selected_confirmation_id` và `reserved_at` đề xuất lưu phản hồi đủ điều kiện được chọn cùng thời điểm giữ vị trí. Lịch sử sự kiện cần lưu thứ tự phản hồi đầy đủ, kết quả kiểm tra và kết quả giữ vị trí để giải thích ai được nhận trước. Giữ vị trí phải được kiểm soát theo phân công, không chỉ theo một bản ghi yêu cầu, để ngăn hai yêu cầu khác nhau cùng giao một vị trí.

`revision` biểu diễn phiên bản phân công theo logic, chưa chọn cách thực hiện. Việc sửa Sheets trực tiếp có thể không tăng trường này; vì vậy phải kiểm tra cả giá trị lịch hiện tại, không chỉ dựa trên số phiên bản.

Các bảng trên là mô hình nghiệp vụ, không phải quyết định mọi dữ liệu kỹ thuật đều nằm trong Sheets. Hệ thống cần theo dõi sự kiện tin nhắn đã xử lý, các thay đổi đang thực hiện và thông báo chờ gửi; vị trí lưu/cơ chế thực hiện sẽ chọn ở bước kỹ thuật.

### 5.1. Quy tắc dữ liệu đề xuất

- Mã người, ca, phân công, yêu cầu và issue là duy nhất, ổn định; quy tắc sinh mã còn cần chọn. YC-000123 và IS-000045 chỉ là ví dụ.
- Thời gian bắt đầu phải trước thời gian kết thúc; lưu ngày đầy đủ và múi giờ thống nhất.
- Người gửi yêu cầu thay ca phải đang phụ trách phân công đó; người thay phải là labcoach đang hoạt động và đã liên kết. Hoán đổi phải xác minh quyền phụ trách cả hai phân công và xác nhận cả hai bên.
- Loại yêu cầu, trạng thái và vai trò dùng danh sách giá trị cố định; nhập sai phải được báo để sửa.
- Khi hoàn tất thay ca: có phân công trước/sau, bằng chứng kiểm tra kết quả lịch và thời điểm hoàn tất; hoán đổi lưu kết quả cho cả hai phân công.
- Khi giải quyết issue: có người xác nhận và mô tả kết quả; không suy ra trạng thái từ màu ô hoặc ghi chú không rõ nghĩa.
- Không xóa bản ghi để biểu diễn hủy; giữ lịch sử và trạng thái hủy.

### 5.2. Cột vận hành cập nhật

Đề xuất vận hành cập nhật người thay đã bố trí/kết quả xử lý, người phụ trách issue và trạng thái issue bằng các cột đã thống nhất. Mã định danh, xác nhận của người thay và lịch sử thay đổi không sửa tùy ý.

**Đã chốt:** bot giữ nguyên cột J khi thay người ở D; vận hành tự cập nhật J. Xác nhận trực tiếp được lưu riêng trong yêu cầu. Nếu vận hành sửa J trong lúc bot cập nhật D, bot giữ giá trị mới do vận hành ghi, không ghi đè bằng bản J đã đọc trước đó.

Nếu vận hành nhập “Hoàn tất” nhưng lịch chưa đúng, bot giữ trạng thái xử lý gần nhất đã xác thực, ghi cảnh báo cho vận hành và không thông báo thành công. Nếu nhập “Đã giải quyết” mà thiếu thông tin bắt buộc đã thống nhất, báo vận hành bổ sung trước khi thông báo.

## 6. Trùng lịch và ngoại lệ

### 6.1. Kiểm tra trùng lịch — đề xuất

Hai khoảng giờ xung đột khi `bắt đầu A < kết thúc B` và `bắt đầu B < kết thúc A`. Hai ca nối tiếp đúng giờ không xung đột theo công thức này; khoảng đệm di chuyển giữa cơ sở còn cần chốt.

**Giờ ca đã chốt:** Sáng 09:00–13:00, Chiều 14:00–18:00 cho mọi lớp có lịch. Với lịch này, hai phân công cùng ngày/cùng buổi giao nhau; sáng và chiều không giao nhau về thời gian. Người đã có tên ở D trong một ca vẫn có phân công đó dù J ghi Bận/Chưa cập nhật; J không được dùng để bỏ qua ca khi kiểm tra. Khi hoán đổi, bot tính thử lịch mới của mỗi người: thay ca giao đi bằng ca nhận về, giữ nguyên các ca khác, rồi kiểm tra trùng lịch.

**Đã chốt:** bot kiểm tra lịch chương trình và yêu cầu người nhận tự xác nhận không có lịch bận khác trong khoảng ca nhận. Hoán đổi áp dụng cho cả hai người tại ca nhận về.

**Cách thực hiện đề xuất:** kiểm tra toàn bộ phân công còn hiệu lực trong các bảng lịch chương trình được tích hợp, gồm lý thuyết và lab; hoán đổi kiểm tra lịch sau đổi như bước 3.3.5. Danh mục bảng/kỳ lịch cần chốt trước pilot để tránh chỉ kiểm tra một phần. Lịch ngoài chương trình dựa vào xác nhận trực tiếp cho đúng khoảng giờ, không cần thu thập nội dung lịch cá nhân. Thiếu xác nhận, câu trả lời chưa rõ hoặc người nhận nói đang bận thì yêu cầu chưa đủ điều kiện cập nhật. Nếu nội dung ca thay đổi, lấy lại xác nhận cho nội dung mới.

### 6.2. Tình huống và cách xử lý đề xuất

| Tình huống | Hành vi |
| --- | --- |
| Có nhiều ca/tên người phù hợp | Hỏi lựa chọn rõ ràng; chưa gửi lời mời hoặc sửa lịch |
| Không tìm thấy ca hoặc ca không thuộc người gửi | Hỏi lại thông tin; nếu vẫn không khớp, chuyển vận hành kiểm tra |
| Người thay trùng lịch | Giữ yêu cầu chưa hoàn tất, nêu ca xung đột cho người thay; người gửi nhận lý do chung và lựa chọn bước tiếp |
| Người nhận chỉ đồng ý nhưng chưa xác nhận lịch bận khác | Hỏi bổ sung cho đúng ca; chưa sửa lịch |
| Người nhận xác nhận có lịch bận ngoài chương trình | Chưa nhận ca; thông báo người gửi để chọn người khác hoặc chuyển vận hành |
| Tài khoản chưa liên kết hoặc đã mất hiệu lực | Hướng dẫn liên hệ vận hành; không chấp nhận xác nhận hoặc cung cấp lịch cá nhân |
| Người thay từ chối/không phản hồi | Thông báo người gửi; chờ chọn người khác, chuyển vận hành hoặc hủy theo quy tắc đã duyệt |
| Nghỉ chưa được vận hành chấp nhận và vẫn chưa có người thay | Giữ chờ chấp nhận; không phát lời mời tìm người hoặc sửa phân công |
| Người gửi bổ sung người thay khi đang chờ vận hành chấp nhận | Giữ mã, báo vận hành và chuyển sang nhận thay không cần duyệt nghỉ; chỉ sửa lịch sau xác nhận trực tiếp và kiểm tra đủ điều kiện |
| Nhiều người đồng ý nhận cùng vị trí | Giữ vị trí cho người xác nhận đầy đủ đầu tiên đủ điều kiện; chặn người sau ngay, chỉ báo hoàn tất sau kiểm tra Sheets |
| Ghi lịch lỗi sau khi giữ vị trí | Giữ người đã được chọn, đối chiếu/xử lý lỗi; không giao lại cho phản hồi sau khi kết quả chưa rõ |
| Một ứng viên từ chối trong lượt mời đồng thời | Lượt tìm tiếp tục với các lời mời còn hiệu lực; không tự hủy cả yêu cầu |
| Vận hành rút chấp nhận trước cập nhật | Đề xuất dừng vòng tìm, vô hiệu lời mời và báo các bên; nếu đang ghi/chưa rõ kết quả thì đối chiếu trước xử lý |
| Không có ứng viên hoặc mọi lời mời đều từ chối/hết hạn | Giữ chưa hoàn tất, báo vận hành xử lý; không tự phát lại lượt mời |
| Người gửi chọn lại người thay | Vô hiệu lời mời cũ, phát lời mời mới và kiểm tra lại toàn bộ điều kiện |
| Vận hành đổi giờ, phòng, lớp hoặc người phụ trách khi đang chờ | Dừng thay đổi dựa trên bản cũ; đọc lại, yêu cầu xác nhận mới nếu nội dung ca thay đổi |
| Hai vùng cột của lịch ghi phòng/key coach khác nhau | Dùng F/E thuộc B–J đã chốt làm chuẩn; ghi nhận sai khác vùng lặp, không chặn chỉ vì sai khác này |
| Có tên labcoach ở D nhưng J là Bận/Chưa cập nhật | D vẫn xác định phân công chính thức; không tự hủy ca hoặc bỏ qua ca đó khi kiểm tra trùng |
| Bảng chính thiếu ngày/buổi hoặc tên chưa đối chiếu được | Hỏi bổ sung/chuyển vận hành; không tự lấy vùng lặp làm nguồn thay thế |
| Hai yêu cầu cùng một phân công | Đề xuất một yêu cầu đang mở mỗi phân công; người gửi bổ sung vào yêu cầu đó. Trường hợp xung đột chuyển vận hành |
| Người thay đồng ý hai ca trùng nhau gần như đồng thời | Kiểm tra và thực hiện thay đổi theo thứ tự có kiểm soát; sau mỗi thay đổi, kiểm tra lại lịch trước thay đổi tiếp |
| Tin nhắn hoặc phản hồi xác nhận được nhận lại | Nhận diện cùng sự kiện; không tạo thêm yêu cầu, thực hiện đổi lịch hoặc phát thông báo trùng |
| Ghi lịch lỗi rõ ràng | Giữ chưa hoàn tất, lưu lỗi và báo vận hành; chỉ thử lại sau khi đọc lại lịch |
| Ghi lịch hết thời gian chờ, chưa biết đã thành công chưa | Đọc và đối chiếu lịch, xác định kết quả trước khi thử lại hoặc nhận yêu cầu hủy |
| Lịch đã đổi nhưng cập nhật bản theo dõi thất bại | Đối chiếu và đồng bộ bản theo dõi; không đổi lịch lần nữa hoặc tự hoàn nguyên |
| Cập nhật lịch thành công nhưng gửi tin lỗi | Giữ kết quả đúng, đánh dấu thông báo chưa gửi và gửi lại có kiểm soát |
| Ca đã bắt đầu/đã kết thúc | Đề xuất chuyển vận hành, không tự thay đổi phân công lịch sử |
| Người dùng gửi lại cùng nội dung | Gợi ý yêu cầu đang mở tương ứng và hỏi có muốn bổ sung; không gộp hai phản ánh khác nhau chỉ vì giống câu chữ |
| Hoán đổi hai ca | Tự xử lý khi đủ điều kiện ở luồng 3.3; hoàn tất chỉ khi cả hai phân công đúng |
| Hoán đổi chỉ cập nhật được một ca | Giữ đang cập nhật, cảnh báo vận hành và đối chiếu/phục hồi cả yêu cầu; không báo thành công hoặc tự xử lý như hai yêu cầu độc lập |
| Yêu cầu nhiều hơn hai ca | Đề xuất chuyển vận hành cho đến khi chốt phạm vi |

**Đã chốt:** vận hành và bot đều được cập nhật D trực tiếp. Bot đọc lại ngay trước khi ghi, kiểm tra ca/vị trí, phân công gốc, nội dung đã xác nhận và lịch liên quan của người nhận. Phát hiện thay đổi ảnh hưởng yêu cầu thì dừng ghi theo bản cũ, đối chiếu lại và thông báo; nếu đủ điều kiện thì ghi đúng D, giữ J và xác minh sau ghi.

Đọc trước/đọc sau chưa ngăn được sửa đồng thời giữa hai bước, cũng không bảo đảm phát hiện thay đổi của vận hành đã bị ghi đè. Thiết kế kỹ thuật phải kiểm chứng tình huống này và đề xuất cách phối hợp trước pilot; không mặc định cấm vận hành sửa trực tiếp hoặc tuyên bố đã tránh mọi xung đột. Khi phát hiện xung đột hay kết quả chưa rõ, giữ chưa hoàn tất, đối chiếu và báo vận hành; không tự ghi lại/hoàn nguyên theo bản cũ.

## 7. Thông báo và công việc tồn đọng

Các ví dụ nội dung gửi cho người tạo yêu cầu, vận hành và người nhận ca được lưu tại [Ví dụ tin nhắn MVP v1](MESSAGE_EXAMPLES_V1_DRAFT.md). Mẫu phân biệt rõ đã ghi nhận, chờ chấp nhận, đang tìm người, đang cập nhật và hoàn tất. Câu trả lời ngắn kèm mã và lệnh chấp nhận trong chat vẫn là đề xuất tương tác, chưa phải quyết định đã chốt.

**Đã chốt:** thông báo thay đổi trạng thái cho người gửi; thông báo vận hành và tổng hợp việc còn tồn đọng. Với nhận thay ca, thông báo kết quả cho các bên liên quan.

**Đề xuất:** thông báo gồm mã, ca/phòng, trạng thái, điều cần làm tiếp và thời điểm cập nhật. Tách kết quả nghiệp vụ khỏi kết quả gửi tin để lỗi gửi tin không biến thành hủy hoặc thực hiện lại đổi ca.

| Sự kiện | Người nhận đề xuất |
| --- | --- |
| Lời mời nhận thay/tìm người sau chấp nhận | Người nhận được xác định cho từng lời mời |
| Đã ghi nhận/chờ bổ sung | Người gửi |
| Người thay từ chối, hết hạn hoặc xung đột | Người gửi; vận hành khi cần xử lý |
| Yêu cầu nghỉ cần bố trí | Danh sách vận hành phụ trách |
| Người gửi bổ sung người thay khi đang chờ chấp nhận nghỉ | Vận hành nhận thông tin chuyển sang nhận thay; người được bổ sung nhận lời mời xác nhận trực tiếp |
| Yêu cầu nghỉ được chấp nhận/đang tìm người | Người gửi; vận hành theo dõi trong bảng yêu cầu |
| Ca đã có người hoặc vòng tìm bị dừng/hủy | Ứng viên còn lời mời mở; chỉ báo có người sau khi lịch đã cập nhật |
| Thay ca hoàn tất hoặc bị hủy sau khi đã gửi lời mời | Người gửi, người thay liên quan và vận hành |
| Issue mới/cần vận hành | Danh sách vận hành phụ trách |
| Issue chuyển trạng thái | Người gửi |
| Lỗi cập nhật hoặc dữ liệu không nhất quán | Vận hành |

Bản tổng hợp đề xuất gồm ca cần bố trí, lời mời chờ xác nhận, yêu cầu cần xử lý lỗi và issue chưa giải quyết; hiển thị thời gian tồn đọng và người phụ trách nếu có. Chưa chốt người nhận, giờ gửi, ngưỡng sát giờ học, nhắc lại hoặc cách đánh dấu khẩn. Không mặc định gửi vào nhóm vì kênh đã chốt là nhắn riêng với bot.

## 8. Kịch bản nghiệm thu nghiệp vụ đề xuất

Các kịch bản này dùng để rà soát đặc tả và sau đó thử pilot; chưa phải kết quả kiểm thử phần mềm.

| Kịch bản | Kết quả cần quan sát |
| --- | --- |
| Nhận thay ca với đúng người xác nhận, không trùng lịch | Lịch đổi đúng một phân công; yêu cầu hoàn tất; các bên nhận kết quả |
| Hoán đổi hai ca, cả hai xác nhận và lịch sau đổi không xung đột | Cả hai phân công đổi đúng; một mã yêu cầu hoàn tất; hai người và vận hành nhận kết quả |
| Hoán đổi có một người chưa đồng ý/từ chối | Không phân công nào bị thay đổi |
| Ca giao đi giao giờ với ca nhận về, nhưng không có ca khác xung đột sau đổi | Kiểm tra trên lịch sau đổi; không từ chối chỉ vì ca cũ sắp giao đi |
| Hoán đổi chỉ ghi được một phân công | Chưa hoàn tất; cảnh báo vận hành; đối chiếu/phục hồi không gây thay đổi lặp |
| Người gửi nói người thay đã đồng ý nhưng chưa có phản hồi trực tiếp | Lịch giữ nguyên; yêu cầu còn chờ xác nhận |
| Người nhận đồng ý nhưng chưa xác nhận không có lịch bận khác | Bot hỏi bổ sung; lịch chưa thay đổi |
| Hoán đổi đủ đồng ý nhưng thiếu xác nhận lịch bận khác của một người | Chưa cập nhật cả hai phân công |
| Người nhận xác nhận không bận ngoài chương trình nhưng có ca trùng trong lịch chương trình | Kiểm tra phát hiện xung đột; không hoàn tất |
| Tài khoản chưa được vận hành xác thực gửi yêu cầu/xác nhận | Không thực hiện thay ca; hướng dẫn liên hệ vận hành |
| Tài khoản bị thay hoặc vô hiệu khi lời mời còn chờ | Phản hồi từ tài khoản cũ không có hiệu lực sửa lịch |
| Người thay có ca giao nhau | Không đổi lịch; có lý do chờ xử lý |
| Người gửi có nhiều ca phù hợp | Bot hỏi chọn trước khi tạo lời mời có hiệu lực |
| Đọc bảng có ô gộp và dòng tiêu đề/ngăn cách | Xác định đúng nhóm ca và vị trí; không tạo ca từ tiêu đề hoặc điền tên vào ô Lab Coach trống |
| Phòng F156 là H210, N156 là H205 | Hội thoại và ca được kiểm tra dùng H210 theo nguồn chuẩn F; sai khác được ghi riêng |
| Người nhận đang được phân công ở D trong một lớp khác cùng sáng, J ghi Chưa cập nhật | Phát hiện trùng 09:00–13:00; không cho nhận thêm ca sáng đó |
| Người nhận có ca sáng và muốn nhận ca chiều cùng ngày | Không coi 09:00–13:00 và 14:00–18:00 là giao nhau; kiểm tra các điều kiện còn lại |
| Một lớp có hai labcoach, một người được thay | Phân công người còn lại được giữ đúng |
| Nghỉ chưa có người thay | Có mã theo dõi và thông báo vận hành; không nói ca đã đủ người |
| Nghỉ vẫn chưa có người thay, vận hành chưa chấp nhận | Không phát lời mời tìm người; D giữ nguyên |
| An bổ sung Bình nhận thay khi yêu cầu nghỉ đang chờ vận hành chấp nhận | Giữ cùng mã, báo vận hành, chuyển chờ Bình xác nhận mà không cần duyệt nghỉ; D giữ nguyên cho tới khi Bình xác nhận đầy đủ và vượt kiểm tra |
| Bình xác nhận đầy đủ và đủ điều kiện sau khi An bổ sung, vận hành chưa chấp nhận nghỉ | Bot cập nhật D, giữ nguyên J, đọc lại và báo hoàn tất theo luồng nhận thay |
| Bình từ chối hoặc có lịch trùng sau khi được bổ sung | Không đổi D; yêu cầu chưa hoàn tất, thông báo người gửi theo luồng nhận thay |
| Phản hồi chấp nhận nghỉ đến muộn sau khi yêu cầu đã chuyển sang nhận thay | Không phát lượt mời tìm người song song hoặc tạo yêu cầu thứ hai |
| Vận hành chấp nhận nghỉ, bot tìm được người đồng ý đủ điều kiện | D cập nhật đúng người nhận; J được bot giữ nguyên; các bên nhận kết quả |
| Vận hành đề cử người nhận nhưng người đó chưa xác nhận trực tiếp | Chưa sửa lịch và chưa hoàn tất |
| Hai ứng viên đồng ý gần nhau | Chỉ một người nhận đúng vị trí; không ghi đè hoặc báo cả hai đã nhận thành công |
| An xác nhận đầy đủ trước Bình, cả hai đủ điều kiện | An được giữ vị trí; Bình không được nhận ngay cả khi Sheets còn đang cập nhật |
| An trả lời đồng ý trước nhưng thiếu xác nhận lịch bận khác, Bình xác nhận đầy đủ | An chưa được giữ vị trí; Bình được xử lý nhận nếu đủ điều kiện |
| Người đầu tiên được giữ vị trí nhưng cập nhật Sheets trả kết quả không rõ | Người sau chưa được nhận; đối chiếu lịch trước xử lý tiếp |
| Một người từ chối, các lời mời khác còn hiệu lực | Vẫn chờ người khác nhận trong cùng lượt tìm |
| Lời mời lúc 10:00 ngày trước cho ca sáng 09:00 ngày sau | Hạn là 09:00 ngày ca diễn ra; phản hồi tại/sau hạn không có hiệu lực |
| Hoán đổi ca sáng/chiều cùng ngày, phản hồi đến sau 09:00 | Đã quá hạn theo ca sớm hơn; không tự đổi |
| Bot đổi D khi J đang là Chưa cập nhật/Bận | J không bị bot sửa thành Rảnh; xác nhận người nhận được lưu riêng |
| Vận hành sửa J trong lúc bot đổi D | Bot giữ thay đổi J của vận hành, không khôi phục giá trị cũ |
| Vận hành ghi đã bố trí nhưng chưa sửa lịch | Người gửi chưa nhận thông báo hoàn tất; vận hành nhận yêu cầu kiểm tra |
| Phản hồi lời mời cũ sau khi đã đổi người thay/hủy | Không thay đổi lịch |
| Hai thay đổi gần nhau có thể làm người thay trùng lịch | Chỉ thay đổi đáp ứng kiểm tra trên lịch mới nhất được thực hiện |
| Vận hành sửa phân công trong lúc bot đang xử lý | Không ghi đè im lặng; yêu cầu được đối chiếu lại hoặc chuyển vận hành |
| Vận hành đã đổi D trước lần kiểm tra cuối của bot | Bot phát hiện phân công gốc thay đổi; không ghi theo yêu cầu cũ, đối chiếu và thông báo |
| Vận hành sửa D giữa lần đọc cuối và lần ghi của bot | Kiểm chứng và ghi nhận giới hạn phát hiện/ghi đè; không coi đọc lại là khóa hoặc bảo đảm tuyệt đối. Nếu phát hiện bất nhất, dừng và đối chiếu, không tự ghi lại |
| Ghi lịch trả kết quả không rõ, sau đó sự kiện được gửi lại | Kiểm tra lịch và xác định kết quả; không thay đổi lần hai |
| Người khác tra cứu bằng mã đoán được | Không lộ nội dung yêu cầu ngoài quyền của họ |
| Issue không có ảnh | Vẫn tiếp nhận khi đủ phòng, mô tả và thời điểm |
| Issue chỉ có ghi chú “đang kiểm tra” | Chưa báo đã giải quyết |
| Hai phản ánh cùng phòng về hai vấn đề khác nhau | Không tự gộp |
| Gửi thông báo thất bại sau khi lịch đổi thành công | Yêu cầu vẫn hoàn tất; thông báo được theo dõi gửi lại |

## 9. Điểm cần chốt và bước sau bản nháp

| Ưu tiên | Nội dung cần đầu vào/quyết định | Ảnh hưởng |
| --- | --- | --- |
| Đã chốt đầu vào lịch | D là phân công, J phục vụ xếp ca và bot giữ nguyên J, B–J là chuẩn, giờ ca cố định | Còn chuẩn bị mã người/ca và ánh xạ ổn định |
| Đã chốt phạm vi; cần rà soát chi tiết | Tự động nhận thay một ca và hoán đổi hai ca | Hoàn thiện xác nhận hai bên, kiểm tra lịch sau đổi và xử lý cập nhật một phần |
| Đã chốt nguyên tắc định danh | Vận hành xác thực liên kết mã labcoach với tài khoản Zalo trước khi dùng | Còn chuẩn bị danh sách người dùng, vai trò vận hành và cách thu thập mã tài khoản |
| Đã chốt nguyên tắc kiểm tra lịch | Kiểm tra lịch chương trình và người nhận tự xác nhận không có lịch bận khác | Còn liệt kê nguồn/kỳ lịch chương trình đầy đủ và đệm di chuyển nếu có |
| Đã chốt hạn lời mời | 24 giờ, tối đa đến lúc ca bắt đầu; hoán đổi lấy ca sớm hơn | Còn rà soát quyền hủy và nhắc việc sát giờ |
| Đã chốt tìm người và thứ tự nhận | Sau chấp nhận, mời đồng thời người hợp lệ không trùng lịch; người đủ điều kiện nhận sớm nhất được nhận, người sau không nhận cùng vị trí | Cụ thể hóa giữ vị trí, xử lý sự kiện trùng/sửa đồng thời và can thiệp khi lỗi |
| Trước khi pilot | Người nhận, giờ tổng hợp và quy tắc việc khẩn | Chốt thông báo |
| Trước khi pilot | Liên kết issue trùng, mở lại issue và kết quả giải quyết bắt buộc | Chốt vòng đời issue |
| Đã chốt kênh tiếp nhận | Chuyển yêu cầu thông thường sang bot từ pilot; vận hành hỗ trợ khi bot lỗi hoặc có việc khẩn | Còn chuẩn bị thông báo chuyển kênh, đối chiếu yêu cầu cũ và hướng dẫn hỗ trợ |
| Trước khi triển khai | Hermes Agent đã được chọn; kiểm tra nền tảng Zalo, chốt kiến trúc dịch vụ nghiệp vụ/tích hợp, nơi lưu dữ liệu và xử lý sửa đồng thời | Thiết kế kỹ thuật dựa trên nghiệp vụ đã duyệt |
| Trước khi pilot | Mục tiêu và cách đo: yêu cầu bị bỏ sót, thời gian xử lý, tỷ lệ dùng bot, lượng tin gửi | Đánh giá hiệu quả và hạn mức |

Trình tự hiện tại: bản thử cục bộ đã được xây theo quyết định được duyệt → người phụ trách nghiệm thu qua Paseo → hoàn thiện danh tính, phạm vi nguồn lịch và kết nối nền tảng → nghiệm thu và mở pilot. Hạn 24 giờ, xác nhận trực tiếp, bot giữ nguyên J, mời đồng thời và người nhận đủ điều kiện sớm nhất đã chốt; không đặt lại thành câu hỏi mở. Việc cho phép xây bản thử chưa đồng nghĩa đã nghiệm thu pilot hoặc cấp quyền ghi Sheets nguồn.
