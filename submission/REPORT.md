# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Do Viet Hoang
- **MSSV:** 2A202602882
- **Lớp:** K4-L3B
- **Repository URL:** https://github.com/demoAccount212/K4-L3-DAY13-DoVietHoang-2A202602882-Monitoring-LLMOps
- **Commit SHA cuối:** 1b09812443a005759fa8d052ada5291bdb3715fc
- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602882`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/01-pytest.png` |
| Log validator | `evidence/02-log-validator.png` |
| Dashboard validator | `evidence/03-dashboard-validator.png` |
| Structured log | `evidence/04-structured-log.png` |
| PII redaction | `evidence/05-pii-redaction.png` |
| Trace list | `evidence/06-trace-list.png` |
| Trace waterfall | `evidence/07-trace-waterfall.png` |
| Trace metadata | `evidence/08-trace-metadata.png` |
| Prompt versions | `evidence/09-prompt-versions.png` |
| Prompt rollback | `evidence/10-prompt-rollback.png` |
| Dashboard runtime | `evidence/11-dashboard-overview.png` |
| Incident metric | `evidence/12-incident-metric.png` |
| Incident log | `evidence/13-incident-logs.jsonl` |
| Incident trace | `evidence/14-incident-trace.png` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | ≥80/100 (yêu cầu) | **100/100** (33 records, 17 correlation IDs) | Đủ schema, enrichment, correlation_id, PII scrub |
| `validate_dashboard.py` | 6 panel (yêu cầu) | **6/6 panel** | Đúng contract `config/dashboard.yaml` |
| `pytest` | 24 test | **24 passed** | Không fail, không skip |
| Số traces hợp lệ | ≥10 (yêu cầu) | **143 traces** trong ngày (root + retrieval + generation) | Project `day13-k4-l3b-2A202602882` |
| Số PII leak | 0 | **0** | Validator phát hiện 0 trong toàn bộ log |
| Latency P95 / TTFT P95 | P95 1753ms, TTFT 50ms (`config/slo.yaml`) | P50 ≈152ms, TTFT P95 50ms; đỉnh incident **2654ms** | Incident `rag_slow` đẩy P95 vọt lên 2654ms (ngưỡng 2000ms) |
| Retrieval success rate | 100% | **100% (15/15)** | `tool_success=true` tất cả request |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** `CorrelationIdMiddleware` ở tầng ASGI: nhận header `x-request-id` hợp lệ từ client hoặc sinh mới `req-<8 hex>` (uuid4), gắn vào `request.state` và đặt vào **contextvars** mà `structlog` đang đọc — nhờ đó mọi log line trong cùng một request tự động mang chung `correlation_id` (không phải truyền tay qua từng hàm). Response trả về `x-request-id` và `x-response-time-ms` để client tự đối chiếu được.
- **Các metadata được ghi vào structured log:** schema yêu cầu `ts`, `level`, `service`, `event`, `correlation_id`; enrichment từ contextvars: `user_id_hash`, `session_id`, `feature`, `model`, `env`; số liệu của request: `latency_ms`, `ttft_ms`, `tokens_in/out`, `cost_usd`, `quality_score`, `tool_name`, `tool_success`, `payload` (chỉ preview đã cắt ngắn).
- **Cách bảo đảm PII được scrub trước khi ghi:** `app/pii.py` định nghĩa regex cho `email`, `phone_vn`, `cccd`, `credit_card` và `scrub_text()` thay bằng `[REDACTED_EMAIL]`, `[REDACTED_PHONE_VN]`, … Processor `scrub_event()` trong `app/logging_config.py` chạy trên **mọi field** của event (kể cả tên event) trước khi `JsonlFileProcessor` ghi ra `data/logs.jsonl` — PII không bao giờ chạm tới file.
- **Cách kiểm chứng kết quả:** `python scripts/validate_logs.py` → **100/100**, "Potential PII leaks detected: 0"; kiểm tra thủ công các dòng có email/SDT trong input vẫn ghi `[REDACTED_*]`. Xem `evidence/02-log-validator.png`, `evidence/04-structured-log.png`, `evidence/05-pii-redaction.png`.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** traces nằm trong project Langfuse **`day13-k4-l3b-2A202602882`**; tôi tự chạy `load_test.py` để sinh 143 traces trong ngày (yêu cầu ≥10) và mỗi trace có `metadata.correlation_id` khớp với dòng log tương ứng trong `data/logs.jsonl`. Ảnh `evidence/06`–`10`, `14` đều chụp từ project này, không mở trang API Keys.
- **Cấu trúc root/retrieval/generation observations:** root `lab-agent-run` (type AGENT) → child `retrieval` (type RETRIEVER, gắn bằng `@observe(name="retrieval", as_type="retriever")` trong `mock_rag.retrieve`) → child `generation` (type GENERATION, `@observe(name="generation")` trong `FakeLLM.generate`) có `model`, `usageDetails`, `costDetails`, link prompt `day13-chat` v1. Không capture input/output thô (`capture_input/output=False`); prompt object được nối vào trace bằng `propagate_attributes(prompt=...)`.
- **Cách nối trace với log:** `correlation_id` — ghi vào root metadata của trace và là field bắt buộc của mọi dòng log; tra cứu bằng `correlation_id` là đủ để mở đúng trace của request đó (dùng cho cả điều tra challenge).
- **Prompt name:** `day13-chat` (text prompt, template `{{feature}}` / `{{docs}}` / `{{message}}`), đọc qua `resolve_prompt()` theo `LANGFUSE_PROMPT_NAME` + `LANGFUSE_PROMPT_LABEL` trong `.env`.
- **Version/label baseline:** v1 — labels `baseline` + `production`.
- **Version/label candidate:** v2 — label `candidate` (thêm dòng "Trả lời ngắn gọn.").
- **Trace ID của mỗi version:** v1 = `e2ed301b6595c662f2663a5961be7cd8` (req-basel01) · v2 = `90f9bdf72a52784ff6bc34378e19cfa5` (req-cand001) · promote production→v2 = `00fbe5b7aa8127d76b2338e5b53bd24a` (req-prom001) · rollback production→v1 = `83afc36068711cf26e2b52603f63ddeb` (req-roll002).
- **Cách promote và rollback `production`:** chạy `python scripts/prompt_labels.py promote` (chuyển label `production` sang v2) hoặc `rollback` (trả về v1) — script dùng Langfuse SDK để dời label, không sửa text; sau đó gửi 1 request test và xác nhận qua trace metadata (`prompt_version`/`prompt_label`). Trạng thái cuối: `baseline→v1, candidate→v2, production→v1`. Xem `evidence/09-prompt-versions.png`, `evidence/10-prompt-rollback.png`.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** Streamlit `scripts/dashboard.py` (venv riêng `.venv-dashboard`, không động vào venv của API), nguồn `data/logs.jsonl` theo contract `config/dashboard.yaml`: (1) **Latency** — P50/P95/P99 + TTFT P95, ms, ngưỡng 3000ms; (2) **Traffic** — requests/phút, bar chart + ngưỡng; (3) **Errors** — error rate % và retrieval success %, ngưỡng 2%; (4) **Cost** — USD lũy kế/ngày, ngưỡng 2.5; (5) **Tokens** — token lũy kế, ngưỡng 50000; (6) **Quality** — điểm quality trung bình, ngưỡng 0.75. Mọi panel: cửa sổ 60 phút, refresh 30 giây, đường threshold đỏ đứt lấy từ YAML. Chạy: `streamlit run scripts/dashboard.py --server.port 8501`. Xem `evidence/11-dashboard-overview.png`, `evidence/12-incident-metric.png`.
- **SLO và lý do chọn:** **99.5% request có latency P95 ≤ 3000ms trong 28 ngày** (`config/slo.yaml`). Chọn vì baseline P50 ≈152ms, P95 thường ≤ ~1.8s (kể cả cold start) nên 3000ms là ngưỡng chặt nhưng đạt được — buộc hệ thống phải giữ retrieval/LLM nhanh; 28 ngày là cửa sổ đủ dài để đo ổn định, tránh phản ứng với vài request chậm lẻ tẻ.
- **Cách tính error budget:** Error budget = 100% − SLO = **0.5%**. Với 10,000 request/28 ngày, tối đa **50 request** được phép lỗi hoặc chậm hơn ngưỡng; ví dụ incident challenge vừa qua: 5/15 request chậm vượt ngưỡng đã tiêu ~33% budget chỉ của riêng cửa sổ đo đó — dùng để quyết định có nên dừng phát hành không.
- **Ba alert và runbook tương ứng:** (`config/alert_rules.yaml`, runbook `docs/alerts.md`)
  1. **HighLatencyP95** — p95 > 3000ms trong 5m · severity `high` · owner `student-2A202602882` · Slack `#k4-l3b-alerts` · runbook Alert 1: Metrics → lọc log theo `correlation_id` → mở trace → xác định span chậm.
  2. **ErrorRateHigh** — error rate > 2% trong 5m · severity `critical` · owner `student-2A202602882` · Slack `#k4-l3b-alerts` · runbook Alert 2: đếm `request_failed` theo `error_type` → trace lỗi.
  3. **CostSpike** — daily cost > $2.5 · severity `medium` · owner `student-2A202602882` · Slack `#k4-l3b-alerts` · runbook Alert 3: so `cost_usd`/`tokens_out` theo request → trace có `prompt`/usage bất thường.

> Ví dụ cách viết error budget: "SLO 99.5% trong 28 ngày nghĩa là error budget 0.5%. Nếu workload có 10,000 request thì tối đa 50 request được phép lỗi hoặc chậm hơn ngưỡng SLO."

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1` (cohort K4, incident `rag_slow`, feature bị ảnh hưởng `monitoring`, ngưỡng latency 2000ms)
- **Khoảng thời gian điều tra:** 2026-09-30 04:34–04:37 UTC (11:34–11:37 UTC+7); thời điểm bất thường 04:36:07–04:36:21 UTC
- **Triệu chứng từ metrics:** Panel **Latency** cho thấy 5/5 request `feature=monitoring` có `latency_ms` = 2652–2654ms so với baseline P50 ≈ 152ms (gấp ~17 lần, vượt ngưỡng 2000ms của challenge) tại 04:36:10–04:36:20 UTC. TTFT không đổi (50ms); panel Errors bình thường — error rate 0%, tất cả HTTP 200, `tool_success=true` → đây là triệu chứng **chậm chứ không lỗi**. (Không dùng thời gian client in ra bởi `load_test.py --concurrency 5` — các request xếp hàng nên số phía client cao hơn thực tế.)
- **Log line và correlation ID liên quan:** `data/logs.jsonl`, `event=response_sent`, `correlation_id=req-f3d3927f`, `latency_ms=2654`, `ttft_ms=50`, `feature=monitoring`, `ts=2026-09-30T04:36:10.047003Z` (với `request_received` cùng ID lúc 04:36:07.390895Z). Xem `evidence/13-incident-logs.jsonl`.
- **Trace ID và span gây ảnh hưởng:** Trace `1f9d341c6be2d17418045752ee22951f` (cùng `correlation_id=req-f3d3927f`): root `lab-agent-run` 2655ms → span **`retrieval` 2501ms (94% thời gian)**, span `generation` chỉ 153ms (model/usage/cost bình thường). Bốn trace còn lại của challenge giống hệt: `b0a848f1def6e427d2c271769820a74d`, `f69eab8753f04f9dd4971b927d38f9aa`, `e6ff4e82f67644a9de55f9f0e17e8c67`, `8962baab446d802fcae484a4f632f66d` — retrieval 2501ms, generation ~151ms. Xem `evidence/14-incident-trace.png`.
- **Root cause:** Span `retrieval` (thành phần RAG) bị chậm ~2500ms/request, chiếm 94% thời gian xử lý; LLM generation và tool đều hoạt động bình thường (không lỗi, không token tăng). Ba bằng chứng — metric (latency P95 2654ms), log (`req-f3d3927f`, `latency_ms=2654`, `ttft_ms=50`), trace (`retrieval` 2501ms) — cùng trỏ vào một nguyên nhân: **độ trễ trong truy vấn retrieval, không phải ở model**.
- **Fix action:** Tắt sự cố đang chạy (`python scripts/inject_incident.py --scenario rag_slow --disable`), xác nhận qua `/health` mọi incidents về `false`, chạy lại `load_test.py` và quan sát latency trở về baseline ~152ms.
- **Preventive measure:** (1) Alert **HighLatencyP95** trong `config/alert_rules.yaml` (p95 > 3000ms trong 5m, severity high) kèm runbook `docs/alerts.md` — Alert 1 với chuỗi **Metrics → Logs → Traces**; (2) canh span `retrieval` riêng (ngưỡng ~1000ms) để phát hiện sớm RAG chậm trước khi vượt SLO; (3) benchmark định kỳ retrieval với load test baseline để có số so sánh khi điều tra. Xem `evidence/12-incident-metric.png`.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** Dùng **`correlation_id` làm chìa khóa xuyên suốt** — sinh ở middleware, truyền qua **contextvars** để structlog tự gắn vào mọi dòng log, đồng thời ghi vào metadata của Langfuse trace. Lý do: nếu không truyền qua contextvars thì correlation_id chỉ sống trong 1 request handler và bị mất khi code gọi qua nhiều tầng; nhờ quyết định này mà metrics → logs → traces nối được với nhau bằng một khóa duy nhất, điều tra incident chỉ mất vài phút.
- **Một lỗi/blocker đã gặp:** Dashboard báo `KeyError: ['minute']` khi chạy thật trên Streamlit. Nguyên nhân: **pandas 3.x làm mất index name sau `reindex()`** nên `reset_index()` tạo cột `"index"` thay vì `"minute"`; quan trọng hơn, **test "smoke" bằng `python scripts/dashboard.py` ở bare mode của Streamlit không chạy body decorator `@st.fragment`** nên đã "pass ảo". Đã reproduce lỗi bằng script độc lập → thêm `.rename_axis("minute")` → dựng lại smoke test patch `st.fragment` về identity và ép `chart.to_dict()` để serialize thật, qua đó bắt thêm 2 bug nữa (`getattr(mark)` phải là `mark_line/mark_bar`; merge 2 frame cùng cột `series/value` bị đổi tên `_x/_y`).
- **Cách tìm nguyên nhân và xử lý:** Áp dụng đúng chuỗi trên incident thật: (1) **Metrics** — panel Latency cho 5 request `monitoring` 2652–2654ms vs baseline 152ms lúc 04:36 UTC, TTFT và error rate bình thường; (2) **Logs** — lọc `data/logs.jsonl` chọn `correlation_id=req-f3d3927f` (`latency_ms=2654`, `ttft_ms=50`); (3) **Traces** — mở trace `1f9d341c6be2d17418045752ee22951f` cùng correlation_id: span `retrieval` 2501ms trong root 2655ms, `generation` chỉ 153ms; (4) **Root cause** = retrieval chậm, không phải model. Fix: tắt incident, verify `/health` + load test baseline trở lại; preventive: alert HighLatencyP95 + runbook.
- **Cách hiểu luồng Metrics → Logs → Traces:** Metrics trả lời **"cái gì bất thường và khi nào"** (latency P95 vọt 2654ms tại 04:36) nhưng không biết request nào; Logs trả lời **"request nào, chi tiết gì"** — tìm dòng có `latency_ms` cao và lấy `correlation_id`; Traces trả lời **"ở đâu trong chuỗi xử lý"** — so sánh thời gian các span của cùng correlation_id để biết retrieval hay generation chiếm thời gian. `correlation_id` + timestamp là hai mắt xích nối ba nguồn; chỉ khi cả ba cùng trỏ về một nguyên nhân mới được kết luận root cause, không được đoán trước khi xem trace.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** Prompt version + label `production` cho phép promote/rollback trong vài lệnh — phiên bản nào đang phục vụ traffic luôn rõ ràng và quay lại bản cũ được ngay khi lỗi. Token/cost theo từng request cho phép phát hiện chi phí tăng bất thường (CostSpike) trước khi hóa đơn vượt budget. SLO + error budget định nghĩa trước "chấp nhận bao nhiêu tồi tệ" để quyết định dừng phát hành dựa trên số liệu chứ không cảm tính. Nhìn chung: rollback (prompt và release) là chốt an toàn cuối cùng của hệ thống.
- **Điều quan trọng nhất đã học:** *Không thấy thì không sửa được* — một pipeline quan sát tốt (log sạch + correlation_id + trace + dashboard + alert) biến sự cố bí ẩn thành bằng chứng nối sẵn với nhau; kỹ thuật phần mềm chỉ nhanh bằng khả năng trả lời "cái gì đang xảy ra" của hệ thống.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** (1) Alert rules mới là YAML + runbook, chưa có scheduler thật gửi Slack; (2) dashboard đọc trực tiếp `data/logs.jsonl` trong cửa sổ 60 phút — ngoài cửa sổ là mất (chưa có TSDB); (3) số liệu baseline chỉ từ ~15 phút chạy lab, SLO 28 ngày chưa đủ dữ liệu thật để tính error budget thực; (4) cost/quality đến từ mock LLM nên chỉ mang tính mô phỏng pipeline quan sát.

## 9. Checklist trước khi nộp

- [x] Kết quả và evidence thuộc commit SHA cuối. _(đánh dấu sau khi commit CP2+CP3 và chạy lại bộ verifiers)_
- [x] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [x] Incident evidence nối đúng metric → log → trace.
- [x] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [x] Repository chạy lại được theo README.
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [x] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
