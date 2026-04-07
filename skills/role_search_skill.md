# Role Search Skill — Hướng dẫn sử dụng công cụ tìm kiếm

## Khi nào nên search

Search khi bạn cần thông tin **cụ thể, cập nhật, hoặc ngoài kiến thức chung**:

- Thư viện / framework / phiên bản mới nhất (ví dụ: "Next.js 15 App Router docs", "Prisma v6 changelog")
- Best practices hiện tại cho một công nghệ cụ thể
- Giá cả, tính năng của dịch vụ cloud (AWS, Vercel, Supabase...)
- Security vulnerabilities hoặc CVE liên quan đến stack dự án
- Competitor analysis, market benchmarks
- API documentation của bên thứ 3

## Khi nào KHÔNG cần search

Không cần search khi:
- Yêu cầu chỉ cần phân tích / lập kế hoạch dựa trên thông tin đã có
- User đã cung cấp đủ context trong yêu cầu
- Câu hỏi về quy trình nội bộ / nghiệp vụ cụ thể của dự án

## Cách search hiệu quả

### 1. Query cụ thể, không chung chung
```
❌ web_search(nextjs authentication)
✅ web_search(Next.js 15 App Router authentication with NextAuth v5 2025)
```

### 2. Tìm nhiều góc độ nếu cần
```
Bước 1: web_search(Supabase vs PlanetScale pricing 2025)
Bước 2: web_search(Supabase free tier limitations production)
→ Tổng hợp kết quả từ 2 query để đưa ra khuyến nghị
```

### 3. Trích dẫn nguồn trong output
Khi dùng thông tin từ search, ghi rõ nguồn:
```
Theo tài liệu chính thức của Next.js 15 (nextjs.org/docs):
- Server Actions được stable từ v14
- ...
```

## Format output khi có search

Sau khi search xong, tổng hợp thông tin và trả lời theo format của role bạn đang đóng.  
Không liệt kê raw search results — hãy phân tích và tổng hợp thành nội dung có giá trị.
