# Tạo Bee Bot trong Zalo và kết nối Hermes

Đã đối chiếu nguồn chính thức ngày **10/10/2026**. Hướng phù hợp bản chat riêng Bee Bot là **Zalo Bot Platform**: người dùng mở cuộc trò chuyện với tài khoản bot trong Zalo; Hermes và nghiệp vụ chạy ở backend. Không cần xây một trang web nhúng để chat với bot. Đây là lựa chọn thiết kế dựa trên khả năng nhắn tin/API của nền tảng, chưa phải bằng chứng bot đã chạy thật. [Giới thiệu nền tảng](https://bot.zapps.me/)

**Đầu vào đã xác nhận:** người phụ trách dùng tài khoản Zalo cá nhân hiện có để quản lý bot; không cần đăng ký lại tài khoản cá nhân.

**Cập nhật:** người phụ trách đã tạo **Bot BeeCoach**, cung cấp Bot Token và gửi mã liên kết từ chat riêng. Token đã lưu trong tệp riêng ngoài Git; `getMe` xác nhận bot và `getWebhookInfo` xác nhận chưa có webhook. Tin thật “Xem lịch của tôi” đã chạy Zalo → Hermes → công cụ Bee Bot → API gửi phản hồi Zalo thành công. Tài khoản thử đang dùng vai An trên lịch JSON giả; chưa ghi Google Sheets thật. Các bước tạo dưới đây được giữ làm hướng dẫn tham khảo.

## “Chưa có tài khoản” có hai trường hợp

| Trường hợp | Đầu vào cần có |
|---|---|
| Chưa có **tài khoản Zalo cá nhân** | Một người được giao làm chủ bot cần đăng ký/đăng nhập Zalo trên điện thoại, dùng số điện thoại mình kiểm soát và tự hoàn tất xác thực. Có thể là bạn hoặc đầu mối vận hành đã có Zalo. |
| Đã có Zalo cá nhân, chưa có **tài khoản Bot** | Dùng tài khoản hiện có mở Zalo Bot Manager/Creator, tạo bot mới để nhận Bot Token. |

Quy trình đăng ký Zalo cá nhân chính thức: cài app → Đăng ký → tên → số điện thoại → xác nhận/kích hoạt. Không thể hoàn thành bước xác thực điện thoại chỉ bằng mã nguồn của Bee Bot. [Hướng dẫn Zalo Help](https://help.zalo.me/huong-dan/chuyen-muc/moi-bat-dau/huong-dan-dang-ky-tai-khoan-zalo-nhanh-chong/)

Trang Bot Platform giới thiệu giải pháp cho cá nhân và doanh nghiệp. Hướng dẫn tạo bot đã kiểm tra không liệt kê thủ tục đăng ký doanh nghiệp hoặc OA riêng làm điều kiện bước tạo bot; tuy nhiên điều kiện/quyền thực tế vẫn do ứng dụng Creator quyết định khi chủ tài khoản mở nó. Không khẳng định mọi tài khoản đều được duyệt tự động. [Nền tảng](https://bot.zapps.me/), [hướng dẫn tạo bot](https://docs.zaloplatforms.com/docs/BOT/create_bot)

## Đường dẫn và thao tác tạo

1. Mở app Zalo trên điện thoại đã đăng nhập, tìm **OA Zalo Bot Manager**.
2. Trong menu chat chọn **Tạo bot** để mở **Zalo Bot Creator**.
3. Đặt tên **Bot Bee** (tài liệu yêu cầu bắt đầu bằng `Bot`), điền thông tin trên màn hình và hoàn tất bước tạo theo chủ tài khoản.
4. Zalo gửi thông tin bot và **Bot Token** vào tin nhắn tài khoản chủ bot. [Hướng dẫn chính thức](https://docs.zaloplatforms.com/docs/BOT/create_bot)

**Zalo Bot Manager là OA của nền tảng Zalo mà bạn tìm và mở, không phải OA bạn phải tạo hoặc sở hữu.** Tài khoản Zalo cá nhân hiện có của bạn dùng để mở Creator và quản lý bot. Quy trình tạo bot này không yêu cầu bạn tự tạo OA doanh nghiệp trong các bước được tài liệu liệt kê. Việc chọn “Truy cập Zalo OA” trong hướng dẫn nói tới OA Bot Manager đó. [Hướng dẫn tạo bot](https://docs.zaloplatforms.com/docs/BOT/create_bot)

Có thể mở [Bot Creator trên Zalo](https://zalo.me/s/botcreator/) từ điện thoại; URL trả trang Zalo Mini App khi kiểm tra, nhưng không có trình duyệt/app Zalo đã đăng nhập để xác minh màn hình tạo thực tế trong phiên làm việc này. Cách tìm OA/menu ở trên là đường đi được hướng dẫn chính thức xác nhận.

Tài liệu chính thức còn cung cấp [ảnh QR mở Creator](https://docs.zaloplatforms.com/assets/BOT/images/zbot-creator_qrcode.jpg). Mã QR trong ảnh đã được giải mã tại máy thành `https://zalo.me/s/zqr.zwuoy64w`; chưa kiểm chứng app đích sau mở QR trên điện thoại. Không tự chế link OA hoặc số ID mini app.

Token cấu hình riêng ngoài Git, không dán vào chat hoặc báo cáo. Mẫu chỉ có tên biến ở [zalo.env.example](../examples/zalo.env.example). Token được nền tảng dùng trong URL API HTTPS và tồn tại tới khi chủ bot reset. [Xác thực Bot API](https://bot.zapps.me/docs/authorize/)

## Sau khi có bot

Luồng triển khai là:

```text
Chat riêng Zalo → Bot API polling/webhook → xác thực sender ID
               → phiên Hermes riêng của người đó → MCP Bee Bot
               → kết quả nghiệp vụ → Bot API sendMessage → Zalo
```

Từng người nhận thay phải xác nhận từ tài khoản Zalo đã liên kết chính họ. Tên hiển thị hay câu “tôi là vận hành” không cấp quyền. Danh sách sender ID → person ID do chủ nghiệp vụ xác nhận; role lấy từ danh mục người của hệ thống.

Thử đầu tiên nên dùng **long polling tại máy** với lịch giả và Hermes thật, không cần public domain/tunnel. API chính thức `getUpdates` dành cho development và không hoạt động khi bot đã có webhook. Không xóa webhook tự động của bot có sẵn. [getUpdates](https://bot.zapps.me/docs/apis/getUpdates/)

Pilot chạy liên tục sau đó dùng webhook HTTPS công khai, xác thực header secret, lưu bền và worker riêng. Endpoint HTTP nhận đã được kiểm thử local; chưa được đăng ký với Zalo. [Webhook](https://docs.zaloplatforms.com/docs/BOT/webhook), [setWebhook](https://bot.zapps.me/docs/apis/setWebhook/)

## Phần chủ bot làm và phần chúng tôi làm

Chủ bot cần có tài khoản Zalo đăng nhập, hoàn tất tạo bot trong app và cấu hình token riêng; chọn tài khoản thử; xác nhận liên kết người dùng. Số điện thoại/OTP và bước chấp nhận điều khoản thuộc thao tác của chủ tài khoản. Không cần bạn tự lập trình bot hay thuê hosting để thử polling đầu tiên.

Phía triển khai có thể tiếp tục ngay: dựng worker polling → Hermes, session theo sender, event ID bền, gửi phản hồi/outbox có trạng thái sent/uncertain; kiểm thử bằng mock khi chưa có token. Khi chủ bot cấu hình token, kiểm tra `getMe`, trạng thái webhook, và thử round trip với tài khoản đã liên kết. Không gửi tới người chưa liên kết hoặc tự điều khiển tài khoản cá nhân thay Bot API.

Nếu “nhúng” nghĩa muốn màn hình lịch/nút thao tác bên trong Zalo thay cho chat, đó là yêu cầu **Zalo Mini App** riêng, cần thiết kế giao diện và quy trình platform khác. Luồng hiện tại là bot chat riêng; việc Creator bản thân là Mini App không có nghĩa Bee Bot cần xây Mini App. [Zalo Mini App Platform](https://miniapp.zaloplatforms.com/)

## Trạng thái và giới hạn

Đã có API client, ingress ánh xạ danh tính, SQLite inbox chống lặp, HTTP nhận chạy local và worker polling gọi Hermes với session riêng. Worker đã nhận tin từ tài khoản chủ bot, gọi Hermes thật và API xác nhận gửi phản hồi có hai ca A001/A005 đúng lịch thử. Trạng thái `sent` là xác nhận API, chưa chứng minh người dùng đọc; chưa nghiệm thu gửi lời mời/nghiệp vụ đổi lịch qua Zalo. Bản thử dùng lịch JSON, không tự ghi Google Sheets thật. [Hướng dẫn chạy worker](../examples/ZALO_ADAPTER.md)

Tệp cấu hình riêng trên máy là `.bee-bot/zalo.env`, đã có token; tệp này cùng các liên kết danh tính nằm ngoài Git, chỉ chủ máy đọc được. Lệnh kiểm tra kết nối:

```bash
.venv/bin/python scripts/zalo_onboard.py check --env-file .bee-bot/zalo.env
```

Helper chỉ đọc hồ sơ bot/cấu hình webhook, không gửi tin hoặc tự xóa webhook. Để liên kết **tài khoản thử đã biết** với persona cục bộ, chủ tài khoản gửi đúng mã riêng trong `.bee-bot/link-code.txt` tới bot; người quản trị chạy:

```bash
.venv/bin/python scripts/zalo_onboard.py identify --actor an --env-file .bee-bot/zalo.env
```

Helper chỉ liên kết nếu nội dung tin khớp mã riêng; tin bất kỳ không cấp quyền. Mã dùng một lần, tệp bị loại bỏ sau liên kết thành công. Không dùng bước demo này thay cho danh sách labcoach/Zalo đã xác thực cho pilot. Trước identify, dừng worker polling khác để không lấy mất tin liên kết. Khi đã liên kết và chuẩn bị dữ liệu/profile, chạy:

```bash
.venv/bin/python -m bee_bot.zalo_worker --env-file .bee-bot/zalo.env --state-dir .bee-bot/zalo-demo
```

Lần thử Zalo đầu dùng lịch giả mới tại `.bee-bot/zalo-demo`, tách dữ liệu các phiên Paseo trước đó để không gửi lại thông báo lịch sử. Tài khoản chủ bot đã liên kết với vai labcoach thử `an`; mã liên kết đã bị loại bỏ sau khi dùng. Đây chưa phải danh tính labcoach production. Worker local đang chạy; máy cần tiếp tục hoạt động và có mạng. Webhook URL trong Creator để trống khi chạy polling. URL webhook public chỉ được điền sau khi có backend HTTPS đã triển khai và kiểm chứng.

Trong Hermes Desktop, chọn profile `bee-zalo-an` ở dãy ô phía trái dưới. Phiên **Xem lịch cá nhân** đã được ghim và có nguồn `zalo`, hiện trong cây dự án. Lỗi ban đầu do runner chạy một lượt bị Hermes gắn nguồn `oneshot`, là loại bị ẩn trong cây dự án; runner hiện truyền `--source zalo` rõ ràng. Phiên cũ được sửa riêng đúng một trường nguồn sau khi dừng worker, sao lưu SQLite và kiểm tra 8 thông điệp giữ nguyên; worker đã chạy lại. API giao diện xác nhận phiên hiển thị và `pinned=true`. Đây là cuộc hội thoại gốc, không phải bản sao nhập từ export.

Trang giá chính thức tại thời điểm kiểm tra mô tả Basic miễn phí, tối đa 3 bot, 50 người/bot và 3.000 tin/tháng; đây là thông tin có thể đổi và cần kiểm tra lại trước pilot. Quota không phải cam kết rằng mọi cuộc chat đều được giao. [Trang Bot Platform](https://bot.zapps.me/)
