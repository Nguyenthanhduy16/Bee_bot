# Bee Bot — Đối chiếu Google Sheets lịch hiện tại

- **Ngày đọc:** 10/10/2026.
- **Nguồn:** [Google Sheets “Lịch lab” do người phụ trách cung cấp](https://docs.google.com/spreadsheets/d/1t2Gqji-T5-4ILiJCGCf4kVmQCurKXzk_3jJfOp6AJnI/edit?usp=sharing).
- **Cách đọc:** bản xuất XLSX chỉ đọc; kiểm tra cấu trúc workbook, ô dữ liệu, ô gộp và danh sách giá trị trạng thái. Không sửa Sheets nguồn.
- **Trạng thái:** đã quan sát cấu trúc và được người phụ trách xác nhận ý nghĩa D/J, giờ ca, nguồn chuẩn B–J; cách định danh và ghi dữ liệu là đề xuất đang rà soát.
- **Liên quan:** [Đặc tả hội thoại và dữ liệu](WORKFLOW_SPEC_V1_DRAFT.md).

Đây là ảnh chụp dữ liệu tại lúc đọc, không phải kết nối đồng bộ đang hoạt động. Không lưu danh sách tên người hoặc link nhóm Zalo vào tài liệu này.

**Đã chốt khi tiếp tục:** D là người được phân công chính thức nếu chưa có thay đổi; J là thông tin bận/rảnh phục vụ xếp ca. Ca sáng 09:00–13:00, chiều 14:00–18:00 áp dụng cho tất cả lớp có lịch. Vùng bảng chính B–J là chuẩn khi khác vùng thông tin lặp K–P.

## 1. Những gì đã quan sát được

Workbook xuất ra có một tab: **Lịch lab 0210-1610**. Tiêu đề ghi lịch Lab Coach K4, khoảng 02/10–16/10/2026; phần nội dung ghi giai đoạn 2, các Track 1, 2, 3A, 3B, 4.

Bảng chia thành từng khối ngày, lặp lại dòng tiêu đề và đặt nhiều labcoach dưới cùng một lớp/buổi. Nhiều ô khóa/session/phòng/buổi/key coach được gộp theo khối. Vì vậy ô trống bên dưới một ô gộp không có nghĩa ca thiếu phòng hoặc buổi; ngược lại, ô trống cột Lab Coach không được tự điền tên từ dòng trước.

| Cột | Tiêu đề/nội dung quan sát | Ý nghĩa đối với thiết kế |
| --- | --- | --- |
| A | STT; đồng thời chứa tiêu đề và ngày ở các dòng khác | STT khởi động lại theo ngày, không phải mã ca/phân công |
| B | Khóa, giá trị như Track 1/Track 3B | Nhận diện track; có ô gộp |
| C | Session, giá trị CS1–CS13 | Session lặp ở các track, không duy nhất toàn bảng |
| D | Lab Coach | Tên người được phân công chính thức; ô trống không được tự điền tên dòng trước |
| E | Key Coach | Có ô gộp; không tự coi là Lab Coach nhận thay |
| F | Phòng | Có ô gộp; có trường hợp khác cột N |
| G | Buổi: Sáng/Chiều | Có ô gộp; không có giờ bắt đầu/kết thúc cụ thể ở trường này |
| H | Sức chứa phòng | Thuộc thông tin phòng/lớp, không phải số vị trí labcoach bắt buộc |
| I | Video / Ghi chú ở một số dòng tiêu đề | Không dùng làm trạng thái yêu cầu; không thấy nội dung trong các dòng có STT đã kiểm tra |
| J | Trạng thái | Rảnh, Bận, Chưa cập nhật hoặc trống; thông tin khả dụng phục vụ xếp ca |
| K | Ngày, dạng dd/mm/yyyy trên các dòng dữ liệu | Thông tin ngày lặp; đối chiếu với tiêu đề khối ngày ở A |
| L | Khóa | Thông tin track lặp lại trên từng dòng |
| M | Session | Thông tin session lặp lại trên từng dòng |
| N | Phòng | Thông tin phòng lặp lại trên từng dòng; có trường hợp khác F |
| O | Buổi | Thông tin Sáng/Chiều lặp lại trên từng dòng |
| P | Key Coach | Thông tin key coach lặp lại; có trường hợp khác E |
| Q | Link join Zalo ở nhiều khối | Link nhóm; không phải mã tài khoản Zalo để bot nhắn riêng |
| R–S | Hướng dẫn/chú thích ở vùng đầu bảng | Không coi là dữ liệu ca |

Có 390 dòng mang STT số; 346 ô D trong những dòng này có tên. Theo ý nghĩa D vừa được xác nhận, đây là 346 lượt phân công có tên trong ảnh dữ liệu đã đọc, chưa phải số người dùng duy nhất. Các dòng mang STT có đủ K–O; những cột này dùng để đối chiếu, không thay thế nguồn chuẩn của bảng chính.

Khối ngày 10/10 và 11/10 có tiêu đề nhưng không có dòng mang STT số trong bản đọc. Không kết luận “không có lịch” chỉ từ điều này; cần biết lịch ngày đó thực sự nghỉ hay chưa được điền.

## 2. Quy tắc nguồn lịch đã xác nhận

### 2.1. Tên labcoach và trạng thái rảnh/bận

**Đã chốt:** người ở D là phân công chính thức nếu chưa có thay đổi; J phục vụ xếp ca theo bận/rảnh.

**Cách áp dụng đề xuất:** lấy D để xác định phân công hiện tại và quyền yêu cầu thay đổi. J không thay thế xác nhận nhận ca, không phải trạng thái YC/issue, và không tự hủy phân công khi ghi Bận hoặc Chưa cập nhật. Kiểm tra trùng lịch dựa trên các phân công chính thức ở D trên phạm vi lịch được tích hợp, không dựa riêng vào nhãn Rảnh.

Ô D trống là vị trí chưa có tên, không tự suy ra đó là yêu cầu nghỉ. Số labcoach bắt buộc mỗi lớp và quy tắc khi thay tên ở D thì ghi gì vào J vẫn cần rà soát; không lấy số dòng trống hoặc sức chứa phòng làm số người cần bố trí.

### 2.2. Hai vùng thông tin chưa nhất quán

Ví dụ quan sát: F156 là **H210**, N156 là **H205**; F362 là **H210**, N362 là **H205**. Một số ô Key Coach E/P cũng khác nhau sau khi bỏ khoảng trắng ở hai đầu.

**Đã chốt:** vùng B–J là chuẩn. Vì vậy các ví dụ trên dùng phòng H210 từ F; Key Coach lấy E thay vì P. Khóa, session và buổi lần lượt lấy B, C, G, có giải giá trị ô gộp trong đúng phạm vi.

**Đề xuất:** ghi nhận sai khác với K–P để vận hành biết, nhưng không chặn yêu cầu chỉ vì vùng lặp khác nguồn chuẩn đã rõ. Nếu bảng chính thiếu thông tin, có tên không xác định được hoặc nội dung trong bảng chính không nhất quán, hỏi/chuyển vận hành; không tự lấy vùng lặp để bù vào nguồn chuẩn.

### 2.3. Giờ ca đã chốt; mã ổn định còn cần chọn

**Đã chốt:** tất cả lớp có lịch áp dụng buổi Sáng 09:00–13:00 và Chiều 14:00–18:00. Lấy ngày đầy đủ từ tiêu đề khối ngày ở A, kết hợp buổi ở G để tạo khoảng giờ của ca. Đề xuất thống nhất múi giờ Asia/Ho_Chi_Minh như trong đặc tả; chưa coi đây là một quyết định được người phụ trách xác nhận riêng.

Hai ca cùng ngày và cùng buổi có giờ giao nhau; sáng và chiều không giao nhau theo giờ đã chốt. Hoán đổi kiểm tra trên lịch sau đổi. **Đã chốt:** bot kiểm tra lịch chương trình, người nhận tự xác nhận không có lịch bận khác trong ca nhận; còn cần liệt kê đủ các bảng/kỳ lịch chương trình được tích hợp.

Không thấy cột mã người, mã ca hoặc mã vị trí phân công chuyên biệt. STT lặp lại và tọa độ dòng có thể đổi khi chèn/sắp xếp, nên không đủ làm định danh lâu dài. Cách bổ sung mã vào Sheets hoặc duy trì ánh xạ riêng còn cần chọn; chưa chỉnh bảng nguồn.

## 3. Ánh xạ đọc/ghi đề xuất dựa trên nguồn đã chốt

| Trường logic | Nguồn | Cách áp dụng |
| --- | --- | --- |
| schedule_source | Spreadsheet + tab/kỳ lịch | Xác nhận cách có kỳ lịch mới và phạm vi các bảng lịch khác |
| cohort/phase | Tiêu đề K4/giai đoạn 2 | Vận hành xác nhận định nghĩa, không chỉ suy ra từ màu ô |
| shift_id | Mã ổn định được bổ sung/ánh xạ | Không dùng mỗi Session hay STT làm khóa |
| shift_date | Tiêu đề khối ngày ở A | K chỉ dùng đối chiếu; thiếu/không rõ ngày trong tiêu đề thì hỏi lại |
| track/session | B/C đã giải ô gộp | L/M chỉ dùng đối chiếu |
| room | F đã giải ô gộp | Lấy F khi khác N |
| daypart | G đã giải ô gộp | Lấy G khi khác O; chỉ chấp nhận Sáng/Chiều đã xác định |
| starts_at/ends_at | Ngày + buổi G | Sáng 09:00–13:00; chiều 14:00–18:00 |
| key_coach | E đã giải ô gộp | Lấy E khi khác P; chưa mở luồng thay Key Coach |
| assignment_id | Mã vị trí trong một ca | Một lớp có nhiều vị trí, kể cả vị trí chưa có người nếu vận hành xác nhận |
| coach_id | D + danh sách mã labcoach và liên kết Zalo đã được vận hành xác thực | Đối chiếu tên với mã người; không tự gộp người trùng tên |
| assigned_coach | D | Nguồn phân công hiện tại; đọc lại trước khi thay đổi |
| availability_hint | J | Thông tin xếp ca; không dùng làm trạng thái yêu cầu hoặc bằng chứng nhận thay |
| source_locator | Tab + ô/dòng lúc đọc | Dùng để đối chiếu; đọc lại và kiểm tra mã/nội dung trước ghi |

Nhóm ca ứng viên có thể dựa trên kỳ lịch, ngày, track, session, phòng và buổi; cần xác nhận trường hợp một nhóm này vẫn có nhiều lớp. Khóa nhận diện ứng viên có thể thay đổi khi phòng/buổi đổi, nên không thay thế mã ca ổn định.

### 3.1. Nhận thay một ca

Xác định đúng dòng D đang ghi người gửi trong ca được chọn, lấy xác nhận người nhận thay và kiểm tra lịch. Đề xuất cập nhật ô D đó sang tên đã đối chiếu của người nhận thay, giữ nguyên các vị trí còn lại và nội dung ca. **Đã chốt:** bot giữ nguyên J, vận hành tự cập nhật.

### 3.2. Hoán đổi hai ca

Xác định hai dòng D ở hai ca, lấy xác nhận cả hai người cho đủ thông tin hai ca, kiểm tra lịch sau đổi và hoán đổi tên ở đúng hai vị trí đó. Mỗi ca tiếp tục giữ track/session, phòng, buổi và Key Coach của mình. Chỉ báo hoàn tất sau khi kiểm tra cả hai phân công; nếu một thay đổi thất bại thì theo dõi phục hồi theo đặc tả.

Sai khác chỉ nằm ở vùng lặp K–P không tự làm yêu cầu mất điều kiện xử lý. Ca chưa rõ nguồn ngày, chưa đối chiếu được tên người hoặc chưa đủ phạm vi lịch để kiểm tra thì cần bổ sung thông tin.

### 3.3. Trình tự đọc/ghi và xử lý cột J — đề xuất

1. Xác định đúng kỳ/tab, khối ngày và các dòng dữ liệu có STT; giải ô gộp B/C/E/F/G/H trong phạm vi tương ứng, đọc D/J theo từng dòng.
2. Tạo ca từ ngày ở tiêu đề A, track B, session C, phòng F và buổi G; đổi buổi sang giờ đã chốt. Đối chiếu tên D với danh sách người dùng và gắn vị trí vào đúng ca.
3. Kiểm tra người dùng có liên kết Zalo đã được vận hành xác thực; hiển thị ca từ nguồn chuẩn và lấy xác nhận nhận ca cùng xác nhận không có lịch bận khác. Hoán đổi cần cả hai người xác nhận ca nhận về; lưu nội dung cùng người phụ trách gốc.
4. Đọc lại nguồn trước ghi, đối chiếu nội dung ca và tên ở D, kiểm tra liên kết còn hiệu lực, xác nhận đầy đủ và lịch chương trình sau thay đổi. Nếu dòng đã di chuyển, tìm lại bằng mã/ánh xạ ổn định rồi kiểm tra nội dung; không dùng tọa độ cũ làm căn cứ duy nhất.
5. Ghi đúng một hoặc hai phân công ở D, không ghi J; đọc lại để xác minh toàn bộ kết quả trước hoàn tất. Cách kiểm soát sửa đồng thời và phục hồi cập nhật một phần phải được thiết kế trước khi bật tự động.
6. Lưu lịch sử thay đổi và thông báo các bên; sai khác ở vùng lặp được ghi riêng để vận hành đối chiếu.

**Quy tắc J đã chốt:** giữ nguyên J khi bot đổi người ở D; vận hành tự cập nhật. Bot không ghi Rảnh hoặc Chưa cập nhật từ xác nhận nhận ca. Xác nhận nhận ca/không có lịch bận khác được lưu riêng. Vì J có thể chưa được cập nhật theo người mới, không coi nhãn này là bằng chứng người mới rảnh hoặc đã nhận ca. Nếu vận hành sửa J trong lúc bot cập nhật D, không ghi đè giá trị mới bằng bản J cũ. Việc sửa vùng thông tin lặp K–P không nằm trong thao tác đổi phân công đề xuất.

Với nghỉ chưa có người thay, **đã chốt** bot nhắn đồng thời các labcoach hợp lệ không trùng lịch sau khi vận hành chấp nhận. Người nhận xác nhận đầy đủ và đủ điều kiện sớm nhất được nhận, người sau không nhận cùng vị trí. Cần lưu chấp nhận, lời mời và người đang được giữ vị trí trong bảng theo dõi yêu cầu, không biểu diễn chấp nhận bằng đổi J hoặc xóa D. Lời mời có hạn 24 giờ, tối đa đến lúc ca bắt đầu; hoán đổi lấy mốc ca sớm hơn. Chỉ hoàn tất sau khi D phản ánh đúng người nhận; giữ vị trí chưa đồng nghĩa lịch đã đổi.

**Ví dụ hội thoại theo dữ liệu chuẩn:** “Bạn đề nghị [người thay] nhận ca [Track/Session], ngày [dd/mm/yyyy], phòng [F], Sáng 09:00–13:00. Xác nhận gửi yêu cầu?” Với hoán đổi, trình bày cả hai ca cùng chiều giao/nhận; chiều luôn hiển thị 14:00–18:00. Tên trong mẫu là chỗ điền từ danh sách đã đối chiếu, không lấy tên ví dụ làm dữ liệu thật.

## 4. Các tab theo dõi bổ sung

Trong workbook đọc được chỉ thấy tab lịch nêu trên; chưa thấy tab người dùng, yêu cầu thay đổi, issue hoặc lịch sử. Đề xuất bổ sung các tab theo mô hình trong đặc tả, sau khi rà soát quy trình vận hành. Bảng lịch hiện tại tiếp tục là lịch chính thức; không coi mô hình Shifts/Assignments trong đặc tả là quyết định tạo thêm một lịch chính thức song song.

Trạng thái yêu cầu và issue phải được theo dõi riêng với cột J rảnh/bận. Link nhóm Q không dùng để liên kết tài khoản cá nhân. **Đã chốt:** danh sách mã labcoach và tài khoản Zalo được vận hành xác thực trước khi sử dụng; cấu trúc danh sách và vòng đời liên kết được đề xuất trong đặc tả.

## 5. Kiểm tra cần có khi tích hợp

- Loại đúng các dòng tiêu đề, ngăn cách và các dòng chỉ có thông tin lặp mà không có STT; không biến chúng thành vị trí phân công.
- Đọc giá trị ô gộp trong đúng phạm vi gộp; không điền giá trị xuyên qua ngày hoặc nhóm lớp khác.
- Chuẩn hóa khoảng trắng, ngày/tháng và tên buổi để đối chiếu; dùng A cho ngày và B–J cho bảng chính, ghi nhận sai khác vùng lặp mà không thay nguồn chuẩn.
- Không dùng màu ô để xác định người hay trạng thái nghiệp vụ.
- Kiểm tra vùng lịch đầy đủ cho người liên quan; bảng 02/10–16/10 chưa chứng minh đã có toàn bộ lịch lý thuyết/lab hoặc các kỳ khác.
- Đọc lại nguồn trước cập nhật; phát hiện dòng di chuyển, đổi tên người và thay đổi nội dung bảng chính.
- Thử các trường hợp nhiều labcoach cùng lớp, tên trùng, vị trí trống, ô gộp, giữ nguyên J kể cả khi vận hành sửa đồng thời, hoán đổi chỉ ghi được một vị trí và nhiều ứng viên đồng ý cho cùng vị trí.

## 6. Phần đã chốt và nội dung còn cần hoàn thiện

Ý nghĩa D/J, giờ Sáng/Chiều, nguồn chuẩn B–J, vận hành xác thực liên kết Zalo và kiểm tra lịch chương trình kết hợp người nhận tự xác nhận không có lịch bận khác đã chốt; không hỏi lại các nguyên tắc này.

Đã chốt thêm bot giữ nguyên J, hạn lời mời 24 giờ tối đa đến lúc ca bắt đầu, mời đồng thời sau chấp nhận nghỉ và người nhận đủ điều kiện sớm nhất được nhận. Các điểm còn mở: mã ca/vị trí ổn định, danh sách người dùng, danh mục bảng/kỳ lịch chương trình; cơ chế giữ vị trí và phục hồi lỗi; số vị trí bắt buộc nếu cần theo dõi ca thiếu người; cách đưa kỳ lịch mới vào hệ thống. Chi tiết quyền và thông báo tiếp tục được rà soát theo đặc tả. Chưa chọn kiến trúc hoặc bắt đầu ghi lên Sheets.
