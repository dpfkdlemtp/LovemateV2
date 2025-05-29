import PyPDF2
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4


def create_watermark(watermark_text, watermark_pdf):
    """워터마크 PDF를 생성"""
    c = canvas.Canvas(watermark_pdf, pagesize=A4)
    width, height = A4

    c.setFont("Helvetica", 50)  # 워터마크 폰트와 크기 설정
    c.setFillAlpha(0.15)  # 워터마크 투명도 설정 (0.0 ~ 1.0)

    # 반복 간격을 넓게
    step_x = 300
    step_y = 200
    for y in range(-100, int(height + step_y), step_y):
        for x in range(-100, int(width + step_x), step_x):
            c.saveState()
            c.translate(x, y)
            c.rotate(45)
            c.drawString(0, 0, watermark_text)
            c.restoreState()

    c.save()


def add_watermark_to_pdf(input_pdf, output_pdf, watermark_pdf):
    """워터마크를 기존 PDF에 추가"""
    # 원본 PDF 열기
    with open(input_pdf, 'rb') as original_file:
        reader = PyPDF2.PdfReader(original_file)
        writer = PyPDF2.PdfWriter()

        # 워터마크 PDF 읽기
        with open(watermark_pdf, 'rb') as watermark_file:
            watermark_reader = PyPDF2.PdfReader(watermark_file)
            watermark_page = watermark_reader.pages[0]

            # 각 페이지마다 워터마크 추가
            for page_num in range(len(reader.pages)):
                original_page = reader.pages[page_num]
                original_page.merge_page(watermark_page)
                writer.add_page(original_page)

            # 워터마크가 추가된 새 PDF 저장
            with open(output_pdf, 'wb') as output_file:
                writer.write(output_file)

