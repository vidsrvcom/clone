# Website Inline Tool 🌐

Tool chuyên nghiệp để tải website và chuyển đổi toàn bộ CSS, JavaScript và hình ảnh thành một file HTML độc lập duy nhất.

## ✨ Tính năng mới (v2.0)

### 🚀 Hiệu suất
- **Concurrent fetching**: Tải nhiều resources song song thay vì tuần tự
- **Resource caching**: Cache thông minh tránh tải trùng lặp resources
- **Size limits**: Giới hạn kích thước file để tránh file quá lớn (mặc định: 5MB)
- **Timeout control**: Kiểm soát thời gian chờ tải trang

### 🎯 Tùy chọn linh hoạt
- `--no-css`: Bỏ qua inline CSS files
- `--no-js`: Bỏ qua inline JavaScript files  
- `--no-images`: Bỏ qua inline hình ảnh
- `--minify`: Nén HTML output (minification cơ bản)
- `--verbose, -v`: Hiển thị chi tiết quá trình
- `--max-size MB`: Giới hạn kích thước file tối đa (MB)
- `--timeout SECONDS`: Thời gian chờ tối đa khi tải trang

### 📊 Thống kê chi tiết
- Số lượng CSS/JS/Images đã inline
- Số lượng resources thất bại
- Kích thước file trước/sau
- Thời gian xử lý
- Phần trăm tăng kích thước file

### 🎨 Xử lý nâng cao
- **Srcset support**: Xử lý responsive images với srcset
- **Background images**: Inline background-image trong inline styles
- **CSS url() references**: Tự động inline fonts và images trong CSS
- **Better error handling**: Xử lý lỗi tốt hơn với messages rõ ràng
- **Progress indicators**: Emoji và progress messages trực quan

## 📦 Cài đặt

```bash
pip install httpx beautifulsoup4 playwright
playwright install chromium
```

## 🎬 Sử dụng

### Cơ bản
```bash
python inline_website.py https://example.com
```

### Với tùy chọn
```bash
# Tải và minify
python inline_website.py https://example.com output.html --minify

# Chỉ inline CSS và images (bỏ qua JS)
python inline_website.py https://example.com --no-js

# Xem chi tiết quá trình
python inline_website.py https://example.com --verbose

# Giới hạn kích thước file 10MB
python inline_website.py https://example.com --max-size 10

# Kết hợp nhiều options
python inline_website.py https://example.com result.html --no-js --minify --verbose
```

## 📋 Examples Output

### Ví dụ với verbose mode:
```
🌐 Loading https://example.com/ ...
⚙️  Processing HTML ...
  Original size: 305,509 bytes
  Found 6 CSS files to inline
  🎨 Inlining CSS: https://example.com/styles/main.css
  Found 15 JS files to inline
  📜 Inlining JS:  https://example.com/scripts/app.js
  Found 42 images to inline
  🖼️  Encoding img: https://example.com/images/logo.png
✅ Saved to index.html

============================================================
📊 Summary Statistics
============================================================
✅ CSS files inlined:     6 (0 failed)
✅ JS files inlined:      15 (0 failed)
✅ Images inlined:        42 (0 failed)
📦 Original HTML size:    305,509 bytes
📦 Final HTML size:       2,284,927 bytes
📈 Size increase:         1,979,418 bytes (648.0%)
⏱️  Total time:            12.34 seconds
============================================================
```

## 🔧 So sánh v1.0 vs v2.0

| Tính năng | v1.0 | v2.0 |
|-----------|------|------|
| Concurrent fetching | ❌ | ✅ |
| Resource caching | ❌ | ✅ |
| CLI options | ❌ | ✅ 8 options |
| Statistics | ❌ | ✅ Detailed |
| Srcset support | ❌ | ✅ |
| Background-image | ❌ | ✅ |
| Size limits | ❌ | ✅ |
| Error handling | Basic | Advanced |
| Progress indicators | Text | Emoji + Text |
| Minification | ❌ | ✅ |

## 🎯 Use Cases

1. **Archiving websites**: Lưu trữ trang web hoàn chỉnh offline
2. **Email templates**: Tạo HTML email self-contained
3. **Presentations**: Nhúng demo web vào presentation
4. **Documentation**: Lưu tài liệu web độc lập
5. **Portfolio sharing**: Chia sẻ portfolio mà không cần hosting

## ⚠️ Lưu ý

- File output có thể rất lớn (>2MB) do inline tất cả resources
- Không phù hợp với trang web động (SPA với API calls)
- External resources (CDN, APIs) không được inline tự động
- Video files không được inline (quá lớn)

## 🐛 Troubleshooting

### File quá lớn
```bash
# Bỏ qua images hoặc giảm max-size
python inline_website.py URL --no-images
python inline_website.py URL --max-size 2
```

### Timeout khi tải trang
```bash
# Tăng timeout
python inline_website.py URL --timeout 60
```

### Debug
```bash
# Sử dụng verbose mode
python inline_website.py URL --verbose
```

## 📊 Performance Tips

1. **Skip unnecessary resources**: Sử dụng `--no-js` nếu không cần JavaScript
2. **Set reasonable size limits**: `--max-size 3` để tránh file quá lớn
3. **Use minify for production**: `--minify` giảm kích thước ~10-20%
4. **Cache-friendly**: Script tự động cache để tránh tải lại

---

Made with ❤️ for web archiving
