from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.enums import TA_LEFT

BRAND_BLUE = colors.HexColor("#1b263b")
BRAND_LIGHT_GREY = colors.HexColor("#e0e1dd")
BRAND_DARK_GREY = colors.HexColor("#0d1b2a")

class PDFBuilder:
    def __init__(self, response):
        self.p = canvas.Canvas(response, pagesize=A4)
        self.width, self.height = A4
        self.y = self.height - 50
        self.styles = getSampleStyleSheet()
        self.cell_style = self.styles["Normal"]
        self.cell_style.fontName = "Helvetica"
        self.cell_style.fontSize = 9
        self.cell_style.leading = 11
        self.cell_style.alignment = TA_LEFT

    def heading(self, text, size=16):
        self.y -= 10
        self.p.setFont("Helvetica-Bold", size)
        self.p.setFillColor(BRAND_BLUE)
        self.p.drawString(50, self.y, text)
        self.p.setFillColor(colors.black)
        underline_y = self.y - 3
        self.p.line(50, underline_y, 550, underline_y)
        self.y -= size + 15

    def subheading(self, text, size=13):
        self.y -= 8
        self.p.setFont("Helvetica-Bold", size)
        self.p.drawString(50, self.y, text)
        self.y -= size + 8

    def text(self, text, size=11):
        self.p.setFont("Helvetica", size)
        self.p.drawString(50, self.y, text)
        self.y -= size + 6

    def hr(self):
        self.p.setLineWidth(0.5)
        self.p.line(50, self.y, 550, self.y)
        self.y -= 12

    def shaded_box(self, lines, padding_top=18, padding_bottom=5, line_height=15):
        # Calculate dynamic height
        content_height = len(lines) * line_height
        total_height = padding_top + content_height + padding_bottom

        # Draw background rectangle
        self.p.setFillColor(BRAND_LIGHT_GREY)
        self.p.roundRect(45, self.y - total_height, 510, total_height, 8, fill=1, stroke=0)
        self.p.setFillColor(colors.black)

        # Starting text position (inside the box)
        text_y = self.y - padding_top - 2

        self.p.setFont("Helvetica", 11)

        # Draw each line
        for line in lines:
            self.p.drawString(55, text_y, line)
            text_y -= line_height

        # Move cursor down after the box
        self.y -= total_height + 20

    def table(self, headers, rows):
        x_positions = [50, 150, 260, 380, 480]
        col_widths = [100, 110, 110, 110, 110]
        CELL_PADDING_X = 8

        # Header background
        self.p.setFillColor(BRAND_LIGHT_GREY)
        header_height = 20
        self.p.rect(45, self.y - header_height, 510, header_height, fill=1, stroke=0)
        self.p.setFillColor(colors.black)

        # Draw header text
        self.p.setFont("Helvetica-Bold", 10)
        for i, header in enumerate(headers):
            self.p.drawString(x_positions[i], self.y - 15, header)

        # Draw header border
        self.p.setLineWidth(0.5)
        self.p.rect(45, self.y - header_height, 510, header_height, fill=0, stroke=1)

        # Move down
        self.y -= header_height

        # Draw rows
        for row in rows:
            # Wrap text into Paragraphs
            paragraphs = []
            heights = []

            for i, cell in enumerate(row):
                para = Paragraph(str(cell), self.cell_style)
                paragraphs.append(para)

                w, h = para.wrap(col_widths[i] - (CELL_PADDING_X * 2), 9999)
                heights.append(h)

            row_height = max(heights) + 6  # padding

            # Page break if needed
            if self.y - row_height < 80:
                self.new_page()

            # Draw cell borders
            self.p.setLineWidth(0.5)
            self.p.rect(45, self.y - row_height, 510, row_height, fill=0, stroke=1)

            # Draw vertical column lines
            for x in x_positions[1:]:
                self.p.line(x - 5, self.y, x - 5, self.y - row_height)

            # Draw text inside cells
            for i, para in enumerate(paragraphs):
                text_y = self.y - 3  # top padding
                para.drawOn(self.p, x_positions[i] + CELL_PADDING_X, text_y - heights[i])

            # Move down
            self.y -= row_height

        # Add spacing after table
        self.y -= 15

    def new_page(self):
        self.p.showPage()
        self.y = self.height - 50
        self.footer()

    def footer(self):
        self.p.setFont("Helvetica", 9)
        self.p.setFillColor(BRAND_DARK_GREY)
        self.p.drawString(270, 20, f"Page {self.p.getPageNumber()}")
        self.p.setFillColor(colors.black)

    def save(self):
        self.footer()
        self.p.showPage()
        self.p.save()