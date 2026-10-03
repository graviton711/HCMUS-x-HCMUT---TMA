# cli — một cửa vào duy nhất cho team

## Trách nhiệm

Parse argv, load config, gọi `pipeline`, in metrics ra stdout, trả exit code.
Không logic nghiệp vụ ngoài dòng lệnh.

## Input / Output

- `tour-crawl <url> [-o out.csv] [--profile vietravel] [--no-browser]`
- `tour-crawl --batch urls.csv [...]` / `--sitemap <url> [...]`
- Exit code: 0 ok, 1 lỗi run, 2 input/config sai (khớp taxonomy validate).

## Interface

- Lớp mỏng trên `pipeline`; mọi behavior test ở pipeline, cli chỉ test parse args.

## Quyết định kỹ thuật

- Stdlib `argparse` (không thêm dependency CLI); `.env` đọc bằng loader
  stdlib nội bộ, không in secret ra log bao giờ.
