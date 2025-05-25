from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.utils import ImageReader
from PIL import Image, ImageOps
import os
import regex

# ✅ 폰트 등록 (배포 환경에 맞게 상대 경로 사용)
pdfmetrics.registerFont(TTFont('PreLight', 'fonts/Pretendard-Light.ttf'))
pdfmetrics.registerFont(TTFont('PreRegular', 'fonts/Pretendard-Regular.ttf'))
pdfmetrics.registerFont(TTFont('PreMedium', 'fonts/Pretendard-Medium.ttf'))
pdfmetrics.registerFont(TTFont('PreSemiBold', 'fonts/Pretendard-SemiBold.ttf'))

# 유니코드 이모지 범위
emoji_range = {
    '\U0001F600', '\U0001F9FF',  # emoticons
    '\U0001F300', '\U0001F5FF',  # symbols & pictographs
    '\U0001F680', '\U0001F6FF',  # transport & map symbols
    '\U0001F1E0', '\U0001F1FF',  # flags
    '\U00002700', '\U000027BF',  # dingbats
    '\U0001F900', '\U0001F9FF',  # supplemental symbols
    '\U00002600', '\U000026FF',  # misc symbols
    '\U00002300', '\U000023FF',  # misc technical
    '\U0000200D', '\U0001F3FB', '\U0001F3FC', '\U0001F3FD', '\U0001F3FE', '\U0001F3FF'  # ZWJ + skin tones
}

def remove_emojis(text):
    # 모든 유니코드 이모지 및 결합된 이모지 제거
    return regex.sub(r'\X', lambda m: '' if any(char in emoji_range for char in m.group()) else m.group(), text)


def auto_rotate_image(image_path):
    try:
        image = Image.open(image_path)
        image = ImageOps.exif_transpose(image)
        temp_path = f"rotated_{os.path.basename(image_path)}"
        image.save(temp_path)
        return temp_path
    except:
        return image_path


def create_pdf_from_data(data: dict, output_path: str = None) -> str:
    member_code = data.get("member_code", "")
    output_path = output_path or f"{member_code}_프로필카드.pdf"
    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4

    # 경고 문구
    warning = "해당 프로필을 무단으로 열람, 사용, 공개, 배포 시 디지털 워터마킹 서비스를 통해 유출자를 추적 가능하며 유출 시 법적 책임이 발생할 수 있습니다."
    c.setFont("PreMedium", 9)
    c.setFillColor(colors.HexColor("#9E9E9E"))
    c.drawCentredString(width / 2, height - 35, warning)

    # 회원코드 박스
    c.setFillColor(colors.HexColor("#FD8F53"))
    c.roundRect(40, height - 125, 165, 24, 12, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("PreRegular", 16.5)
    c.drawCentredString(40 + 165 / 2, height - 118, f"회원코드  {member_code}")

    # ✅ 뱃지 조건부 출력
    badge_x_start = 220
    badge_y = height - 120
    badge_size = 24
    badge_spacing = 30
    badge_index = 0
    badge_fields = [
        ("verify_edu", "badges/badge_edu.png"),
        ("verify_job", "badges/badge_job.png"),
        ("verify_income", "badges/badge_income.png"),
        ("verify_asset", "badges/badge_asset.png"),
        ("verify_car", "badges/badge_car.png")
    ]
    for field, path in badge_fields:
        if data.get(field):
            badge_img = ImageReader(path)
            c.drawImage(badge_img, badge_x_start + badge_index * badge_spacing, badge_y, badge_size, badge_size, mask='auto')
            badge_index += 1

    # 기본 항목
    left_keys = ["나이", "키", "거주지", "흡연", "음주"]
    center_keys = ["학력", "회사규모", "근무형태", "종교", "MBTI"]
    right_keys = ["직무", "연봉", "자차"]
    if data.get("house") == "O":
        right_keys.append("자가")

    left_values = [data.get(k, "") for k in ["age", "height", "region", "smoking", "drink"]]
    center_values = [data.get(k, "") for k in ["edu", "company", "work", "religion", "mbti"]]
    right_values = [data.get(k, "") for k in ["job", "salary", "car"]]
    if data.get("house") == "O":
        right_values.append("O")

    def draw_centered_text(x_center, y, text, font, size, color):
        c.setFont(font, size)
        c.setFillColor(color)
        text_width = c.stringWidth(text, font, size)
        c.drawString(x_center - text_width / 2, y, text)

    left_k_center, left_v_x = 70, 105
    center_k_center, center_v_x = 230, 270
    right_k_center, right_v_x = 390, 430
    row_y_start = height - 185
    row_spacing = 27

    for i, (k, v) in enumerate(zip(left_keys, left_values)):
        y = row_y_start - i * row_spacing
        draw_centered_text(left_k_center, y, k, "PreSemiBold", 13, colors.HexColor("#FD6F22"))
        c.setFont("PreMedium", 11)
        c.setFillColor(colors.black)
        c.drawString(left_v_x, y, v)

    for i, (k, v) in enumerate(zip(center_keys, center_values)):
        y = row_y_start - i * row_spacing
        draw_centered_text(center_k_center, y, k, "PreSemiBold", 13, colors.HexColor("#FD6F22"))
        c.setFont("PreMedium", 11)
        c.setFillColor(colors.black)
        c.drawString(center_v_x, y, v)

    for i, (k, v) in enumerate(zip(right_keys, right_values)):
        y = row_y_start - i * row_spacing
        draw_centered_text(right_k_center, y, k, "PreSemiBold", 13, colors.HexColor("#FD6F22"))
        c.setFont("PreMedium", 11)
        c.setFillColor(colors.black)
        c.drawString(right_v_x, y, v)

    def draw_section(title, content, y_start):
        box_x, box_width, box_height = 40, 170, 23
        text_x, max_width, line_spacing = 45, 500, 15
        c.setFillColor(colors.HexColor("#FEE6E0"))
        c.roundRect(box_x, y_start, box_width, box_height, 12, fill=1, stroke=0)
        c.setFont("PreMedium", 16)
        c.setFillColor(colors.black)
        c.drawCentredString(box_x + box_width / 2, y_start + 5, title)

        from reportlab.pdfbase.pdfmetrics import stringWidth
        def wrap_text(text, font_name, font_size, max_width):
            lines = []
            for paragraph in text.strip().split("\n"):
                words = paragraph.strip().split(" ")
                line = ""
                for word in words:
                    test_line = f"{line} {word}".strip()
                    if stringWidth(test_line, font_name, font_size) <= max_width:
                        line = test_line
                    else:
                        lines.append(line)
                        line = word
                if line:
                    lines.append(line)
            return lines

        c.setFont("PreMedium", 13)
        c.setFillColor(colors.black)
        wrapped_lines = wrap_text(content, "PreMedium", 13, max_width)
        for i, line in enumerate(wrapped_lines):
            c.drawString(text_x, y_start - 5 - (i + 1) * line_spacing, line.strip())

    sections = [
        ("저를 소개합니다", remove_emojis(data.get("info_text", ""))),
        ("저의 매력포인트는", remove_emojis(data.get("attract_text", ""))),
        ("제 취미는요", remove_emojis(data.get("hobby_text", ""))),
        ("저의 연애스타일은", remove_emojis(data.get("dating_text", ""))),
    ]
    section_y_positions = [height - 350, height - 490, height - 590, height - 700]
    for (title, content), y in zip(sections, section_y_positions):
        draw_section(title, content, y)

    def draw_photos_page(c, image_paths):
        c.showPage()
        c.setFont("PreMedium", 9)
        c.setFillColor(colors.HexColor("#9E9E9E"))
        c.drawCentredString(width / 2, height - 35, warning)

        img_width, img_height, spacing_x, spacing_y = 195.5, 264.5, 40, 100
        total_width = img_width * 2 + spacing_x
        start_x = (width - total_width) / 2
        start_y = height - 160 - img_height

        positions = [
            (start_x, start_y),
            (start_x + img_width + spacing_x, start_y),
            (start_x, start_y - img_height - spacing_y),
            (start_x + img_width + spacing_x, start_y - img_height - spacing_y),
        ]

        for idx, image_path in enumerate(image_paths):
            if idx >= 4 or not os.path.exists(image_path):
                continue
            x, y = positions[idx]
            rotated_path = auto_rotate_image(image_path)
            img = ImageReader(rotated_path)
            c.drawImage(img, x, y, img_width, img_height, preserveAspectRatio=True, mask='auto')
            circle_radius = 30
            circle_x = x + 10
            circle_y = y + img_height - 10
            c.setFillColor(colors.HexColor("#0070C0"))
            c.circle(circle_x, circle_y, circle_radius, stroke=0, fill=1)
            c.setFillColor(colors.white)
            c.setFont("PreSemiBold", 40)
            c.drawCentredString(circle_x, circle_y - 12, str(idx + 1))

    image_paths = data.get("photo_paths", [])
    draw_photos_page(c, image_paths)
    c.save()
    # 이미지 임시 파일 삭제
    for img_path in image_paths:
        if img_path.startswith("/tmp") and os.path.exists(img_path):
            os.remove(img_path)
    return output_path
