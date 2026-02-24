import os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors

PDF_DIR = "static/pdfs"
os.makedirs(PDF_DIR, exist_ok=True)

def generate_catalog_pdf() -> str:
    """Генерация тестового PDF каталога Сибирского кедра"""
    filepath = os.path.join(PDF_DIR, "Siberian_Cedar_Catalog.pdf")
    
    # Если файл уже есть, не пересоздаем
    if os.path.exists(filepath):
        return filepath
        
    c = canvas.Canvas(filepath, pagesize=A4)
    width, height = A4
    
    # Заголовок
    c.setFont("Helvetica-Bold", 24)
    c.setFillColor(colors.darkgreen)
    c.drawString(100, height - 100, "SIBERIAN CEDAR - PRODUCT CATALOG")
    
    # Подзаголовок
    c.setFont("Helvetica", 12)
    c.setFillColor(colors.black)
    c.drawString(100, height - 130, "Premium eco-products for catering & gifts (siberia.eco)")
    
    # Продукты
    products = [
        ("Pine Nuts (Shelled)", "500g", "1200 RUB", "Fresh raw pine nuts from Siberian forests."),
        ("Pine Nut Oil (Cold Pressed)", "250ml", "950 RUB", "100% pure cold-pressed oil."),
        ("Pine Cone Jam", "300g", "450 RUB", "Young pine cones in sweet syrup. Exotic dessert."),
        ("Cedar Nut Marmalade", "Assorted", "350 RUB", "Natural fruit marmalade with whole nuts."),
        ("Cedar Grillage in Chocolate", "Box", "550 RUB", "Premium handmade candies."),
    ]
    
    y = height - 180
    for name, size, price, desc in products:
        c.setFont("Helvetica-Bold", 14)
        c.setFillColor(colors.darkgreen)
        c.drawString(100, y, name)
        
        c.setFont("Helvetica", 12)
        c.setFillColor(colors.black)
        c.drawString(400, y, price)
        
        c.setFont("Helvetica-Oblique", 10)
        c.setFillColor(colors.gray)
        c.drawString(100, y - 15, f"Size: {size} | {desc}")
        
        y -= 60
        c.line(100, y + 30, 500, y + 30)
        
    # Footer
    c.setFont("Helvetica", 10)
    c.setFillColor(colors.black)
    c.drawString(100, 50, "Contact us for wholesale pricing: sales@siberia.eco")
    
    c.save()
    return filepath
