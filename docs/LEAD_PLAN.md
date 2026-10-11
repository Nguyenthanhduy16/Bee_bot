# Kế hoạch thực thi của Lead — Bee Bot MVP v1

- **Ngày lập:** 10/10/2026.
- **Trạng thái:** bản thử cục bộ đã được ba Peer triển khai và Lead tích hợp vào Hermes/Paseo; đã kiểm chứng hội thoại nghiệp vụ trên dữ liệu giả. Chưa mở pilot thật.
- **Owner chung:** Lead dự án Bee Bot. Các owner bên dưới là vai trò cần được Lead gắn với người cụ thể trong team.

## Đợt thực thi tiếp theo — 11/10/2026

Lead đã giao việc qua Paseo, profile Peer đã cấu hình, trong workspace Bee_Bot.
Không có Peer kỹ thuật cũ phù hợp trong inventory hiện tại; ba Peer mới nhận
phạm vi độc lập. Hợp đồng điều phối tại [WORKSPACE_PROTOCOL](WORKSPACE_PROTOCOL.md)
ghi rõ cách xử lý đường dẫn hợp đồng chung bị thiếu. Không mở thêm cổng duyệt
cho các quy tắc đã chốt trong DECISIONS_TO_START_V1.

Candidate ban đầu: base `df3bd34a0decb8ef448655daef5ef8f05831f04e`, 10 file
sửa và 3 file mới của đợt profile chung/xưng hô/nhãn session. Snapshot riêng
`.bee-bot/reviews/20261011-dispatch-base`, manifest SHA256
`d27f15da59290b381ebee66dae6944143d20faa917f9a2195410881cbef7aedc`.

| Task | Peer Paseo | Owner/phạm vi | Trạng thái và cổng bàn giao |
| --- | --- | --- | --- |
| QA-11OCT / QA-SHEETS | `a47d9ff9-e93a-49cf-97d9-2859ba7ff3b6` | Review snapshot; báo cáo QA/reproducer và acceptance Sheets riêng | Review 11/10 ACCEPT, hai uncertain chỉ đọc; đang kiểm tra độc lập Core candidate và kịch bản Data |
| DATA-ZALO / DATA-FIX | `d5a14f81-f135-4c9e-aef3-20de76e04c23` | Mã Zalo/Hermes, tests tương ứng, kịch bản offline và hướng dẫn hai sender | Bàn giao 9 kịch bản, Lead đã chạy 49 tests Core/Data đạt; đã mở scope sửa findings QA |
| CORE-SHEETS / CORE-PROBE | `94b20df6-a336-4883-9b7d-018b2304f967` | Adapter/transport Sheets thử mới, tests Core/docs; probe REST riêng mới | Adapter 40 tests + demo đã bàn giao, chờ QA; đang thêm probe copy D-only có mock tests, không chạy live |
| INTEGRATE | Lead | Review chéo, tích hợp, test, báo cáo hiện có, checklist vận hành/pilot và commit đã nghiệm thu | Chỉ nhận phần có candidate/evidence rõ; không sửa scope Peer đang giữ |

Checkpoint đầu yêu cầu trong 10 phút từ giao việc; báo sớm lỗi quan trọng hoặc
dependency. Hoàn tất Peer không đồng nghĩa Lead chấp nhận; disposition ghi tại
mục này trước khi giao phần phụ thuộc. Worker thử hiện `inactive/dead`, nhật ký
ghi dừng lúc 14:48 ngày 11/10; giữ dừng trong đợt offline. Hai inbox uncertain
không phát lại. Chủ dự án đã xác nhận phản hồi danh tính thật trên Zalo; nhãn
session đã được đối chiếu DB/CLI, chưa nghiệm thu nhiều tài khoản Zalo thật.

Phần có thể làm ngay: review/sửa hồi quy, mô phỏng hai sender và nghiệp vụ,
adapter Sheets copy/synthetic cùng kiểm thử xung đột và đối chiếu. Phần cần
đầu vào riêng trước live: tài khoản Zalo thứ hai đã xác thực, workbook bản sao
với phạm vi lịch/ID được ops chấp nhận, nơi chạy thường trực và cổng nghiệm thu
ghi D thật. Chủ dự án đã xác nhận CÓ tài khoản thứ hai và workbook bản sao được
phép thử ghi; đang chờ link/ID bản sao, ID nguồn cần bảo vệ, tab/ca thử, vai của
tài khoản thứ hai và đường dẫn cấu hình truy cập riêng. `.bee-bot/source/schedule.xlsx`
là bản xuất nguồn chỉ đọc, tuyệt đối không dùng như bản sao ghi. Không dùng dữ
liệu thử thay cho các đầu vào này; tiếp tục mọi phần offline độc lập.

Chỉnh đính đầu vào: chủ dự án xác nhận workbook đã gửi CHÍNH LÀ bản sao được
phép test đọc/ghi. Ghi chú `source_id_collision` cũ đã được thay bằng
`owner_confirmed_test_copy` trong `.bee-bot/pilot-inputs.json` ngoài Git và
SHEETS_MAPPING_V1_DRAFT được sửa nghĩa “nguồn khảo sát”. Không hỏi lại URL
hoặc tính chất bản sao. Lead đã đọc export thật HTTP200: một tab lịch,
390 vị trí; chưa có thao tác ghi. Kiểm tra hiện tại chưa thấy Google credentials,
browser khả dụng hoặc connected Sheets document session; quyền ghi còn cần
đường truy cập thực tế. Người thứ hai sẽ được chủ dự án liên hệ tại bước
nghiệm thu cần họ; persona và thời điểm còn mở. Không chặn công việc synthetic.

Disposition QA-11OCT: ACCEPT review snapshot d27f15da…aedc và bằng chứng
163 tests baseline / 169 kèm reproducer. F1 shared skill_manage được Lead
xác nhận từ toolset Hermes cài tại máy; giao Data sửa cùng F2 diagnostics,
F3 preflight stale session và ràng buộc event context mutation. Hai uncertain
cũ: không có business mutation/giao nhận, đã superseded bởi lượt trả lời sau;
không replay/gửi lại và không đổi runtime rows. QA tiếp tục review độc lập
Core candidate code cc752f8d/ac70da08 và kịch bản Data. Core đã bàn giao
40 tests + demo service partial/reopen/reconcile; technical acceptance đang
chờ Lead/QA review, không coi DONE là đã chấp nhận. Lead chạy riêng 49 tests
Core/Data và demo: replacement completed; swap partial giữ reconciliation_required
qua reopen/maintenance, 2 bot writes trước/sau; ops sửa synthetic rồi reconcile
completed. QA đang kiểm tra thêm provenance chuyển sang ID/tab hợp lệ khác và
thay đổi thông tin ca giữa ghi/verify.

Workbook copy live đã đọc HTTP200 vào thư mục evidence riêng ngoài Git. Tab
quan sát `Lịch lab 0210-1610`, chọn ca sáng 12/10/2026 phòng H201, ô D278/J278
cho probe có kiểm soát và khôi phục D ban đầu sau khi verify. Giá trị D/J gốc
lưu riêng. Chưa có credential Google/API access hoặc phiên Sheets/browser
khả dụng để ghi; chưa thực hiện PUT nào. CORE-PROBE tạo script đọc trước,
PUT đúng một D, verify toàn vùng bounded/J, restore có guard và evidence;
không retry/restore tự động sau kết quả ghi chưa rõ. Không nối probe này vào
bot hoặc suy ra nghiệm thu multi-tab/roster/ID từ một lần sửa ô.

Disposition QA-SHEETS: ACCEPT findings độc lập, REJECT Core candidate đầu
cc752f8d/ac70da08. S1/S2 High: dòng canonical có STT text/trống bị bỏ sót,
header ngày không nhận diện bị giữ ngày cũ. S3/S4 Medium: chưa pin identity
workbook/tab và chưa kiểm tra lại overlap sau ghi. Đã giao Core sửa trong
scope adapter/transport/test Core; QA giữ reproducer riêng để chuyển thành
regression an toàn sau handoff. Candidate sửa cần guard per-write/readback,
không che giới hạn no-CAS. Data sửa proof nguồn actor trong scenario MCP và
assertion notification, ngoài F1–F3. Tests pass của candidate đầu không phải
bằng chứng các lỗi này đã được xử lý.

Quyết định kiến trúc được chỉnh đính: Bee Bot dùng Python Google Sheets API
transport phía sau SheetsScheduleAdapter và Bee Bot MCP hiện có. Connector
ChatGPT chỉ là lựa chọn thử thủ công ngoài hệ vận hành, không cấp quyền cho
Hermes/worker và không phải dependency triển khai. Giữ probe D278/J278 chưa
chạy cho tới khi credential API thật khả dụng trong dịch vụ.

| Task tiếp theo | Owner | Deliverable/phạm vi |
| --- | --- | --- |
| DATA-GOOGLE | Peer Data `d5a14f81` | `google_sheets_transport.py`, mock tests, setup guide; read values/metadata, pin workbook/tab, chỉ write D; đánh giá tái sử dụng OAuth/setup Google Workspace của Hermes |
| CORE-GUARD / CORE-BACKEND | Peer Core `94b20df6` | Guard `_reconcile` trong service cho S8; factory JSON/synthetic/Google test-copy; adapter không CAS; wiring worker/MCP sau QA chấp nhận candidate Data |
| QA-DATA / QA-GOOGLE | Peer QA `a47d9ff9` | Review Data fixes frozen 5c5052ac; chuyển reproducer thành regression; review Core guard và Google mock transport/backend sau handoff |

Disposition S8: ACCEPT bằng chứng QA rằng adapter-only overlap guard vẫn bị
service `_reconcile` đánh completed khi D đã khớp. Core được cấp scope hẹp
service completion guard: xác minh lịch người liên quan/coverage trước hoàn
tất, giữ reconciliation_required và reservation khi xung đột, không ghi lại.
QA giữ report/reproducer scope; không review source đang moving.

Auth thực tế: root Hermes và profile bee-zalo đều chưa có google_token.json
hoặc google_client_secret.json. Data đánh giá helper setup/format token có sẵn,
ưu tiên OAuth `--services sheets`, token/refresh ngoài Git; không viết lại
OAuth flow hoặc cho model công cụ Sheets generic. Lead quản lý dependency và
cấu hình riêng. Authorization test-copy đã có; missing credential được phân
biệt với permission, không xin lại tính chất bản sao/URL.

### Khôi phục năng lực Peer sau quota

Ba Peer Claude cũ bị quota tới 19:30; Lead không chờ hoặc nhận DONE từ thông
báo quota. Bằng chứng/candidate đã viết giữ nguyên. Chủ dự án xác nhận chuyển
sang Codex, Lead kiểm tra provider/model khả dụng và chuyển owner qua Paseo:

| Owner mới | Agent/task | Phạm vi tiếp tục |
| --- | --- | --- |
| Data/Integration Codex | `d7a5086f-d7bb-45c5-b151-5bcfa95224e6` / DATA-GOOGLE-RECOVERY | Google transport, OAuth reuse/setup guide; sửa hẹp gate MCP maintenance/reconcile khi QA reopen |
| Core Codex | `bc405016-beeb-4596-9fbb-c1e001786233` / CORE-BACKEND-RECOVERY | Adapter/guard S8 và factory; sửa thêm header STT có dữ liệu thật không được bỏ sót |
| QA Codex | `9ffc06bc-b5b2-4bca-9ecf-6521a381b6af` / QA-RECOVERY | Tiếp quản report và regression, review exact candidates độc lập |

Data candidate được đóng băng lại tại `.bee-bot/reviews/data-zalo-fixed` với
manifest `94038c08bd6adc5765a11818d885f42a255c542fb072be1d08e8e55f2b906e57`;
hash đóng gói 5c5052ac của handoff cũ chưa tái lập từ thứ tự cung cấp. Các hash
7 file sửa khớp handoff; QA dùng snapshot Lead rõ ràng thay vì khẳng định hai
manifest bằng nhau. QA reopen gate: reconcile_request/run_maintenance cũng
ghi state/outbox, đã giao Data guard context Zalo cho hai tool này. Direct demo
vẫn giữ cách dùng cũ. Code/test/report mỗi phạm vi chỉ một owner.

Hermes Google Workspace skill đã được đọc. Managed Python chạy setup.py
`--check` trả NOT_AUTHENTICATED, token chưa có. SKILL.md mô tả `--services`
nhưng script thực tế trên máy chưa nhận cờ này; không hướng dẫn dùng lệnh
không chạy được hoặc xin scope Workspace rộng. Data đánh giá reuse helper/token
refresh với Sheets-only scope; dependency google-auth[requests] đã lock/sync
trong Bee Bot. Không chạy OAuth consent hoặc ghi API khi chưa có client/token
thật được cấu hình ngoài Git.

Disposition CORE-SHEETS phase 1: ACCEPT giao diện 4 method tương thích service,
transport synthetic read_tab/write_d chỉ ghi D, roster xác thực và ID anchor.
Yêu cầu bổ sung trước chấp nhận candidate: writes fail closed khi thiếu/duplicate
anchor hoặc coverage canonical mơ hồ; kiểm tra provenance từng write; chứng
minh giới hạn lost-update/ABA của no-CAS; demo service end-to-end trên dữ liệu
synthetic và reopen/reconcile partial swap không ghi lại. Các lựa chọn ID của
Google Sheets thật chưa được kiểm chứng/duyệt, không suy rộng bảo đảm fake.
Data Peer review thiết kế chỉ đọc song song với phần Zalo độc lập.

Các quyết định được xác nhận và cách phân công Peer agent được cụ thể hóa trong [Các quyết định để bắt đầu thực hiện](DECISIONS_TO_START_V1.md). [Hợp đồng triển khai](IMPLEMENTATION_CONTRACT_V1.md) thống nhất giao diện giữa các Peer. Bản thử được phép bắt đầu; pilot thật là mốc nghiệm thu sau.

Đầu ra đợt xây đầu tiên: chat thử **qua Paseo với Hermes thật đã cài trên máy** và công cụ nghiệp vụ Bee Bot, dùng lịch/outbox cục bộ. Lead đã kiểm chứng các phiên riêng An/Bình/Dũng/vận hành, đọc danh tính, nhận thay, nghỉ, hoán đổi, issue và tra cứu. [Báo cáo kỹ thuật](ACCEPTANCE_REPORT_V1.md) phân biệt bằng chứng này với phần Zalo/Sheets thật chưa nghiệm thu.

## 1. Tiến độ và ranh giới quyết định

MVP đã chốt phạm vi nghiệp vụ: chat riêng trên Zalo cho labcoach và vận hành; nhận thay một ca, hoán đổi hai ca, nghỉ chưa có người thay, báo issue và tra cứu trạng thái. Google Sheets là lịch chính thức; D là người được phân công, J là thông tin xếp ca do vận hành cập nhật, B–J là nguồn chuẩn; ca sáng 09:00–13:00, chiều 14:00–18:00. Bot giữ nguyên J khi đổi D. Vận hành xác thực liên kết Zalo với mã labcoach; người nhận xác nhận trực tiếp và tự xác nhận không bận ngoài chương trình, bot kiểm tra lịch chương trình. Với nghỉ chưa có người thay, vận hành chấp nhận trước khi bot mời đồng thời người hợp lệ; người đủ điều kiện sớm nhất nhận vị trí. Lời mời hết hạn sau tối đa 24 giờ và không muộn hơn lúc ca bắt đầu.

Đã chọn **Hermes Agent** làm nền tảng agent; dịch vụ nghiệp vụ SQLite/MCP, JSON schedule và công cụ Hermes đã chạy cục bộ. **Bot BeeCoach** đã được tạo, token lưu riêng, tài khoản chủ bot liên kết thử với An. Tin thật “Xem lịch của tôi” đã nhận qua polling, xử lý bằng Hermes/công cụ và API xác nhận gửi phản hồi đúng lịch giả. Nghiệp vụ đổi lịch, gửi lời mời chủ động, hạn mức và webhook thật vẫn cần kiểm chứng. Bản đọc Sheets đã chuẩn hóa 390 vị trí từ một tab/kỳ lịch, chưa chứng minh bao phủ toàn bộ chương trình. Người phụ trách nghiệm thu là chủ dự án; phát triển bot/tích hợp là trách nhiệm Lead và Peer. Worker thử Zalo đã dừng ngày 11/10, dữ liệu lịch giả riêng ở `.bee-bot/zalo-demo` được giữ nguyên theo [hướng dẫn](ZALO_ONBOARDING.md).

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

## Checkpoint Codex recovery — 11/10

Lead ACCEPT phần sửa Zalo offline: QA độc lập chạy 151 test trên snapshot `94038c08…` và MCP repair `b4e602ac…`, gồm F1–F3 và F5 (cả reconcile/maintenance). Stdio và full-suite chờ mã Core/Google ổn định; chưa nâng kết quả thành nghiệm thu live. Profile đang cài chưa migrate, worker vẫn dừng.

Core handoff guard/provenance `24461139…`: 208 test của owner đạt; QA được giao review độc lập S1–S8, coverage `A=STT`, owner-confirmed copy không cần source ID bịa. Guard/provenance đã nhả scope; factory/doc vẫn Core giữ chờ Data contract. Data đang hoàn thiện Google transport mock và setup reuse token Google Workspace; credential thật vẫn thiếu. Probe D/J chưa chạy.

Commit tích hợp Zalo: `8814648` (16 file trong scope đã review; không gom Core/Google đang làm). Lead tái chạy đúng 151 test, 1 stdio deselected như QA; private workbook/key scan và diff --check sạch. Không push hoặc thay runtime. Core được giao MCP factory/context sau khi Data contract được chốt; Data giữ worker wiring riêng, không sửa trùng MCP. Câu hỏi đầu vào credential thật đã gửi chủ dự án; không phải hỏi lại quyền workbook.

## Checkpoint tích hợp Google offline và điều phối Claude — 11/10

Các Peer Codex recovery gặp quota. Phần tiếp quản đã thêm mock tests cho Google transport và nối factory/worker/Hermes profile theo cùng lựa chọn backend; JSON vẫn là mặc định. Chuyển profile JSON ↔ bản sao Google cần migration tường minh và tạo backup. Chưa chạy API/Zalo thật, chưa có credential Sheets hoặc anchor được nghiệm thu; worker vẫn dừng. Workbook thử đã được chủ dự án cho phép ghi, không đặt lại câu hỏi quyền bản sao.

Đã giao Peer Claude: QA review độc lập snapshot transport/factory/worker/service (chỉ đọc); Data bổ sung `tests/test_google_sidecar.py`; Core đồng bộ `docs/SHEETS_ADAPTER_OFFLINE.md`. Phạm vi ghi tách biệt. Lượt test tích hợp trước sửa lỗi: 312 đạt, 2 lỗi trong `tests/test_recovery_guard_qa.py` do merge columns không hashable trả `TypeError` thay vì lỗi có kiểm soát; 1 stdio test bỏ qua. Sau QA snapshot, cần sửa lỗi này, kiểm thử lại và quyết định ACCEPT/REOPEN từng bàn giao.

ACCEPT bàn giao CORE-DOC-SYNC của Peer Claude: `docs/SHEETS_ADAPTER_OFFLINE.md` hash `df41300d…` khớp nội dung code hiện tại, đã bỏ mô tả factory Google bị khóa và phân biệt mock với nghiệm thu live. Lỗi merge được sửa trong `_validated_tab` bằng kiểm tra từng tên cột trước khi tạo set; tập kiểm thử liên quan sau sửa đạt 433, bỏ qua 1 stdio test. QA độc lập đang review snapshot trước sửa (`sheets_adapter.py` hash `a3a949d9…`); cần đối chiếu phát hiện của QA với mã hiện tại trước khi chốt candidate.

ACCEPT bàn giao DATA-SIDECAR-TEST của Peer Claude: `tests/test_google_sidecar.py` hash `1d1b6323…` đúng một file được giao, 37 ca mock đạt khi chạy độc lập. Tập Google transport/sidecar/factory/MCP liên quan đạt 235, bỏ qua 1 stdio test. Kiểm thử chứng minh sidecar từ chối cấu trúc/anchor lệch và không PUT khi scope lỗi; chưa chứng minh metadata/ID ổn định trên Google thật. Transport đã có thêm kiểm tra scope và receipt trong lúc Peer làm việc, nên QA cần đối chiếu snapshot mới trước quyết định chung.

QA trả REOPEN_REQUEST cho quy trình review: ba file đổi trong lúc đọc, không thể nhận bộ hash cũ là một candidate duy nhất. ACCEPT nhận xét thiết kế phân quyền của QA trên các file ổn định; lỗi merge G2 đã sửa. Đã dừng Peer Codex Data còn ở trạng thái chạy để chặn drift, thêm `.aws` vào ignore, rồi tạo snapshot cố định `.bee-bot/reviews/google_review_20261011_frozen_v2/manifest.json` gồm bảy file với SHA-256. Giao QA Claude review lại đúng snapshot này. G3 (log qua luồng khác), G4 (vị trí/mode credential), G6 (quota đọc), G7 (dòng A bất thường) là các giới hạn cần phân loại trước live; chưa coi là nghiệm thu. Tập thử offline sau đóng băng đạt 210 ca liên quan. Full-suite ở môi trường của phiên điều phối bị `timeout` sau 45 giây tại một test treo, không coi là full-suite pass của phiên này; Peer Data/QA báo full-suite 705 đạt trong môi trường của họ.

QA ACCEPT chính xác snapshot `c61c9cc2…`: bảy file giữ nguyên hash đầu/cuối, transport + sidecar 176 test đạt, full-suite Peer QA 706 đạt. Không thấy lỗi an toàn của increment offline. QA rút lại lo ngại G3 sau khi xác minh I/O và log cùng context; G7 hiện fail-closed hai chiều. Ba điều kiện trước pilot: (V2-1) credential Sheets-only, không hứa tái sử dụng token Hermes nhiều scope; (V2-2) kiểm tra thực tế cách Google trả `updatedRange` cho tên tab tiếng Việt, tab thử hiện có dấu cách; (V2-3) enforce credential file ngoài repo, là regular file và không đọc được bởi group/world. Đã giao Data Claude xử lý V2-1/V2-3 trong transport/tests/setup guide rồi QA review hẹp. G6 quota/latency và G7 thiếu số dòng chẩn đoán vẫn là vấn đề vận hành cần đo/xử lý trước pilot, không làm sai kết quả offline.

Data bàn giao AUTH-HARDEN ba file: `google_sheets_transport.py` ca69574f…, `test_google_sheets_transport.py` a0196f8d…, `GOOGLE_SHEETS_SETUP.md` 9ce8762a…. Owner báo 155 test transport đạt, full-suite 722 đạt; phiên điều phối tái chạy tập transport/sidecar/factory 224 đạt, `git diff --check` sạch. Credential nhiều scope giờ bị từ chối trước API; tệp credential phải ở ngoài repo, regular, không qua symlink và không có quyền group/world. Đã đóng băng snapshot `.bee-bot/reviews/google_auth_harden_20261011_v1/manifest.json` hash `6b9c192e…` và giao QA Claude review hẹp; chưa ACCEPT hardening cho tới khi có phản hồi QA. V2-2 vẫn cần xác nhận receipt từ Google thật; chưa có credential để chạy.

QA ACCEPT AUTH-HARDEN đúng snapshot `6b9c192e…`: cả ba file trùng hash đầu/cuối, 155 transport tests và full-suite 722 tests đạt ở môi trường Peer; phiên điều phối kiểm tra lại tập liên quan 224 đạt. V2-1/V2-3 đã đóng cho increment offline. QA còn ghi nhận hai giới hạn thấp: đường dẫn parent có thể bị thay trong khoảng kiểm tra–mở, và hardlink ngoài repo trỏ cùng inode với file trong repo. Đã sửa mô tả code/tài liệu để không hứa bảo đảm tuyệt đối; vận hành phải giữ thư mục credential private `0700`. Không có credential thật, chưa chạy API thật. Trước pilot vẫn cần xác nhận V2-2 receipt cho tab thực tế, anchor/roster/coverage, chi phí đọc và các quy tắc sửa đồng thời.

## Checkpoint Sheets live có giới hạn — 11/10/2026

Các câu “chưa có credential/chưa chạy API” ở những checkpoint lịch sử phía trên
đã được thay thế bởi checkpoint này. Chủ dự án đã cung cấp service-account JSON,
bật Google Sheets API cho project thử và chia sẻ workbook bản sao. Khóa được
lưu ngoài Git trong thư mục riêng `0700`, file `0600`; đường dẫn nằm ở cấu hình
riêng và không ghi vào tài liệu/commit. Tệp tải lên gốc cũng được thu hẹp về
`0600`. Bot/worker vẫn dừng, cấu hình probe trở lại `write_enabled=false`.

Service account xác thực thành công và Sheets metadata GET trả HTTP 200: đúng
tab cho phép, gid đã đối chiếu, grid 1000 dòng × 20 cột. Probe đọc chỉ một
lần GET trả `PRECONDITIONS_MATCH` cho D278/J278. Probe execute dùng ba GET,
hai PUT: chỉ D278 thay đổi tạm, J278 giữ nguyên, sau đó D278 và toàn vùng
bounded được xác nhận khôi phục. Một PUT cùng giá trị tiếp theo trên D278
trả receipt HTTP 200 với quoted `updatedRange` và ba số lượng cập nhật đều 1;
D/J không đổi sau đọc lại. V2-2 đã được kiểm chứng đúng với tab tiếng Việt này.
Giá trị ô và bằng chứng thô chỉ có trong `.bee-bot/` riêng, không đưa vào Git.

Đường đọc của transport hiện tại đã chạy trên API thật: A–J có 390 dòng STT
số, 390 ứng viên theo coverage, 434 merge liên quan và không có ứng viên dư;
một lượt đọc đo được khoảng 0,65 giây. Chưa có developer metadata nào trên
workbook, vì vậy chưa có stable row anchor cho runtime. Phép thử D đơn lẻ
không chứng minh roster, ánh xạ Zalo, lịch chương trình đầy đủ, sửa đồng thời,
hoán đổi một phần, giới hạn quota hay phục hồi service. Chưa bật backend Google
cho worker và chưa mở pilot.

Lead tiếp theo cần chốt với ops cơ chế ID vị trí (metadata hoặc sidecar thử),
roster labcoach ↔ tên trên Sheets đã xác thực, phạm vi các workbook/tab/kỳ lịch
để kiểm tra xung đột, quy tắc khi vận hành sửa D đồng thời và xử lý ghi chưa rõ.
Sau khi có các đầu vào đó, QA nghiệm thu backend đọc/ghi với anchor trên bản
sao, rồi mới lên lịch thử tài khoản Zalo thứ hai và quyết định mức pilot.

## Checkpoint mã dòng trên bản sao — 12/10/2026

Chủ dự án chọn thử mã ẩn gắn vào dòng của bản sao và cho biết chưa có tệp roster
labcoach đã xác thực. Lead thử trên tab tạm dữ liệu giả: gắn mã, chèn/di chuyển
dòng, xác nhận mã đi theo, rồi xóa tab và mã. Lần thử đầu trên dòng lịch thật
phát hiện bug thực tế: Google trả row metadata trong `GridData.rowMetadata`,
không nằm ở các mảng metadata mức workbook/tab mà transport trước đó đọc.
Mã thử đã được gỡ. Đã sửa `google_sheets_transport.py` để yêu cầu và kiểm tra
metadata ở đúng vị trí, thêm mock regression cho shape thật và vị trí sai;
226 test transport/sidecar/factory đạt, 135 test MCP/adapter/QA đạt khi bỏ
1 stdio test bị treo trong môi trường phiên này. Thử lại một mã trên dòng 278
đã được backend đọc đúng và xóa sạch sau đó.

Sau khi kiểm tra lại cấu trúc và coverage, Lead chuẩn bị kế hoạch private rồi
gắn `PROJECT` row metadata key `bee_bot_pos_v1` cho đúng 390 dòng vị trí trong
một `batchUpdate`. Google trả receipt; đọc lại và `read_tab()` xác nhận đủ 390
mã tại đúng dòng. Không sửa ô dữ liệu. Gọi live `write_d` của transport cho
anchor D278, ghi lại cùng giá trị hiện tại, được receipt hợp lệ; toàn bộ A–J
đọc lại giống trước, J không đổi. Metadata plan và ID chỉ lưu ngoài Git.

Đã lập CSV riêng ngoài Git gồm 51 tên D khác nhau từ 346 vị trí có tên, để
ops bổ sung mã người, liên kết Zalo, vai trò và xác thực. CSV này chỉ là ứng
viên, chưa được dùng làm trusted roster. Worker/backend runtime vẫn khóa ghi;
chưa nghiệm thu thao tác sort/copy-paste, sửa D đồng thời, lịch chương trình
đầy đủ, hoán đổi nhiều ô hoặc người dùng Zalo thứ hai. Pilot vẫn đóng.

Chủ dự án chấp nhận danh sách 51 tên **tạm thời** để tiếp tục kiểm thử đọc.
Lead tạo cấu hình riêng ngoài Git với 51 mã người tạm `inactive`, `write_enabled`
false và allowlist ghi rỗng. Adapter và factory đọc live đủ 390 phân công,
0 diagnostic cấu trúc; cấu hình chưa được cài vào worker. Đây chưa phải xác
thực danh tính người hoặc liên kết Zalo. Khi rà soát context MCP, phát hiện
`writable` trước đó chỉ phản ánh cấu trúc, có thể báo true dù transport khóa
ghi. Đã sửa context Google để yêu cầu thêm cổng ghi và anchor allowlist của
transport; 219 test MCP/transport/factory đạt, bỏ 1 stdio test treo đã biết.

## Checkpoint Zalo với bạn giả lập Hermes — 12/10/2026

Một tài khoản Zalo của chủ dự án đã thử vai `duy` trên lịch JSON cô lập;
`binh` là persona Hermes riêng dùng cùng DB. Worker Zalo cũ đang dừng nên tin
gửi trước khi mở lượt thử không vào inbox cục bộ. Sau khi gửi lại, bot hỏi xác
nhận, nhận xác nhận của chủ dự án và tạo yêu cầu thay A001. Bình giả lập gọi
MCP xác nhận trực tiếp; yêu cầu hoàn tất, A001 chuyển `duy` → `binh`, revision
tăng 1 và J giữ nguyên. Inbox thử có 2 `completed`, giao nhận có 4 `sent`,
không có mục `uncertain`; worker thử đã kết thúc. Chi tiết bằng chứng và giới
hạn ở [nghiệm thu Zalo](ZALO_TWO_SENDER_ACCEPTANCE.md#7-lượt-thử-một-người-zalo-và-bạn-giả-lập-hermes--12102026).

Lượt này chứng minh một người thật trên Zalo phối hợp với một người giả lập qua
Hermes trên lịch JSON. Nó chưa chứng minh hai người Zalo thật, vận hành thường
trực hoặc ghi Sheets từ bot. Pilot vẫn đóng; danh sách người trên Sheets còn
tạm và chưa xác thực liên kết Zalo.
