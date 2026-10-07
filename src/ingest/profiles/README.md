# profiles — tri thức nguồn dưới dạng data, không phải code

## Trách nhiệm

Load và validate file YAML: `configs/settings.yaml` (toàn cục) và
`configs/profiles/<nguồn>.yaml` (riêng nguồn). Engine không bao giờ chứa
`if source == ...`; mọi khác biệt nguồn (flow, alias, anchor, pattern rác)
nằm ở đây, review qua PR như code.

## Input / Output

- Input: tên profile hoặc path file YAML.
- Output: dict đã validate schema tối thiểu (origin, flows, aliases...),
  merge với settings toàn cục.

## Workflow

Đọc YAML → kiểm tra key bắt buộc → merge settings → trả config cho `pipeline`.
Profile sai schema thì fail nhanh lúc load, không fail giữa chừng khi crawl.

## Interface

- `pipeline` và các module nhận config đã load; không module nào tự đọc file.
- Thêm nguồn mới = thêm 1 file YAML + fixture test, không sửa engine.

## Quyết định kỹ thuật

- PyYAML đọc/sửa dễ hơn TOML với cấu trúc lồng (alias list, flow steps);
  xem thêm `beautifulsoup4` (parse) trong `pyproject.toml`.
- Trạng thái field mới (`proposed`/`canonical`) để dành cho phase vocab sau,
  hiện tại profile chỉ chứa flow, alias, anchor và pattern lọc.
- Triển khai ship cả thư mục `configs/` cùng code (data, không phải code);
  loader tìm theo thứ tự: path truyền vào → env `TOURCRAWL_CONFIGS` →
  configs cạnh package (checkout) → configs ở thư mục hiện hành.
