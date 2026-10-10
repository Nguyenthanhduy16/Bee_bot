# Báo cáo nghiệm thu kỹ thuật Bee Bot v1

Ngày: 10/10/2026. Người phụ trách nghiệm thu nghiệp vụ: chủ dự án. QA độc lập kiểm tra qua các giao diện công khai; không sửa phần triển khai nghiệp vụ.

## Kết quả hiện tại

**140 kiểm thử tự động đạt**, lệnh chạy tại repo:

```bash
.venv/bin/python -m pytest -q
```

Lần chạy QA ghi nhận: `140 passed, 1 warning in 6.73s`; Lead chạy độc lập cũng đạt 140 tests. Phạm vi gồm dịch vụ Python/SQLite, lịch JSON giả lập, MCP stdio thật, importer XLSX, adapter Zalo/HTTP webhook, polling worker/HermesRunner, onboarding và nội dung thông báo kiểm thử cục bộ. Ba kiểm thử onboarding xác minh không có token thì không gọi API, tin bất kỳ không cấp danh tính, chỉ mã riêng đúng mới liên kết một lần. Warning là deprecation của Starlette TestClient với httpx; không có kiểm thử thất bại.

**Hermes/model thật đã gọi công cụ và cả 5 luồng đã được thử qua các phiên Paseo riêng:** nhận thay, nghỉ, hoán đổi, issue và tra cứu. Ngoài ra, tin Zalo thật “Xem lịch của tôi” đã đi qua Hermes, đọc lịch demo và được API Zalo xác nhận gửi trả lời. QA kiểm tra dữ liệu/session độc lập; người dùng chưa xác nhận đã nhìn thấy tin trả lời. Chưa ghi Google Sheets thật.

## Các kết quả đã quan sát

| Nhóm | Hành vi đã kiểm chứng |
| --- | --- |
| Nhận thay | Chưa có xác nhận trực tiếp thì D giữ nguyên; thiếu xác nhận không bận ngoài chương trình chưa giữ vị trí; đủ xác nhận và điều kiện mới hoàn tất. J và các phân công khác giữ nguyên. |
| Nghỉ | Chưa được vận hành chấp nhận thì không phát lời mời tìm người. Người gửi bổ sung người thay giữ cùng mã, báo vận hành, chuyển nhận thay không cần duyệt nghỉ. Chấp nhận nghỉ đến muộn không tạo lượt mời song song. |
| Tìm người | Mời nhiều người sau duyệt; một người từ chối không hủy lượt tìm. Xác nhận thiếu điều kiện không giữ chỗ; hai phản hồi đầy đủ đồng thời chỉ một người hoàn tất. Người đã giữ chỗ nhưng lỗi ghi vẫn ngăn người sau nhận vị trí. Không có ứng viên hoặc tất cả từ chối chuyển ops, không tự phát lại. |
| Hoán đổi | Một yêu cầu kiểm tra và ghi hai vị trí; loại bỏ ca giao đi khi kiểm tra lịch sau đổi. Kiểm tra cả lịch ca nhận của người gửi; thiếu xác nhận không sửa lịch. |
| Issue | Tiếp nhận không cần ảnh; không tự gộp các sự cố cùng phòng. Tái phát liên kết mã cũ. Vận hành giải quyết phải có kết quả, người và thời điểm; người ghi nhận chỉ hủy trước xử lý. |
| Tra cứu và quyền | Người không liên kết/đã vô hiệu không đọc hoặc ghi, kể cả tài khoản bị vô hiệu sau lúc mời. Đoán mã không cấp quyền đọc yêu cầu/issue hoặc xác nhận thay người khác. Lịch cá nhân/outbox chỉ trả cho đúng actor. Người nhận thay không có quyền ops. |
| Hạn và lịch bận | Không trùng khi hai ca chỉ chạm mốc giờ; có phân công trùng vẫn bị chặn kể cả J ghi Bận. Từ đúng hạn 24 giờ hoặc giờ bắt đầu không nhận nữa; ngay trước hạn vẫn nhận. Hoán đổi lấy ca bắt đầu sớm hơn. |
| Hủy/rút duyệt | Vận hành cần lý do; hủy/rút duyệt trước ghi vô hiệu lời mời cũ. Yêu cầu hoàn tất không thể dùng hủy để hoàn nguyên. Ops đề cử người vẫn cần người đó phản hồi trực tiếp. |
| Dedup và khởi động lại | Phát lại sự kiện không tạo yêu cầu/issue/thông báo/ghi lịch lặp; không tái dùng mã sự kiện giữa actor hoặc thao tác khác. Yêu cầu, issue, lời mời và outbox giữ sau khởi động lại. |
| Giữ chỗ xuyên yêu cầu | Một người đã giữ ca nhưng kết quả ghi chưa rõ không được nhận thêm ca khác giao giờ. |
| Lỗi ghi và đối chiếu | Timeout trước/sau ghi, lỗi rõ ràng, hoán đổi ghi một ô: đọc lại mọi ô; hoàn tất chỉ khi cả hai đúng, giữ chưa hoàn tất khi ghi một phần. Đối chiếu/maintenance không ghi lại hoặc tự hoàn nguyên. Ops hoàn thành ô còn thiếu thì bot xác minh được. |
| Mất tiến trình | Mô phỏng tiến trình mất sau ghi lịch nhưng trước lưu kết quả: restart + maintenance đọc lại để hoàn tất, không ghi thêm lần nào; phát lại sự kiện nhận kết quả hoàn tất hiện tại. |
| Sửa lịch thủ công | Ops đổi người/phòng/lớp trước lần ghi khiến yêu cầu cũ dừng. Ops sửa J riêng vẫn được giữ sau bot đổi D. Lịch người nhận phát sinh xung đột sau mời được kiểm tra lại. |
| Emulator | Đổi D giữa đọc snapshot và ghi bị từ chối bởi kiểm tra snapshot cục bộ; hoán đổi kiểm tra toàn bộ trước sửa bất kỳ vị trí nào. Không suy ra bảo đảm này cho Sheets thật. |
| Bảo trì | Cảnh báo ca còn 2 giờ và đã bắt đầu; không tự sửa lịch lịch sử. Tổng hợp mỗi mốc chạy không bị lặp. |

Các tệp kiểm thử: `tests/test_workflows.py`, `tests/test_safety.py`, `tests/test_schedule.py`, `tests/test_mcp.py`, `tests/test_sheets_import.py`, `tests/test_zalo.py`, `tests/test_zalo_webhook.py`, `tests/test_zalo_worker.py`, `tests/test_zalo_worker_qa.py`, `tests/test_notification_text.py`, `tests/test_zalo_live_contract_qa.py`, `tests/test_onboarding.py`. Dữ liệu service dùng clock cố định có múi giờ; riêng subprocess MCP dùng lịch tương đối với clock thực để không hết hạn giả khi chạy lại sau ngày lập báo cáo.

## Bằng chứng MCP

Kiểm thử khởi chạy chương trình `python -m bee_bot.mcp_server` qua MCP SDK và stdio, thực hiện chuỗi:

1. Phiên `an` đọc danh tính/lịch, xác nhận tạo nhận thay cho `binh`.
2. Phiên `chi` tra mã đó bị từ chối.
3. Phiên `binh` nhận lời mời và xác nhận không bận ngoài chương trình; D đổi đúng và yêu cầu hoàn tất.

Schema công cụ không có `actor_id`, `role`, `event_id` hoặc đối số sửa ô tự do. Server không khởi động với danh tính không tồn tại/vô hiệu. Mutation thiếu xác nhận ý định bị từ chối. Kiểm thử subprocess này độc lập với bằng chứng hội thoại bên dưới.

## Bằng chứng Hermes và Paseo

Lead đã cài dependency có `uv.lock`, tạo 5 profile Hermes `bee-bot-*` và 5 provider Paseo riêng, giữ provider/cấu hình cá nhân cũ; áp dụng qua `paseo daemon reload`.

Log cục bộ `.bee-bot/hermes-smoke-an.jsonl` có các sự kiện `tool_use`/`tool_result` cho `mcp__bee_bot__get_bot_context` và `mcp__bee_bot__get_my_assignments`. Lead quan sát model đọc skill Bee Bot và trả actor An/lịch A001 đúng. QA xác nhận độc lập log có các tên công cụ này. Log chứa dữ liệu phiên thử, nằm ở thư mục bị Git bỏ qua.

Lead tạo và sử dụng các phiên Paseo:

| Vai thử | Mã phiên Paseo |
| --- | --- |
| An | `d2d71f15-19f3-4b0a-9f08-c6ebcee7aad2` |
| Bình | `c0652d42-c847-4e8c-9fea-fddde7974526` |
| Vận hành | `9773b6e5-e403-4bc3-a45f-350ab064a6a2` |
| Dũng | `d94fc3f2-ba73-4856-9525-96a23c4b78a1` |

Qua phiên An, yêu cầu `YC-4a45d1adbaa2` đề nghị Bình nhận A001 được tạo. Qua phiên riêng Bình, người nhận xác nhận nhận và không bận ngoài chương trình; công cụ trả hoàn tất. QA đọc lại dữ liệu cục bộ xác nhận:

- `A001.coach_id = binh`; J vẫn là `Ghi chú vận hành A001 — giữ nguyên`.
- Yêu cầu có owner `an`, reserved recipient `binh`, trạng thái `completed`, thời điểm `2026-10-10T21:46:47.648668+07:00`.
- Outbox hoàn tất có đúng các người nhận `an`, `binh`, `ops`.

Lead tiếp tục thực hiện các luồng còn lại qua phiên Paseo; QA đọc lại các kết quả dưới đây từ JSON/SQLite:

| Luồng | Kết quả quan sát |
| --- | --- |
| Nghỉ | `YC-559e3d70e859`: An xin nghỉ A005, ops chấp nhận, Bình xác nhận trực tiếp không bận; trạng thái completed, A005 = binh, J giữ nguyên. |
| Hoán đổi | `YC-860e0546354d`: Bình giao A007 sáng 14/10 và nhận A008 chiều từ Dũng, cả hai xác nhận không bận; completed, A007 = dung, A008 = binh, cả hai J giữ nguyên. |
| Issue | `IS-394b0121006f`: An báo Wi-Fi phòng A101 không có ảnh, ops giải quyết có mô tả khởi động lại bộ phát và kiểm tra ổn định; resolved, có resolved_by ops và resolved_at. |
| Tra cứu | An tra issue đã resolved; Dũng dùng get_my_invitations/get_request_status/respond_to_invitation/get_request_status trong phiên của mình. |

Đây là nghiệm thu tích hợp hội thoại cho 5 luồng trên dữ liệu giả qua phiên Paseo do Lead điều khiển. Người phụ trách chưa tự ký nghiệm thu các luồng trong giao diện Paseo; kết quả service test và hội thoại do Lead thử không thay cho bước nghiệm thu của người phụ trách.

## Import lịch và adapter Zalo

Importer XLSX được kiểm thử bằng workbook tổng hợp: nguồn chuẩn B–J, ô gộp, D trống, ngày/buổi, giờ sáng/chiều, sai khác vùng lặp, ID snapshot và nguồn không bị sửa. Workbook do người phụ trách cung cấp đã được tải read-only vào thư mục riêng bị Git bỏ qua. QA kiểm tra snapshot thực tế:

- 390 vị trí; 346 có phân công D, 44 trống.
- 101 cảnh báo khác vùng lặp; 51 nhóm tên labcoach tạo định danh tạm, đều inactive và chưa xác thực. Snapshot còn một danh tính ops tạm inactive.
- `complete_coverage=false`, `source_write_enabled=false`, ID chỉ có hiệu lực trong snapshot. Chưa dùng snapshot này để đổi lịch thật.

Các kiểm thử adapter Zalo và HTTP webhook chạy offline: URL/payload API qua mock transport, che token trong lỗi, timeout gửi không tự lặp, xác thực secret trước đọc payload, chỉ chat riêng và tài khoản đã ánh xạ, inbox bền/dedup qua restart, một worker claim sự kiện, không phát lại handler có kết quả chưa rõ. HTTP test client xác nhận chỉ ACK sau ghi inbox, lỗi ghi trả 503, payload quá lớn bị từ chối và không lộ nội dung riêng trong response.

13 kiểm thử bridge polling bổ sung dùng client/model giả lập. Kiểm chứng profile cố định theo actor; không sao chép auth.json/.env/API key; gửi nội dung qua stdin, dùng resume session riêng từng sender; loại token/secret Zalo khỏi env Hermes; lưu session và lịch sử gửi bền. Pending inbox được xử lý lại, nhưng model hoặc gửi tin có kết quả chưa rõ không tự chạy/gửi lại. Có webhook hoặc trạng thái webhook chưa rõ thì từ chối polling, không tự xóa webhook. Worker yêu cầu đúng một tài khoản Zalo cho mỗi actor thử. HTTP log INFO được lọc token, không tắt các thông báo log khác.

5 kiểm thử nội dung thông báo xác nhận tiếng Việt dễ đọc, lời mời có ca/phòng/hạn và cả hai điều kiện xác nhận, lời mời đóng không được mời lại, không in metadata hoặc lý do nghỉ riêng. Nội dung lấy qua getter đúng quyền; khi không được phép chỉ trả câu chung. Tổng hợp tính cả yêu cầu và sự cố đang mở qua dữ liệu được phép xem.

Lead còn chạy HermesRunner/model thật với tin đầu vào cục bộ, actor `binh`, trả session_id và các ca A001/A003/A005/A008 đúng; bằng chứng ở `.bee-bot/zalo-hermes-runner-smoke.json`. QA kiểm tra các trường `real_hermes=true`, `zalo_network_used=false` và các mã ca trong kết quả. Probe này chỉ đọc và được chạy trước sửa truyền event ID; việc safe-env truyền event ID sau sửa có bằng chứng runtime riêng. Khởi động worker thiếu token cũng đã được Lead kiểm tra: trả `ZALO_CONFIG`, không gọi network hoặc gửi tin.

Không có token bot thật, endpoint public hoặc người dùng Zalo thật tham gia các kiểm thử tự động này. Bằng chứng một luồng Zalo thật chạy xuyên suốt được ghi riêng dưới đây.

## Bằng chứng API và hội thoại Zalo thật

Lead đã cấu hình token riêng ngoài Git và kiểm tra API thật; QA không gọi mạng Zalo hoặc đọc token:

| Thao tác thật của Lead | Kết quả đã quan sát |
| --- | --- |
| getMe | HTTP 200, `ok=true`, tài khoản bot hợp lệ loại BASIC. |
| getWebhookInfo trên bot mới chưa đặt webhook | HTTP 200, `ok=false`, integer `error_code=404`, description đúng `Not Found`; được chuẩn hóa thành URL webhook trống. |
| getUpdates timeout 1 giây khi chưa có tin | HTTP 200, `ok=false`, integer `error_code=408`, description đúng `Request timeout`; được chuẩn hóa thành không có sự kiện. |

QA bổ sung 19 hồi quy bằng mock transport cho các phản hồi thực tế này: chỉ chuẩn hóa đúng phương thức, HTTP 200, boolean `ok=false`, integer code và description đã quan sát. Cùng envelope ở getMe/sendMessage, lỗi xác thực, code dạng chuỗi, description khác, HTTP 404/408/500 hoặc network timeout vẫn là lỗi; không nuốt kết quả gửi chưa rõ. Kiểm thử DEBUG logs và lỗi không lộ token/description riêng.

Các probe trong bảng chỉ đọc API và không gửi tin. Sau đó, chủ dự án gửi mã challenge đúng và tài khoản Zalo được liên kết với persona demo `an`. Worker nhận tin thật “Xem lịch của tôi”, gọi Hermes/model rồi gửi câu trả lời về Zalo.

QA đọc các DB đã tồn tại bằng SQLite URI `mode=ro`, không đọc token hoặc thay đổi runtime/profile, xác nhận:

- Trong `.bee-bot/zalo-demo/zalo-inbox.db`, đúng một sự kiện có text “Xem lịch của tôi”, actor `an`, inbox `completed`, result `delivery_status=sent`. Bảng giao nhận có một bản ghi `sent`.
- Kết quả là 2 ca A001 ngày 12/10/2026 09:00–13:00 và A005 ngày 13/10/2026 09:00–13:00, phòng A101; câu trả lời ghi rõ dữ liệu giả lập và chưa phải Sheets thật.
- Session `20261010_223421_11fad6` trong profile riêng `bee-zalo-an` có tool results `mcp__bee_bot__get_bot_context` và `mcp__bee_bot__get_my_assignments`, cùng hoạt động đọc skill. Không dùng lời tự nhận của model để thay cho bằng chứng gọi công cụ.

Đây là bằng chứng Zalo → Hermes → công cụ → API gửi trả lời thành công cho **một luồng tra cứu lịch**. Trạng thái `sent` xác nhận API nhận thao tác gửi; người dùng chưa xác nhận nhìn thấy câu trả lời trên Zalo. Chưa nghiệm thu nhận thay/nghỉ/hoán đổi/issue qua Zalo thật.

Lần thử dùng lịch demo mới riêng ở `.bee-bot/zalo-demo/schedule.json`, có 8 vị trí và 5 persona thử, tránh gửi lại outbox của các phiên Paseo trước. Theo Lead, worker đang chạy trong phiên thử hiện tại; chưa được triển khai thành dịch vụ nền tự phục hồi. Nguồn Sheets thật vẫn chỉ đọc.

## Lỗi phát hiện và đã sửa

QA phát hiện phát lại sự kiện sau mất tiến trình trả trạng thái `updating` cũ dù maintenance đã đối chiếu hoàn tất. Peer nghiệp vụ sửa đọc kết quả hiện tại khi replay; kiểm thử hồi quy đã đạt. Ca này bảo vệ thông báo kết quả đúng khi adapter gửi lại sự kiện sau khởi động lại.

QA đối chiếu bản Hermes đã cài và phát hiện stdio MCP lọc bỏ biến parent env tùy ý, nên chỉ đặt BEE_BOT_EVENT_ID trong env Hermes chưa truyền được mã sự kiện tới MCP. Peer tích hợp sửa profile Zalo thử thêm env interpolation rõ ràng `${BEE_BOT_EVENT_ID}`; MCP từ chối placeholder chưa được thay. Kiểm thử hồi quy xác nhận cấu hình này và event ID ổn định theo thông điệp + thao tác + đối số. Peer tích hợp còn chạy probe dưới runtime Hermes đã cài để xác nhận bước interpolate/safe-env truyền mã đúng. Không coi probe môi trường hoặc subprocess giả lập là nghiệm thu tin Zalo thật.

## Phạm vi chưa nghiệm thu và giới hạn

Sau khi chủ dự án kiểm tra Hermes Desktop, Lead sửa lỗi phiên Zalo bị ẩn trong cây dự án: nguồn mặc định `oneshot` là loại Hermes không liệt kê ở đây. Runner hiện truyền `--source zalo`; 14 kiểm thử worker và QA worker đạt sau sửa. Với đúng phiên tra cứu đã có, Lead dừng worker khi không có lượt xử lý, sao lưu DB riêng, đổi một trường nguồn và đối chiếu 8 thông điệp giữ nguyên. API giao diện xác nhận phiên xuất hiện trong cây dự án và đã được ghim; worker chạy lại. Không thay nội dung hội thoại hoặc tạo bản sao phiên.

- Chưa kiểm chứng Google Sheets ghi thật, các luồng thay đổi/issue qua Zalo thật, webhook public thật hoặc triển khai máy chủ. Một tài khoản chủ dự án đã liên kết với persona demo; chưa xác thực danh mục tài khoản labcoach thật cho pilot. API đã xác nhận gửi một câu trả lời tra lịch nhưng người dùng chưa xác nhận nhìn thấy tin.
- File lock và kiểm tra snapshot là của JSON emulator. Chưa có bằng chứng Google Sheets tránh ghi đè khi vận hành sửa giữa lần đọc cuối và lần ghi; đọc lại sau ghi không bảo đảm phát hiện giá trị ops đã bị ghi đè.
- Lead đã chạy maintenance CLI `worker --once`; lệnh `bee-bot worker --interval 30` chạy liên tục khi bỏ `--once`. Chưa bật tiến trình nền bền/triển khai scheduler đảm bảo tổng hợp 08:00/16:00 khi không có ai gọi.
- Bản thử dùng đệm di chuyển 0 phút. Chưa chứng minh lịch được nhập bao phủ đủ toàn bộ kỳ/tab chương trình hoặc tên/mã người đã xác thực cho pilot.
- MCP demo trực tiếp sinh UUID cho mỗi mutation. Bridge Zalo đặt event ID qua env tin cậy và tạo mã ổn định theo thông điệp/thao tác/đối số để dedup. Hai mutation có đối số khác nhau là hai thao tác; event ID không xuất hiện trong schema để model tự đặt.
- Chủ máy là quản trị viên tin cậy của các profile thử. Giới hạn actor trong MCP không phải cơ chế cách ly chủ máy khỏi quyền sửa DB/lịch.

Trước pilot, người phụ trách nghiệm thu nghiệp vụ cần chạy các ca qua kênh hội thoại được bàn giao, xác nhận danh tính và nguồn lịch, và duyệt kết quả tích hợp thật riêng. Không dùng kết quả `pytest` để thay thế nghiệm thu những phần chưa được nối thật.
