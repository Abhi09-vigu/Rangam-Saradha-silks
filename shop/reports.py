import io
import os
import calendar
import urllib.request
from datetime import datetime
from decimal import Decimal

from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Sum

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.drawing.image import Image as XLImage
from PIL import Image as PILImage

from .models import Order, OrderItem, ProductImage


def generate_monthly_sales_excel(year: int, month: int, include_cancelled: bool = False):
    """
    Generates an executive, beautifully formatted Excel (.xlsx) report for
    the selected month and year.
    Features:
      - Luxury Store Header & Report Metadata
      - Elegant Floating KPI Summary Cards (Revenue, Orders, Items Sold, Avg Order Value)
      - Itemized Order Transactions Table
      - Real Embedded Product Image Thumbnails (Supports Cloudinary URLs and Local Media)
      - Executive Accounting Summary Totals Row (with Excel Formulas)
      - Set to 100% Zoom and Clean Frozen Table Headers
    """
    # 1. Date Range in Project Timezone
    current_tz = timezone.get_current_timezone()
    last_day = calendar.monthrange(year, month)[1]
    
    start_dt = timezone.make_aware(datetime(year, month, 1, 0, 0, 0), current_tz)
    end_dt = timezone.make_aware(datetime(year, month, last_day, 23, 59, 59, 999999), current_tz)
    month_name = calendar.month_name[month]

    # 2. Query Orders
    base_orders = Order.objects.filter(created_at__gte=start_dt, created_at__lte=end_dt)
    
    if not include_cancelled:
        valid_orders = base_orders.exclude(order_status__in=['CANCELLED', 'RETURNED'])
    else:
        valid_orders = base_orders

    total_orders_count = valid_orders.count()
    total_revenue = valid_orders.aggregate(total=Sum('grand_total'))['total'] or Decimal('0.00')

    orders_with_items = base_orders.order_by('-created_at').prefetch_related(
        'items__product__images'
    )

    total_items_sold = 0
    line_items_data = []

    # Product image cache to prevent duplicate downloads
    product_image_cache = {}

    def get_product_pil_image(product):
        if not product:
            return None
        if product.id in product_image_cache:
            return product_image_cache[product.id]

        first_img = product.images.first()
        if not first_img or not first_img.image:
            product_image_cache[product.id] = None
            return None

        # Try 1: Local file path
        try:
            if hasattr(first_img.image, 'path') and os.path.exists(first_img.image.path):
                img = PILImage.open(first_img.image.path)
                product_image_cache[product.id] = img.copy()
                return product_image_cache[product.id]
        except Exception:
            pass

        # Try 2: Direct file storage handle
        try:
            f = first_img.image.open('rb')
            img = PILImage.open(f)
            product_image_cache[product.id] = img.copy()
            f.close()
            return product_image_cache[product.id]
        except Exception:
            pass

        # Try 3: Remote Cloudinary/CDN URL (fetch once with quick timeout)
        try:
            img_url = first_img.image.url
            if img_url and img_url.startswith('http'):
                req = urllib.request.Request(img_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=3.5) as resp:
                    data = resp.read()
                    img = PILImage.open(io.BytesIO(data))
                    product_image_cache[product.id] = img.copy()
                    return product_image_cache[product.id]
        except Exception:
            pass

        product_image_cache[product.id] = None
        return None

    for order in orders_with_items:
        items = list(order.items.all())
        if not items:
            line_items_data.append({
                'order': order,
                'item': None,
                'product': None,
                'pil_image': None,
                'product_name': 'No Products',
                'sku': '-',
                'quantity': 0,
                'price': Decimal('0.00'),
                'total_price': Decimal('0.00'),
            })
            continue

        for item in items:
            prod = item.product
            if order.order_status not in ['CANCELLED', 'RETURNED']:
                total_items_sold += item.quantity

            pil_img = get_product_pil_image(prod)

            line_items_data.append({
                'order': order,
                'item': item,
                'product': prod,
                'pil_image': pil_img,
                'product_name': prod.name if prod else 'Deleted Product',
                'sku': prod.sku if (prod and prod.sku) else '-',
                'quantity': item.quantity,
                'price': item.price,
                'total_price': item.price * item.quantity,
            })

    avg_order_value = (total_revenue / total_orders_count) if total_orders_count > 0 else Decimal('0.00')

    # 3. Create Workbook & Setup Styling
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"{month_name[:3]} {year} Sales Report"
    ws.views.sheetView[0].showGridLines = True
    ws.sheet_view.zoomScale = 100  # Ensure Excel opens at 100% zoom

    # Color Palette
    maroon_primary = "721428"
    gold_accent = "C5A059"
    kpi_card_bg = "FAF8F5"
    border_light = "E5DFD7"
    row_alt_bg = "FAF8F5"
    header_text_color = "FFFFFF"

    # Borders
    thin_side = Side(style="thin", color=border_light)
    cell_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)
    double_bottom_border = Border(
        left=thin_side, right=thin_side,
        top=Side(style="thin", color=maroon_primary),
        bottom=Side(style="double", color=maroon_primary)
    )

    # --- ROW 1: Store Brand Header ---
    ws.merge_cells("A1:N1")
    title_cell = ws["A1"]
    title_cell.value = "RANGAM SARADHA SILK SAREES"
    title_cell.font = Font(name="Calibri", size=15, bold=True, color="FFFFFF")
    title_cell.fill = PatternFill(start_color=maroon_primary, end_color=maroon_primary, fill_type="solid")
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 32

    # --- ROW 2: Report Subtitle ---
    ws.merge_cells("A2:N2")
    sub_cell = ws["A2"]
    sub_cell.value = f"MONTHLY REVENUE & SALES REPORT — {month_name.upper()} {year}"
    sub_cell.font = Font(name="Calibri", size=11, bold=True, color="721428")
    sub_cell.fill = PatternFill(start_color="F5EFEB", end_color="F5EFEB", fill_type="solid")
    sub_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[2].height = 22

    # --- ROW 3: Generation Metadata ---
    ws.merge_cells("A3:N3")
    meta_cell = ws["A3"]
    now_str = timezone.localtime(timezone.now()).strftime("%d %B %Y, %I:%M %p")
    meta_cell.value = f"Period: {month_name} 1 – {last_day}, {year}   |   Generated: {now_str}   |   Currency: INR (₹)"
    meta_cell.font = Font(name="Calibri", size=9, italic=True, color="666666")
    meta_cell.fill = PatternFill(start_color="FBF9F7", end_color="FBF9F7", fill_type="solid")
    meta_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[3].height = 18

    # Row 4 Spacer
    ws.row_dimensions[4].height = 10

    # --- ROWS 5 & 6: Floating KPI Summary Cards ---
    kpi_cards = [
        ("B", "D", "MONTHLY TOTAL REVENUE", f"₹ {total_revenue:,.2f}", "721428"),
        ("E", "G", "TOTAL ORDERS", f"{total_orders_count:,} Orders", "1B8A53"),
        ("H", "J", "TOTAL ITEMS SOLD", f"{total_items_sold:,} Items", "AE6F21"),
        ("K", "M", "AVERAGE ORDER VALUE", f"₹ {avg_order_value:,.2f}", "721428"),
    ]

    for start_c, end_c, label, val_str, val_color in kpi_cards:
        # Title row 5
        ws.merge_cells(f"{start_c}5:{end_c}5")
        c_label = ws[f"{start_c}5"]
        c_label.value = label
        c_label.font = Font(name="Calibri", size=8.5, bold=True, color="777777")
        c_label.alignment = Alignment(horizontal="center", vertical="center")
        c_label.fill = PatternFill(start_color=kpi_card_bg, end_color=kpi_card_bg, fill_type="solid")

        # Value row 6
        ws.merge_cells(f"{start_c}6:{end_c}6")
        c_val = ws[f"{start_c}6"]
        c_val.value = val_str
        c_val.font = Font(name="Calibri", size=13, bold=True, color=val_color)
        c_val.alignment = Alignment(horizontal="center", vertical="center")
        c_val.fill = PatternFill(start_color=kpi_card_bg, end_color=kpi_card_bg, fill_type="solid")

        # Set borders
        start_idx = openpyxl.utils.column_index_from_string(start_c)
        end_idx = openpyxl.utils.column_index_from_string(end_c)
        for r in (5, 6):
            for c in range(start_idx, end_idx + 1):
                ws.cell(row=r, column=c).border = cell_border

    ws.row_dimensions[5].height = 18
    ws.row_dimensions[6].height = 26
    ws.row_dimensions[7].height = 12  # Spacer

    # --- ROW 8: Table Column Headers ---
    headers = [
        ("#", 6),
        ("Product Image", 16),
        ("Saree / Product Name", 34),
        ("SKU Code", 14),
        ("Order Number", 18),
        ("Customer Name", 22),
        ("Customer Phone", 16),
        ("Purchase Date & Time", 20),
        ("Qty", 8),
        ("Selling Price (₹)", 17),
        ("Total Paid (₹)", 18),
        ("Payment Method", 16),
        ("Payment Status", 15),
        ("Order Status", 15),
    ]

    header_font = Font(name="Calibri", size=10, bold=True, color=header_text_color)
    header_fill = PatternFill(start_color=maroon_primary, end_color=maroon_primary, fill_type="solid")
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

    ws.row_dimensions[8].height = 28

    for col_idx, (title, width) in enumerate(headers, start=1):
        cell = ws.cell(row=8, column=col_idx, value=title)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = cell_border
        col_letter = get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = width

    # --- ROWS 9+: Data Rows ---
    data_font = Font(name="Calibri", size=10)
    bold_data_font = Font(name="Calibri", size=10, bold=True)
    align_center = Alignment(horizontal="center", vertical="center")
    align_left = Alignment(horizontal="left", vertical="center", wrap_text=True)
    align_right = Alignment(horizontal="right", vertical="center")

    white_fill = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
    alt_fill = PatternFill(start_color=row_alt_bg, end_color=row_alt_bg, fill_type="solid")

    img_buffers_to_keep = []
    current_row = 9

    # Status styling colors
    status_badge_styles = {
        'DELIVERED': (Font(name="Calibri", size=9, bold=True, color="0F5132"), PatternFill("solid", fgColor="D1E7DD")),
        'CONFIRMED': (Font(name="Calibri", size=9, bold=True, color="084298"), PatternFill("solid", fgColor="CFE2FF")),
        'SHIPPED': (Font(name="Calibri", size=9, bold=True, color="055160"), PatternFill("solid", fgColor="CFF4FC")),
        'PACKED': (Font(name="Calibri", size=9, bold=True, color="664D03"), PatternFill("solid", fgColor="FFF3CD")),
        'PENDING': (Font(name="Calibri", size=9, bold=True, color="664D03"), PatternFill("solid", fgColor="FFF3CD")),
        'CANCELLED': (Font(name="Calibri", size=9, bold=True, color="842029"), PatternFill("solid", fgColor="F8D7DA")),
        'PAID': (Font(name="Calibri", size=9, bold=True, color="0F5132"), PatternFill("solid", fgColor="D1E7DD")),
        'FAILED': (Font(name="Calibri", size=9, bold=True, color="842029"), PatternFill("solid", fgColor="F8D7DA")),
    }

    for idx, row_item in enumerate(line_items_data, start=1):
        order = row_item['order']
        row_fill = alt_fill if (idx % 2 == 0) else white_fill
        ws.row_dimensions[current_row].height = 48

        # 1. Row #
        c1 = ws.cell(row=current_row, column=1, value=idx)
        c1.alignment = align_center

        # 2. Product Image
        c2 = ws.cell(row=current_row, column=2)
        c2.alignment = align_center
        img_placed = False

        if row_item['pil_image']:
            try:
                pil_copy = row_item['pil_image'].copy()
                pil_copy.thumbnail((42, 42))
                buf = io.BytesIO()
                pil_copy.save(buf, format="PNG")
                buf.seek(0)
                img_buffers_to_keep.append(buf)

                xl_img = XLImage(buf)
                xl_img.width = pil_copy.width
                xl_img.height = pil_copy.height
                xl_img.anchor = f"B{current_row}"
                ws.add_image(xl_img)
                img_placed = True
            except Exception:
                img_placed = False

        if not img_placed:
            c2.value = "No Image"
            c2.font = Font(name="Calibri", size=8, italic=True, color="999999")

        # 3. Saree / Product Name
        c3 = ws.cell(row=current_row, column=3, value=row_item['product_name'])
        c3.alignment = align_left
        c3.font = bold_data_font

        # 4. SKU Code
        c4 = ws.cell(row=current_row, column=4, value=row_item['sku'])
        c4.alignment = align_center

        # 5. Order Number
        c5 = ws.cell(row=current_row, column=5, value=order.order_number)
        c5.alignment = align_center
        c5.font = Font(name="Calibri", size=9.5, color="721428", bold=True)

        # 6. Customer Name
        c6 = ws.cell(row=current_row, column=6, value=order.full_name)
        c6.alignment = align_left

        # 7. Customer Phone
        c7 = ws.cell(row=current_row, column=7, value=str(order.phone_number))
        c7.alignment = align_center

        # 8. Purchase Date
        c8 = ws.cell(row=current_row, column=8, value=timezone.localtime(order.created_at).strftime("%Y-%m-%d %I:%M %p"))
        c8.alignment = align_center

        # 9. Quantity
        c9 = ws.cell(row=current_row, column=9, value=row_item['quantity'])
        c9.alignment = align_center
        c9.font = bold_data_font

        # 10. Selling Price (₹)
        c10 = ws.cell(row=current_row, column=10, value=float(row_item['price']))
        c10.alignment = align_right
        c10.number_format = '"₹"#,##0.00'

        # 11. Total Paid (₹)
        c11 = ws.cell(row=current_row, column=11, value=float(row_item['total_price']))
        c11.alignment = align_right
        c11.font = bold_data_font
        c11.number_format = '"₹"#,##0.00'

        # 12. Payment Method
        c12 = ws.cell(row=current_row, column=12, value=order.get_payment_method_display())
        c12.alignment = align_center

        # 13. Payment Status Badge
        c13 = ws.cell(row=current_row, column=13, value=order.get_payment_status_display())
        c13.alignment = align_center
        pay_st = order.payment_status
        if pay_st in status_badge_styles:
            c13.font, c13.fill = status_badge_styles[pay_st]
        else:
            c13.fill = row_fill

        # 14. Order Status Badge
        c14 = ws.cell(row=current_row, column=14, value=order.get_order_status_display())
        c14.alignment = align_center
        ord_st = order.order_status
        if ord_st in status_badge_styles:
            c14.font, c14.fill = status_badge_styles[ord_st]
        else:
            c14.fill = row_fill

        # Apply fonts, borders & row fills to non-badge cells
        for col_i in range(1, 15):
            cell_c = ws.cell(row=current_row, column=col_i)
            cell_c.border = cell_border
            if col_i not in (13, 14):
                cell_c.fill = row_fill
            if col_i not in (3, 5, 9, 11, 13, 14) and cell_c.value != "No Image":
                cell_c.font = data_font

        current_row += 1

    # --- SUMMARY TOTALS ROW AT BOTTOM ---
    if line_items_data:
        total_row = current_row
        ws.row_dimensions[total_row].height = 28

        # Merged label A-H
        ws.merge_cells(f"A{total_row}:H{total_row}")
        label_total_cell = ws[f"A{total_row}"]
        label_total_cell.value = "TOTALS (ITEMS & REVENUE):"
        label_total_cell.font = Font(name="Calibri", size=10, bold=True, color="721428")
        label_total_cell.fill = PatternFill(start_color="F5EFEB", end_color="F5EFEB", fill_type="solid")
        label_total_cell.alignment = Alignment(horizontal="right", vertical="center")

        # Sum of Quantities (Column 9 / I)
        qty_total_cell = ws.cell(row=total_row, column=9, value=f"=SUM(I9:I{total_row - 1})")
        qty_total_cell.font = Font(name="Calibri", size=10.5, bold=True, color="721428")
        qty_total_cell.fill = PatternFill(start_color="F5EFEB", end_color="F5EFEB", fill_type="solid")
        qty_total_cell.alignment = align_center

        # Column 10 (Blank Selling Price)
        ws.cell(row=total_row, column=10).fill = PatternFill(start_color="F5EFEB", end_color="F5EFEB", fill_type="solid")

        # Sum of Total Paid (Column 11 / K)
        rev_total_cell = ws.cell(row=total_row, column=11, value=f"=SUM(K9:K{total_row - 1})")
        rev_total_cell.font = Font(name="Calibri", size=11, bold=True, color="721428")
        rev_total_cell.fill = PatternFill(start_color="F5EFEB", end_color="F5EFEB", fill_type="solid")
        rev_total_cell.alignment = align_right
        rev_total_cell.number_format = '"₹"#,##0.00'

        # Remaining columns in summary row
        for col_i in range(12, 15):
            ws.cell(row=total_row, column=col_i).fill = PatternFill(start_color="F5EFEB", end_color="F5EFEB", fill_type="solid")

        # Accounting double bottom border across all columns
        for col_i in range(1, 15):
            ws.cell(row=total_row, column=col_i).border = double_bottom_border
    else:
        # No data message
        no_data_row = current_row
        ws.row_dimensions[no_data_row].height = 36
        ws.merge_cells(f"A{no_data_row}:N{no_data_row}")
        nd_cell = ws[f"A{no_data_row}"]
        nd_cell.value = f"No orders or sales recorded for {month_name} {year}."
        nd_cell.font = Font(name="Calibri", size=11, italic=True, color="777777")
        nd_cell.alignment = Alignment(horizontal="center", vertical="center")
        for col_i in range(1, 15):
            ws.cell(row=no_data_row, column=col_i).border = cell_border

    # Freeze header row (Row 8) so only table headers freeze when scrolling
    ws.freeze_panes = "A9"

    # 4. Generate HTTP Response
    filename = f"Rangam_Saradha_Silks_Sales_Report_{month_name}_{year}.xlsx"
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    wb.save(response)

    # Clean up image buffers
    for buf in img_buffers_to_keep:
        try:
            buf.close()
        except Exception:
            pass

    return response
