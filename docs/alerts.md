# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert mẫu để tham khảo

Ví dụ dưới đây minh họa mức độ cụ thể cần có. Học viên không cần copy nguyên, nhưng ba alert trong bài nộp nên rõ ràng tương tự: điều kiện là gì, kéo dài bao lâu, ảnh hưởng tới user ra sao và người trực cần kiểm tra gì trước.

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn trước khi nhận câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard latency để xác nhận P95/P99 và khoảng thời gian tăng.
  2. Lọc `data/logs.jsonl` trong khoảng đó, lấy một `correlation_id` có `latency_ms` cao.
  3. Mở trace cùng `correlation_id` trên Langfuse, so sánh các span chính để xác định bước nào bất thường.
- Mitigation tạm thời: dựa trên evidence thực tế để rollback prompt, khôi phục cấu hình liên quan, tắt practice scenario hoặc giảm tải khi demo.
- Owner: `student-<MSSV>`

## Alert 1

- Tên: `HighLatencyP95`
- Severity: `high`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: SLO chính `fast_successful_requests` — latency P95 của `response_sent.latency_ms` phải ≤ 3000ms
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` liên tục trong 5 phút
- Ảnh hưởng tới người dùng: người dùng phải chờ quá lâu trước khi nhận câu trả lời, vi phạm SLO và ăn dần error budget (0.5%)
- Ba bước kiểm tra đầu tiên:
  1. **Metrics** — mở dashboard, panel *Latency percentiles and TTFT*, xác nhận P95/P99 và khoảng thời gian bắt đầu tăng; so sánh với baseline p95=1753ms.
  2. **Logs** — lọc `data/logs.jsonl` trong khoảng đó, tìm `event == "response_sent"` có `latency_ms` cao, lấy một `correlation_id` (ví dụ so sánh `ttft_ms` vs `latency_ms` để biết chậm ở LLM hay ở retrieval).
  3. **Traces** — mở trace cùng `correlation_id` trên Langfuse, so sánh thời gian các span `retrieval` và `generation` để xác định bước nào bất thường (vd: retrieval chậm do `rag_slow`, hoặc fetch prompt Langfuse timeout).
- Mitigation tạm thời: nếu trace cho thấy retrieval chậm → tắt practice scenario `rag_slow` / khôi phục vector store; nếu do fetch prompt timeout → bật lại prompt cache hoặc pre-warm prompt khi khởi động; nếu do mẫu (pattern) thật → giảm tải khi demo và mở ticket xử lý gốc.
- Owner: `student-2A202602882`

## Alert 2

- Tên: `ErrorRateHigh`
- Severity: `critical`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: guardrail `error_rate_pct_max: 2` và SLO chính (request lỗi không phải `response_sent` nên phá error budget)
- Điều kiện và thời gian duy trì: `count(request_failed) / count(request_received) * 100 > 2%` liên tục trong 5 phút
- Ảnh hưởng tới người dùng: một tỉ lệ đáng kể request trả lỗi (5xx) hoặc fail — người dùng không nhận được câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. **Metrics** — mở dashboard, panel *Error rate and retrieval success*, xác nhận error rate vượt 2% và retrieval success có giảm dưới 90% hay không.
  2. **Logs** — lọc `data/logs.jsonl` lấy `event == "request_failed"`, đếm theo `error_type` để biết lỗi phổ biến nhất và lấy vài `correlation_id` tương ứng.
  3. **Traces** — mở các trace cùng `correlation_id` trên Langfuse, tìm span báo lỗi (retrieval fail = vector store timeout, generation fail = LLM error) và đọc `status_message`.
- Mitigation tạm thời: nếu lỗi do practice scenario (`tool_fail`) → tắt scenario ngay; nếu retrieval fail → khôi phục vector store / rollback cấu hình vừa thay đổi; nếu lỗi thật → rollback phiên bản gần nhất và thông báo trên kênh Slack.
- Owner: `student-2A202602882`

## Alert 3

- Tên: `CostSpike`
- Severity: `medium`
- Duration: `10m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: guardrail `daily_cost_usd_max: 2.5` (ngân sách chi phí mỗi ngày)
- Điều kiện và thời gian duy trì: `sum(cost_usd)` trong cửa sổ trượt 24 giờ > 2.5 USD, duy trì 10 phút (chống nhiễu do một request lớn bất thường)
- Ảnh hưởng tới người dùng: không lỗi trực tiếp, nhưng nếu kéo dài sẽ vượt ngân sách — dịch vụ có thể phải giảm chất lượng hoặc bị cắt nguồn lực
- Ba bước kiểm tra đầu tiên:
  1. **Metrics** — mở dashboard, panel *Cost over time*, xác nhận tổng chi phí 24h vượt 2.5 USD và chi phí/phút có nhảy bất thường không.
  2. **Logs** — lọc `data/logs.jsonl` theo `event == "response_sent"` tìm request có `cost_usd` hoặc `tokens_out` bất thường (gấp 4× bình thường = dấu hiệu `cost_spike`); lấy `correlation_id`.
  3. **Traces** — mở trace cùng `correlation_id` trên Langfuse, xem span `generation`: `usage` (tokens output) và `cost` có đúng bất thường không, so với prompt version đang dùng.
- Mitigation tạm thời: nếu do practice scenario (`cost_spike`) → tắt scenario; nếu do prompt version mới (sau promote) sinh token dài hơn → rollback label `production` về version trước; nếu do traffic thật → rà soát rate limit / mẫu truy vấn bất thường.
- Owner: `student-2A202602882`
