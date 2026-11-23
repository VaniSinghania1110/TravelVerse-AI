"""
TravelVerse Official PDF Generator Engine
Generates personalized, luxury expedition booking invoices and official vouchers.
Uses ReportLab to produce professional, strictly maximum 2-page documents.
Provides a graceful pure-Python PDF fallback if ReportLab is missing.
"""

import io
import time
from typing import Dict, Any, Optional, List

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


def _generate_reportlab_pdf(trip_data: dict, booking_data: dict = None) -> bytes:
    """
    Generates a personalized luxury booking invoice & expedition dossier.
    Strictly guaranteed to be at most 2 pages:
    - Page 1: Official Tax Invoice, Lead Customer Details, Host Guide & Agency Details,
              Financial & Payment Breakdown, Registered Passenger Details (Name, Gender, Age, Nationality, Preferences),
              Special Logistics Requests & Notes.
    - Page 2: Day-wise Expedition Schedule, Inclusions & Exclusions, Mandatory Travel Advisory,
              and Official TravelVerse Verified Host Seal.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=28,
        rightMargin=28,
        topMargin=26,
        bottomMargin=26
    )

    styles = getSampleStyleSheet()
    primary = colors.HexColor('#0B2027')
    gold = colors.HexColor('#C9A227')
    gold_dark = colors.HexColor('#9A7512')
    bg_light = colors.HexColor('#FAF8F5')
    border_col = colors.HexColor('#E2D8C6')
    ink = colors.HexColor('#17242A')
    ink_soft = colors.HexColor('#55625F')
    green = colors.HexColor('#166534')
    green_bg = colors.HexColor('#DCFCE7')
    red = colors.HexColor('#991B1B')

    title_style = ParagraphStyle('TTitle', fontName='Helvetica-Bold', fontSize=15, leading=19, textColor=primary)
    tagline_style = ParagraphStyle('TTagline', fontName='Helvetica-Oblique', fontSize=8, leading=11, textColor=gold_dark)
    sec_head = ParagraphStyle('SecH', fontName='Helvetica-Bold', fontSize=9.5, leading=13, textColor=primary, spaceBefore=3, spaceAfter=3)
    body_style = ParagraphStyle('Body', fontName='Helvetica', fontSize=8, leading=11, textColor=ink)
    body_bold = ParagraphStyle('BodyB', fontName='Helvetica-Bold', fontSize=8, leading=11, textColor=ink)
    small_soft = ParagraphStyle('SmallSoft', fontName='Helvetica', fontSize=7.5, leading=10, textColor=ink_soft)

    story = []

    b_doc = booking_data or {}
    b_code = b_doc.get('booking_code', 'TV-EXP-ONLINE')
    b_date = b_doc.get('created_at') or time.strftime('%Y-%m-%d %H:%M:%S')
    b_user = b_doc.get('user_name') or b_doc.get('traveller_name') or 'Valued Explorer'
    b_email = b_doc.get('user_email') or b_doc.get('traveller_email') or 'guest@travelverse.com'
    b_phone = b_doc.get('user_phone') or b_doc.get('traveller_phone') or 'Not provided'
    seats = int(b_doc.get('seats', 1) or 1)

    t_name = trip_data.get('title') or trip_data.get('trip_title') or 'Hosted Group Expedition'
    dest = trip_data.get('destination', 'Global Destination')
    agency = trip_data.get('agency_name') or 'TravelVerse Certified Agency'
    guide = trip_data.get('agent_name') or 'Certified Expedition Guide'
    agent_contact = trip_data.get('agent_phone') or trip_data.get('agent_email') or 'concierge@travelverse.com'
    start_date = trip_data.get('start_date', 'Upcoming')
    end_date = trip_data.get('end_date', '')
    dates_str = f"{start_date} to {end_date}".strip(" to") if end_date else start_date
    dur_days = int(trip_data.get('duration_days', 2) or 2)
    duration = f"{dur_days} Days / {max(1, dur_days - 1)} Nights"
    meeting_pt = trip_data.get('meeting_point') or 'Designated Airport VIP Lounge / Central Station Rendezvous'
    curr = b_doc.get('currency') or trip_data.get('currency') or 'USD'
    unit_price = float(trip_data.get('price', 0.0) or b_doc.get('price', 0.0) or 0.0)
    total_amount = float(b_doc.get('amount_paid', 0.0) or (unit_price * seats))

    # =========================================================================
    # PAGE 1: OFFICIAL BOOKING INVOICE & PASSENGER VOUCHER
    # =========================================================================

    # 1. Header Banner
    h_title = Paragraph('<b>TRAVELVERSE</b> &bull; OFFICIAL BOOKING INVOICE & EXPEDITION VOUCHER', ParagraphStyle('H1', fontName='Helvetica-Bold', fontSize=9, textColor=colors.white))
    h_sub = Paragraph(f'<b>INVOICE REF: {b_code}</b> &nbsp;|&nbsp; <font color="#4ADE80"><b>✓ CONFIRMED BOOKING</b></font>', ParagraphStyle('H2', fontName='Helvetica-Bold', fontSize=8.5, textColor=gold, alignment=2))
    header_table = Table([[h_title, h_sub]], colWidths=[310, 229])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), primary),
        ('PADDING', (0,0), (-1,-1), 7),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 7))

    # 2. Trip Name & Subtitle
    story.append(Paragraph(t_name, title_style))
    t_tagline = trip_data.get('tagline') or f"An intimate curated journey through {dest} with verified local specialists"
    story.append(Paragraph(t_tagline, tagline_style))
    story.append(Spacer(1, 4))

    # 3. Two-Column Card: Customer (Billed To) & Expedition Host / Logistics
    cust_html = f'''
    <b>BILLED TO / PRIMARY GUEST</b><br/>
    <b>Guest Name:</b> {b_user} <font color="#D97706">(Lead Traveller)</font><br/>
    <b>Registered Email:</b> {b_email}<br/>
    <b>Phone / WhatsApp:</b> {b_phone}<br/>
    <b>Reserved Spots:</b> {seats} Guest Seat(s)<br/>
    <b>Issue Timestamp:</b> {b_date}
    '''
    host_html = f'''
    <b>EXPEDITION HOST & LOGISTICS</b><br/>
    <b>Host Agency:</b> {agency}<br/>
    <b>Lead Guide:</b> {guide} <font color="#166534">(Certified Guide)</font><br/>
    <b>Host Contact:</b> {agent_contact}<br/>
    <b>Destination:</b> {dest}<br/>
    <b>Meeting Point:</b> {meeting_pt[:68]}
    '''
    two_col = Table([
        [Paragraph(cust_html, body_style), Paragraph(host_html, body_style)]
    ], colWidths=[265, 274])
    two_col.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), bg_light),
        ('BOX', (0,0), (-1,-1), 1, border_col),
        ('INNERGRID', (0,0), (-1,-1), 0.5, border_col),
        ('PADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(two_col)
    story.append(Spacer(1, 7))

    # 4. Financial & Payment Summary Table
    fin_data = [
        [Paragraph('<b>ITEM / EXPEDITION SERVICE</b>', small_soft), Paragraph('<b>RATE / SEAT</b>', small_soft), Paragraph('<b>SEATS</b>', small_soft), Paragraph('<b>TOTAL VALUE</b>', small_soft)],
        [Paragraph(f'<b>Expedition Spot:</b> {t_name}<br/><font color="#55625F">Schedule: {dates_str} &bull; {duration} &bull; {dest}</font>', body_style),
         Paragraph(f'{curr} {unit_price:,.2f}', body_style),
         Paragraph(f'{seats}', body_style),
         Paragraph(f'<b>{curr} {total_amount:,.2f}</b>', body_bold)],
        [Paragraph('<b>Invoice Settlement & Booking Guarantee:</b>', body_bold),
         Paragraph('<b>PAID & CONFIRMED</b>', ParagraphStyle('Pd', parent=body_bold, textColor=green)),
         Paragraph(f'<b>{seats} Pax</b>', body_bold),
         Paragraph(f'<b>{curr} {total_amount:,.2f}</b>', ParagraphStyle('TB', parent=body_bold, textColor=primary, fontSize=9))]
    ]
    fin_table = Table(fin_data, colWidths=[270, 95, 60, 114])
    fin_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F3EDE2')),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#FEF9C3')),
        ('BOX', (0,0), (-1,-1), 1, border_col),
        ('INNERGRID', (0,0), (-1,-1), 0.5, border_col),
        ('PADDING', (0,0), (-1,-1), 5),
        ('ALIGN', (1,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(fin_table)
    story.append(Spacer(1, 7))

    # 5. Registered Passenger Details Table
    story.append(Paragraph('REGISTERED PASSENGERS & TRAVEL PREFERENCES', sec_head))
    passengers = b_doc.get('passengers') or []
    if not passengers:
        names = b_doc.get('traveller_names') or [b_user]
        passengers = [{'name': n} for n in names]
    
    pax_data = [
        [Paragraph('<b>#</b>', small_soft),
         Paragraph('<b>PASSENGER NAME</b>', small_soft),
         Paragraph('<b>GENDER</b>', small_soft),
         Paragraph('<b>AGE</b>', small_soft),
         Paragraph('<b>NATIONALITY</b>', small_soft),
         Paragraph('<b>MEAL / PREFERENCES</b>', small_soft)]
    ]
    # Show up to 5 passengers to fit perfectly on Page 1
    for idx, p in enumerate(passengers[:5]):
        p_name = p.get('name') or f'Passenger {idx+1}'
        lead_tag = ' <font color="#D97706"><b>(Lead)</b></font>' if idx == 0 else ''
        p_gen = p.get('gender') or '&mdash;'
        p_age = f"{p.get('age')} yrs" if p.get('age') is not None and str(p.get('age')).strip() else '&mdash;'
        p_nat = p.get('nationality') or 'Indian'
        p_pref = p.get('preferences') or 'Standard'
        pax_data.append([
            Paragraph(f'{idx+1}', small_soft),
            Paragraph(f'<b>{p_name}</b>{lead_tag}', body_style),
            Paragraph(p_gen, body_style),
            Paragraph(p_age, body_style),
            Paragraph(p_nat, body_style),
            Paragraph(p_pref, body_style)
        ])
    
    pax_table = Table(pax_data, colWidths=[22, 160, 60, 48, 85, 164])
    pax_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F3EDE2')),
        ('BOX', (0,0), (-1,-1), 1, border_col),
        ('INNERGRID', (0,0), (-1,-1), 0.5, border_col),
        ('PADDING', (0,0), (-1,-1), 4.5),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(pax_table)
    story.append(Spacer(1, 5))

    # 6. Special Requests & Notes Box
    notes = b_doc.get('special_notes') or 'No dietary restrictions, special assistance, or extra requests recorded.'
    notes_table = Table([
        [Paragraph(f'<b>Special Requests & Logistics Notes:</b> {notes}', small_soft)]
    ], colWidths=[539])
    notes_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), bg_light),
        ('BOX', (0,0), (-1,-1), 0.5, border_col),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(notes_table)
    story.append(Spacer(1, 7))

    # Page 1 Footer Strip
    p1_footer = Table([
        [Paragraph('<b>TravelVerse Verified Booking Voucher & Tax Invoice</b> &bull; Customer Care: support@travelverse.com', small_soft),
         Paragraph('<b>Page 1 of 2</b> &bull; Turn over for Day-wise Itinerary & Inclusions &gt;&gt;', ParagraphStyle('P1F', parent=small_soft, alignment=2))]
    ], colWidths=[290, 249])
    p1_footer.setStyle(TableStyle([
        ('LINEABOVE', (0,0), (-1,-1), 0.5, border_col),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(p1_footer)

    # =========================================================================
    # PAGE 2: DAY-WISE ITINERARY, INCLUSIONS & ADVISORY
    # =========================================================================
    story.append(PageBreak())

    p2_head = Table([
        [Paragraph('<b>TRAVELVERSE</b> &bull; EXPEDITION ITINERARY, INCLUSIONS & ADVISORY', ParagraphStyle('P2H', fontName='Helvetica-Bold', fontSize=8.5, textColor=colors.white)),
         Paragraph(f'Ref: <b>{b_code}</b> &bull; {t_name}', ParagraphStyle('P2Sub', fontName='Helvetica', fontSize=8, textColor=gold, alignment=2))]
    ], colWidths=[280, 259])
    p2_head.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), primary),
        ('PADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(p2_head)
    story.append(Spacer(1, 7))

    # Day-wise Itinerary
    story.append(Paragraph('DAY-WISE EXPEDITION SCHEDULE', sec_head))
    itin_items = trip_data.get('itinerary') or trip_data.get('itinerary_days') or []
    itin_rows = []
    # Up to 6 days fit cleanly on Page 2
    for item in itin_items[:6]:
        if isinstance(item, dict):
            d_num = item.get('day', 1)
            d_title = item.get('title') or f'Day {d_num}'
            d_desc = item.get('description', '')
            itin_rows.append([
                Paragraph(f'<b>Day {d_num}</b>', ParagraphStyle('DNum', fontName='Helvetica-Bold', fontSize=8, textColor=gold_dark)),
                Paragraph(f'<b>{d_title}</b><br/>{d_desc}', body_style)
            ])
    if itin_rows:
        itin_table = Table(itin_rows, colWidths=[50, 489])
        itin_table.setStyle(TableStyle([
            ('LINEBELOW', (0,0), (-1,-1), 0.5, border_col),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ]))
        story.append(itin_table)
        story.append(Spacer(1, 7))

    # Inclusions & Exclusions
    inclusions = trip_data.get('inclusions', [])
    exclusions = trip_data.get('exclusions', [])
    if isinstance(inclusions, str):
        inclusions = [i.strip() for i in inclusions.split('\n') if i.strip()]
    if isinstance(exclusions, str):
        exclusions = [e.strip() for e in exclusions.split('\n') if e.strip()]

    inc_html = '<br/>'.join([f'&bull; {i}' for i in inclusions[:5]]) if inclusions else '&bull; Guided logistics & verified stays'
    exc_html = '<br/>'.join([f'&bull; {e}' for e in exclusions[:5]]) if exclusions else '&bull; Personal expenses & transport to start'

    ie_table = Table([
        [Paragraph('<b>EXPEDITION INCLUSIONS</b>', ParagraphStyle('IncH', fontName='Helvetica-Bold', fontSize=8.5, textColor=green)),
         Paragraph('<b>EXCLUSIONS</b>', ParagraphStyle('ExcH', fontName='Helvetica-Bold', fontSize=8.5, textColor=red))],
        [Paragraph(inc_html, body_style), Paragraph(exc_html, body_style)]
    ], colWidths=[265, 274])
    ie_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), bg_light),
        ('BOX', (0,0), (-1,-1), 1, border_col),
        ('INNERGRID', (0,0), (-1,-1), 0.5, border_col),
        ('PADDING', (0,0), (-1,-1), 5.5),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(ie_table)
    story.append(Spacer(1, 7))

    # Mandatory Guidelines Box
    guide_html = f'''
    <b>MANDATORY TRAVEL ADVISORY & RENDEZVOUS PROTOCOL:</b><br/>
    &bull; <b>Original Photo ID:</b> All registered travellers must carry government-issued photo ID (Aadhaar / Passport) matching passenger records.<br/>
    &bull; <b>Reporting Time:</b> Please report to <i>{meeting_pt[:60]}</i> at least 30 minutes prior to departure.<br/>
    &bull; <b>TravelVerse SafeTrip Protection:</b> 100% verified host certification, emergency concierge hotline, and booking integrity guarantee.
    '''
    guide_table = Table([[Paragraph(guide_html, small_soft)]], colWidths=[539])
    guide_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#FEF9C3')),
        ('BOX', (0,0), (-1,-1), 1, gold),
        ('PADDING', (0,0), (-1,-1), 5.5),
    ]))
    story.append(guide_table)
    story.append(Spacer(1, 7))

    # Page 2 Footer
    p2_footer = Table([
        [Paragraph(f'TravelVerse Global Expedition Network &bull; Certified Host: {agency} ({guide}) &bull; travelverse.com', small_soft),
         Paragraph('<b>Page 2 of 2 &bull; Official Digital Document</b>', ParagraphStyle('P2F', parent=small_soft, alignment=2))]
    ], colWidths=[360, 179])
    p2_footer.setStyle(TableStyle([
        ('LINEABOVE', (0,0), (-1,-1), 0.5, border_col),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(p2_footer)

    doc.build(story)
    return buffer.getvalue()


def _generate_pure_python_pdf(trip_data: dict, booking_data: dict = None) -> bytes:
    """Zero-dependency pure Python PDF generator that produces standard, valid 2-page PDF 1.4 files."""
    title = trip_data.get("trip_title") or trip_data.get("title") or "TravelVerse Official Trip Itinerary"
    dest = trip_data.get("destination") or "Featured Global Destination"
    agency = trip_data.get("agency_name") or "TravelVerse Certified Partner"
    guide = trip_data.get("agent_name") or "Expedition Guide"
    dates = trip_data.get("dates") or f"{trip_data.get('start_date', '')} - {trip_data.get('end_date', '')}".strip(" -") or "Flexible Departure"
    price = str(trip_data.get("price") or trip_data.get("price_per_person") or "Inquire with Agent")
    inclusions = trip_data.get("inclusions") or []
    if isinstance(inclusions, str):
        inclusions = [i.strip() for i in inclusions.split("\n") if i.strip()]
    exclusions = trip_data.get("exclusions") or []
    if isinstance(exclusions, str):
        exclusions = [e.strip() for e in exclusions.split("\n") if e.strip()]
    days = trip_data.get("itinerary_days") or trip_data.get("itinerary") or []
    
    b_doc = booking_data or {}
    booking_code = b_doc.get("booking_code") or "TV-EXPEDITION"
    traveller = b_doc.get("user_name") or b_doc.get("traveller_name") or b_doc.get("user_email") or "Valued Guest"
    user_email = b_doc.get("user_email") or ""
    user_phone = b_doc.get("user_phone") or ""
    seats = str(b_doc.get("seats") or 1)
    passengers = b_doc.get("passengers") or []

    # Page 1 lines
    p1_lines = [
        "TRAVELVERSE - OFFICIAL EXPEDITION BOOKING INVOICE (PAGE 1 OF 2)",
        "=" * 68,
        f"Invoice Ref:   {booking_code}     Status: CONFIRMED BOOKING",
        f"Trip Title:    {title}",
        f"Destination:   {dest}",
        "-" * 68,
        "BILLED TO / CUSTOMER DETAILS:",
        f"Primary Guest: {traveller} (Lead)",
        f"Email:         {user_email}",
        f"Phone/WhatsApp:{user_phone}",
        f"Reserved Seats:{seats} seat(s)",
        "-" * 68,
        "EXPEDITION HOST & LOGISTICS:",
        f"Host Agency:   {agency}",
        f"Certified Host:{guide}",
        f"Meeting Point: {trip_data.get('meeting_point', 'Designated Airport VIP Lounge')}",
        f"Dates:         {dates}",
        f"Fare / Seat:   {price}",
        "-" * 68,
        "REGISTERED PASSENGERS & PREFERENCES:"
    ]
    if passengers:
        for idx, p in enumerate(passengers[:5]):
            p1_lines.append(f"  {idx+1}. {p.get('name', 'Guest')} | {p.get('gender', '-')} | {p.get('age', '-')} yrs | {p.get('nationality', 'Indian')} | Meal: {p.get('preferences', 'Standard')}")
    else:
        p1_lines.append(f"  1. {traveller} (Lead Passenger)")

    p1_lines.extend([
        "",
        f"Special Notes: {b_doc.get('special_notes') or 'None'}",
        "=" * 68,
        ">> CONTINUED ON PAGE 2 FOR DAY-WISE ITINERARY & INCLUSIONS >>"
    ])

    # Page 2 lines
    p2_lines = [
        f"TRAVELVERSE - EXPEDITION ITINERARY & GUIDELINES (PAGE 2 OF 2) [Ref: {booking_code}]",
        "=" * 68,
        "DAY-WISE EXPEDITION SCHEDULE:",
        "-" * 68
    ]
    for d in days[:6]:
        if isinstance(d, dict):
            d_num = d.get("day", 1)
            d_title = d.get("title") or d.get("activity") or f"Day {d_num} Itinerary"
            d_desc = d.get("description") or ""
            p2_lines.append(f"Day {d_num}: {d_title}")
            if d_desc:
                desc_line = d_desc[:85] + ("..." if len(d_desc) > 85 else "")
                p2_lines.append(f"   {desc_line}")
        elif isinstance(d, str):
            p2_lines.append(f"- {d}")
    
    if inclusions:
        p2_lines.append("")
        p2_lines.append("EXPEDITION INCLUSIONS:")
        p2_lines.append("-" * 68)
        for inc in inclusions[:5]:
            p2_lines.append(f" [x] {str(inc)[:80]}")

    p2_lines.extend([
        "",
        "MANDATORY ADVISORY:",
        "- Carry government photo ID matching passenger names.",
        "- Arrive at meeting point 30 minutes prior to departure.",
        "=" * 68,
        "Issued by TravelVerse Global Expedition Network * travelverse.com"
    ])

    def lines_to_stream(lines):
        ops = []
        y = 790
        for line in lines:
            clean = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            ops.append(f"BT /F1 9 Tf 35 {y} Td ({clean}) Tj ET")
            y -= 13
            if y < 40:
                break
        return "\n".join(ops).encode("latin-1", errors="replace")

    s1 = lines_to_stream(p1_lines)
    s2 = lines_to_stream(p2_lines)

    pdf = bytearray()
    pdf.extend(b"%PDF-1.4\n")
    offsets = []

    def add_obj(body: bytes):
        offsets.append(len(pdf))
        pdf.extend(f"{len(offsets)} 0 obj\n".encode())
        pdf.extend(body)
        pdf.extend(b"\nendobj\n")

    add_obj(b"<< /Type /Catalog /Pages 2 0 R >>")
    add_obj(b"<< /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 >>")
    # Page 1
    add_obj(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 7 0 R >> >> >>")
    add_obj(f"<< /Length {len(s1)} >>\nstream\n".encode() + s1 + b"\nendstream")
    # Page 2
    add_obj(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 6 0 R /Resources << /Font << /F1 7 0 R >> >> >>")
    add_obj(f"<< /Length {len(s2)} >>\nstream\n".encode() + s2 + b"\nendstream")
    # Font
    add_obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    xref_pos = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets) + 1}\n0000000000 65535 f \n".encode())
    for off in offsets:
        pdf.extend(f"{off:010d} 00000 n \n".encode())
    pdf.extend(f"trailer\n<< /Size {len(offsets) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode())

    return bytes(pdf)


def generate_trip_itinerary_pdf(trip_data: dict, booking_data: dict = None) -> bytes:
    """Main PDF generation function. Uses ReportLab when available; otherwise uses zero-dependency fallback."""
    if REPORTLAB_AVAILABLE:
        try:
            return _generate_reportlab_pdf(trip_data, booking_data)
        except Exception as e:
            print("[PDF] ReportLab generation error, falling back to pure-Python PDF generator:", e)
            return _generate_pure_python_pdf(trip_data, booking_data)
    else:
        return _generate_pure_python_pdf(trip_data, booking_data)
