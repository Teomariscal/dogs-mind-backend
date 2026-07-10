"""
Generación de informes PDF de caso clínico.

Combina en un único PDF las dos piezas más densas del caso:
  - Análisis funcional ABC  (latest CaseEntry de tipo 'abc')
  - Plan de intervención    (latest CaseEntry de tipo 'intervention')

Layout:
  - Cabecera (todas las páginas):
      * Logo TDM en margen izquierdo
      * Logo empresa en margen derecho (solo profesional con logo subido)
      * Bloque centrado con nombre del perro + fecha del informe
  - Cuerpo:
      * Sección "Análisis funcional ABC" (markdown renderizado)
      * Page break
      * Sección "Plan de intervención" (markdown renderizado)
  - Pie (todas las páginas):
      * Disclaimer clínico
      * Numeración de página

Privacidad: NO se incluye nunca el nombre del cliente humano (dueño o cliente
del profesional). Solo nombre del perro y, si aplica, nombre de la empresa.

Markdown soportado (pragmático, suficiente para outputs de Sonnet):
  - Encabezados:  # H1   ## H2   ### H3
  - Listas:       - item   * item   1. item
  - Énfasis:      **bold**   *italic*
  - Párrafos separados por línea en blanco

reportlab es pure-Python (sin deps nativas), seguro para imagen Docker slim.
"""

from __future__ import annotations

import base64
import io
import os
import re
from datetime import datetime
from typing import List, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    BaseDocTemplate, Frame, Image, ListFlowable, ListItem, PageBreak,
    PageTemplate, Paragraph, Spacer,
)
from reportlab.platypus.flowables import HRFlowable
from sqlalchemy.orm import Session

from app.models.case import Case, CaseEntry
from app.models.dog import Dog
from app.models.user import User


# ── Constantes de diseño ─────────────────────────────────────────────────────
TDM_COLOR_GREEN = colors.HexColor("#4a6741")  # verde oliva del icon temporal
TDM_COLOR_TEXT  = colors.HexColor("#2d3a26")  # texto oscuro coherente
TDM_COLOR_MUTED = colors.HexColor("#6b6b6b")
PAGE_MARGIN     = 1.8 * cm
LOGO_SIZE       = 1.6 * cm  # tanto TDM como empresa, mismo box

DISCLAIMER_TEXT = (
    "Este informe se ha generado con asistencia de IA dentro de la app "
    "The Dogs Mind. No sustituye la consulta presencial con un profesional "
    "veterinario o etólogo cuando el caso lo requiera (agresión, mordedura, "
    "conductas autolesivas u otros riesgos clínicos serios)."
)

# ── i18n del chrome del PDF (fix 2026-07-09: informe italiano salía con
# disclaimer/página/títulos en español — la "extraña mezcla" del caso Achille).
# El idioma sale de case.lang; fallback es (comportamiento previo intacto).
_PDF_I18N = {
    "es": {
        "disclaimer": DISCLAIMER_TEXT,
        "page": "Página",
        "abc_title": "Análisis funcional ABC",
        "plan_title": "Plan de intervención",
        "doc_title": "Informe",
    },
    "en": {
        "disclaimer": (
            "This report was generated with AI assistance within The Dogs Mind "
            "app. It does not replace an in-person consultation with a qualified "
            "veterinary or behavior professional when the case requires it "
            "(aggression, biting, self-injurious behavior or other serious "
            "clinical risks)."
        ),
        "page": "Page",
        "abc_title": "Functional analysis (ABC)",
        "plan_title": "Intervention plan",
        "doc_title": "Report",
    },
    "it": {
        "disclaimer": (
            "Questo report è stato generato con l'assistenza dell'IA all'interno "
            "dell'app The Dogs Mind. Non sostituisce la consulenza in presenza di "
            "un medico veterinario qualificato quando il caso lo richieda "
            "(aggressione, morsi, condotte autolesive o altri rischi clinici seri)."
        ),
        "page": "Pagina",
        "abc_title": "Analisi funzionale ABC",
        "plan_title": "Piano d'intervento",
        "doc_title": "Report",
    },
}

# Vía cognitivista italiana: el PDF no puede nombrar "ABC" ni marco conductual.
# Se detecta por el léxico del propio contenido (mismo criterio que el frontend).
_COGNITIVE_RX = re.compile(
    r"evocator|lettura cognitiv|profilo rappresentazional|attività emendativ|zooantropolog",
    re.IGNORECASE,
)


def _pdf_strings(case: Case, abc_md: Optional[str] = None) -> dict:
    lang = ((getattr(case, "lang", None) or "es")[:2]).lower()
    s = dict(_PDF_I18N.get(lang, _PDF_I18N["es"]))
    if lang == "it" and abc_md and _COGNITIVE_RX.search(abc_md):
        s["abc_title"] = "Report clinico"
        s["plan_title"] = "Progetto educativo"
    return s

_LOGO_TDM_PATH = os.path.join(os.path.dirname(__file__), "..", "static", "logo-tdm.png")


# ── Estilos de Paragraph ─────────────────────────────────────────────────────
def _build_styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "h1": ParagraphStyle(
            "h1", parent=base["Heading1"],
            fontName="Helvetica-Bold", fontSize=18, leading=22,
            textColor=TDM_COLOR_GREEN, spaceBefore=10, spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"],
            fontName="Helvetica-Bold", fontSize=14, leading=18,
            textColor=TDM_COLOR_GREEN, spaceBefore=10, spaceAfter=6,
        ),
        "h3": ParagraphStyle(
            "h3", parent=base["Heading3"],
            fontName="Helvetica-Bold", fontSize=12, leading=15,
            textColor=TDM_COLOR_TEXT, spaceBefore=8, spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body", parent=base["BodyText"],
            fontName="Helvetica", fontSize=10.5, leading=14,
            textColor=TDM_COLOR_TEXT, alignment=TA_JUSTIFY,
            spaceBefore=2, spaceAfter=4,
        ),
        "list_item": ParagraphStyle(
            "list_item", parent=base["BodyText"],
            fontName="Helvetica", fontSize=10.5, leading=14,
            textColor=TDM_COLOR_TEXT, alignment=TA_LEFT,
            spaceBefore=1, spaceAfter=1,
        ),
        "header_dog": ParagraphStyle(
            "header_dog", parent=base["BodyText"],
            fontName="Helvetica-Bold", fontSize=11, leading=14,
            textColor=TDM_COLOR_GREEN, alignment=TA_CENTER,
        ),
        "header_meta": ParagraphStyle(
            "header_meta", parent=base["BodyText"],
            fontName="Helvetica", fontSize=8.5, leading=11,
            textColor=TDM_COLOR_MUTED, alignment=TA_CENTER,
        ),
        "section_title": ParagraphStyle(
            "section_title", parent=base["Heading1"],
            fontName="Helvetica-Bold", fontSize=20, leading=24,
            textColor=TDM_COLOR_GREEN, alignment=TA_CENTER,
            spaceBefore=4, spaceAfter=14,
        ),
    }


# ── Conversión Markdown → Flowables ──────────────────────────────────────────
_RE_BOLD   = re.compile(r"\*\*(.+?)\*\*")
_RE_ITALIC = re.compile(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)")
# Caracteres XML que deben escaparse antes de aplicar inline markdown.
_XML_ESCAPE = {"&": "&amp;", "<": "&lt;", ">": "&gt;"}


def _escape_xml(text: str) -> str:
    out = []
    for ch in text:
        out.append(_XML_ESCAPE.get(ch, ch))
    return "".join(out)


def _inline_markdown(text: str) -> str:
    """Convierte **bold**/*italic* a <b>/<i> de reportlab. Resto en plano."""
    s = _escape_xml(text)
    s = _RE_BOLD.sub(r"<b>\1</b>", s)
    s = _RE_ITALIC.sub(r"<i>\1</i>", s)
    return s


def _flush_paragraph(buf: List[str], styles: dict, out: List):
    if not buf:
        return
    text = " ".join(line.strip() for line in buf if line.strip())
    if text:
        out.append(Paragraph(_inline_markdown(text), styles["body"]))
    buf.clear()


def _flush_list(items: List[str], styles: dict, out: List):
    if not items:
        return
    flowables = [
        ListItem(Paragraph(_inline_markdown(it), styles["list_item"]), leftIndent=10)
        for it in items
    ]
    out.append(ListFlowable(
        flowables,
        bulletType="bullet", start="•",
        leftIndent=14, bulletFontName="Helvetica", bulletFontSize=10.5,
        spaceBefore=2, spaceAfter=4,
    ))
    items.clear()


def markdown_to_flowables(md: str, styles: dict) -> List:
    """
    Convierte markdown plano a una lista de Flowables.
    Soporta: # ## ###, listas con - * o "1. ", **bold**, *italic*, párrafos.
    Suficiente para los outputs típicos de Sonnet 4.6 en clínica.
    """
    if not md:
        return []
    out: List = []
    para_buf: List[str] = []
    list_buf: List[str] = []

    for raw in md.splitlines():
        line = raw.rstrip()
        if not line.strip():
            _flush_paragraph(para_buf, styles, out)
            _flush_list(list_buf, styles, out)
            continue

        # Encabezados
        m = re.match(r"^(#{1,3})\s+(.+)$", line)
        if m:
            _flush_paragraph(para_buf, styles, out)
            _flush_list(list_buf, styles, out)
            level = len(m.group(1))
            style_key = {1: "h1", 2: "h2", 3: "h3"}[level]
            out.append(Paragraph(_inline_markdown(m.group(2)), styles[style_key]))
            continue

        # Lista (- item, * item, 1. item)
        m = re.match(r"^\s*(?:[-*]|\d+\.)\s+(.+)$", line)
        if m:
            _flush_paragraph(para_buf, styles, out)
            list_buf.append(m.group(1))
            continue

        # Línea normal — acumula párrafo
        _flush_list(list_buf, styles, out)
        para_buf.append(line)

    _flush_paragraph(para_buf, styles, out)
    _flush_list(list_buf, styles, out)
    return out


# ── Header / Footer en cada página ───────────────────────────────────────────
def _draw_header_footer(
    canvas: Canvas,
    doc: BaseDocTemplate,
    *,
    dog_label: str,
    report_date: str,
    company_name: Optional[str],
    company_logo_image: Optional[Image],
    disclaimer_text: str = DISCLAIMER_TEXT,
    page_label: str = "Página",
):
    canvas.saveState()

    page_w, page_h = A4
    top_y = page_h - PAGE_MARGIN

    # Logo TDM (esquina superior izquierda)
    if os.path.exists(_LOGO_TDM_PATH):
        canvas.drawImage(
            _LOGO_TDM_PATH,
            PAGE_MARGIN, top_y - LOGO_SIZE,
            width=LOGO_SIZE, height=LOGO_SIZE,
            preserveAspectRatio=True, mask="auto",
        )

    # Logo empresa (esquina superior derecha) — solo si profesional con logo
    if company_logo_image is not None:
        try:
            company_logo_image.drawHeight = LOGO_SIZE
            company_logo_image.drawWidth  = LOGO_SIZE
            company_logo_image.drawOn(
                canvas,
                page_w - PAGE_MARGIN - LOGO_SIZE,
                top_y - LOGO_SIZE,
            )
        except Exception:
            # Logo corrupto: no romper el PDF entero por el logo
            pass

    # Bloque central: nombre perro + fecha
    canvas.setFillColor(TDM_COLOR_GREEN)
    canvas.setFont("Helvetica-Bold", 11)
    canvas.drawCentredString(page_w / 2, top_y - 0.4 * cm, dog_label)
    canvas.setFillColor(TDM_COLOR_MUTED)
    canvas.setFont("Helvetica", 8.5)
    meta_parts = [report_date]
    if company_name:
        meta_parts.append(company_name)
    canvas.drawCentredString(page_w / 2, top_y - 0.95 * cm, "  ·  ".join(meta_parts))

    # Línea separadora bajo cabecera
    canvas.setStrokeColor(TDM_COLOR_GREEN)
    canvas.setLineWidth(0.4)
    canvas.line(
        PAGE_MARGIN, top_y - LOGO_SIZE - 0.2 * cm,
        page_w - PAGE_MARGIN, top_y - LOGO_SIZE - 0.2 * cm,
    )

    # Footer: disclaimer + número de página
    footer_top = PAGE_MARGIN + 1.6 * cm
    canvas.setStrokeColor(TDM_COLOR_GREEN)
    canvas.line(PAGE_MARGIN, footer_top, page_w - PAGE_MARGIN, footer_top)

    canvas.setFillColor(TDM_COLOR_MUTED)
    canvas.setFont("Helvetica-Oblique", 7.5)
    # Wrap manual del disclaimer (texto fijo, ancho conocido)
    disclaimer_lines = _wrap_text_for_canvas(
        canvas, disclaimer_text,
        font="Helvetica-Oblique", size=7.5,
        max_width=page_w - 2 * PAGE_MARGIN,
    )
    y = footer_top - 0.35 * cm
    for line in disclaimer_lines:
        canvas.drawString(PAGE_MARGIN, y, line)
        y -= 0.32 * cm

    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(
        page_w - PAGE_MARGIN, PAGE_MARGIN * 0.6,
        f"{page_label} {doc.page}",
    )

    canvas.restoreState()


def _wrap_text_for_canvas(canvas: Canvas, text: str, *, font: str, size: float, max_width: float) -> List[str]:
    """Wrap básico por palabras usando stringWidth del propio canvas."""
    canvas.setFont(font, size)
    words = text.split()
    lines: List[str] = []
    current = ""
    for w in words:
        candidate = (current + " " + w).strip()
        if canvas.stringWidth(candidate, font, size) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines


# ── Helpers para extraer entries y datos del header ──────────────────────────
def _latest_entry_content(case_id, entry_type: str, db: Session) -> Optional[str]:
    e = (
        db.query(CaseEntry)
        .filter(CaseEntry.case_id == case_id, CaseEntry.type == entry_type)
        .order_by(CaseEntry.created_at.desc())
        .first()
    )
    return e.content if e else None


def _resolve_dog_label(case: Case, db: Session) -> str:
    """Devuelve el nombre del perro a mostrar en cabecera. Sin datos de cliente humano."""
    if case.dog_id:
        dog = db.query(Dog).filter(Dog.id == case.dog_id).first()
        if dog:
            return dog.name
    if case.client_dog_name:
        return case.client_dog_name
    return "Caso clínico"


def _decode_logo_data_url(data_url: str) -> Optional[Image]:
    """Convierte un data URL base64 (image/jpeg|png|webp) a un Image flowable de reportlab."""
    if not data_url:
        return None
    m = re.match(r"^data:image/(jpeg|png|webp);base64,(.+)$", data_url)
    if not m:
        return None
    try:
        raw = base64.b64decode(m.group(2), validate=True)
    except Exception:
        return None
    try:
        return Image(io.BytesIO(raw), width=LOGO_SIZE, height=LOGO_SIZE, kind="proportional")
    except Exception:
        return None


# ── API pública ──────────────────────────────────────────────────────────────
def build_case_pdf(case: Case, user: User, db: Session) -> bytes:
    """
    Genera el PDF del caso (análisis + plan unificados).

    Asume que el caller ha verificado que el caso pertenece al usuario y que
    EXISTEN entries de 'abc' y de 'intervention' (el endpoint hace esa guard).
    """
    abc_md  = _latest_entry_content(case.id, "abc", db)
    plan_md = _latest_entry_content(case.id, "intervention", db)
    if not abc_md or not plan_md:
        # Defensa interna: el caller ya debería filtrar; lanzamos para no producir un PDF vacío.
        raise ValueError("El caso no tiene aún análisis ABC y plan de intervención generados.")

    styles      = _build_styles()
    dog_label   = _resolve_dog_label(case, db)
    report_date = datetime.utcnow().strftime("%d/%m/%Y")
    strings     = _pdf_strings(case, abc_md)
    company_name  = user.company_name if user.account_type == "professional" else None
    company_logo  = (
        _decode_logo_data_url(user.company_logo_base64)
        if user.account_type == "professional" and user.company_logo_base64
        else None
    )

    buf = io.BytesIO()
    doc = BaseDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=PAGE_MARGIN, rightMargin=PAGE_MARGIN,
        topMargin=PAGE_MARGIN + LOGO_SIZE + 0.6 * cm,    # deja sitio a header
        bottomMargin=PAGE_MARGIN + 1.8 * cm,             # deja sitio a footer
        title=f"{strings['doc_title']} — {dog_label} — {report_date}",
        author="The Dogs Mind",
    )
    frame = Frame(
        doc.leftMargin, doc.bottomMargin,
        doc.width, doc.height, id="content",
    )

    def _on_page(canvas, doc_):
        _draw_header_footer(
            canvas, doc_,
            dog_label=dog_label,
            report_date=report_date,
            company_name=company_name,
            company_logo_image=company_logo,
            disclaimer_text=strings["disclaimer"],
            page_label=strings["page"],
        )

    doc.addPageTemplates([PageTemplate(id="default", frames=[frame], onPage=_on_page)])

    story: List = []
    story.append(Paragraph(strings["abc_title"], styles["section_title"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=TDM_COLOR_GREEN, spaceAfter=8))
    story.extend(markdown_to_flowables(abc_md, styles))

    story.append(PageBreak())
    story.append(Paragraph(strings["plan_title"], styles["section_title"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=TDM_COLOR_GREEN, spaceAfter=8))
    story.extend(markdown_to_flowables(plan_md, styles))

    doc.build(story)
    return buf.getvalue()


def has_required_entries_for_export(case_id, db: Session) -> bool:
    """True solo si el caso tiene al menos un 'abc' Y un 'intervention'."""
    has_abc  = db.query(CaseEntry).filter(CaseEntry.case_id == case_id, CaseEntry.type == "abc").first() is not None
    has_plan = db.query(CaseEntry).filter(CaseEntry.case_id == case_id, CaseEntry.type == "intervention").first() is not None
    return has_abc and has_plan


def build_export_filename(case: Case, db: Session) -> str:
    """Nombre de archivo seguro para Content-Disposition (slug + fecha)."""
    dog_label = _resolve_dog_label(case, db)
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", dog_label.strip()) or "caso"
    return f"informe_{slug}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"


# ── PDFs para variantes accesibles (Plan Sencillo + ABC explained) ──────────
#
# Mismo header/footer que `build_case_pdf` (logo TDM + logo empresa si
# profesional con logo subido + nombre perro + fecha + disclaimer + paginación).
# Solo cambia el contenido y el título de sección.

def _build_simple_pdf(
    case: Case,
    user: User,
    db: Session,
    *,
    section_title: str,
    body_md: str,
    pdf_title_prefix: str,
) -> bytes:
    """Builder común para los PDFs accesibles (plan-simple, abc-explained)."""
    if not body_md or not body_md.strip():
        raise ValueError("PDF builder llamado sin contenido.")

    styles      = _build_styles()
    dog_label   = _resolve_dog_label(case, db)
    report_date = datetime.utcnow().strftime("%d/%m/%Y")
    strings     = _pdf_strings(case, body_md)
    company_name  = user.company_name if user.account_type == "professional" else None
    company_logo  = (
        _decode_logo_data_url(user.company_logo_base64)
        if user.account_type == "professional" and user.company_logo_base64
        else None
    )

    buf = io.BytesIO()
    doc = BaseDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=PAGE_MARGIN, rightMargin=PAGE_MARGIN,
        topMargin=PAGE_MARGIN + LOGO_SIZE + 0.6 * cm,
        bottomMargin=PAGE_MARGIN + 1.8 * cm,
        title=f"{pdf_title_prefix} — {dog_label} — {report_date}",
        author="The Dogs Mind",
    )
    frame = Frame(
        doc.leftMargin, doc.bottomMargin,
        doc.width, doc.height, id="content",
    )

    def _on_page(canvas, doc_):
        _draw_header_footer(
            canvas, doc_,
            dog_label=dog_label,
            report_date=report_date,
            company_name=company_name,
            company_logo_image=company_logo,
            disclaimer_text=strings["disclaimer"],
            page_label=strings["page"],
        )

    doc.addPageTemplates([PageTemplate(id="default", frames=[frame], onPage=_on_page)])

    story: List = []
    story.append(Paragraph(section_title, styles["section_title"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=TDM_COLOR_GREEN, spaceAfter=8))
    story.extend(markdown_to_flowables(body_md, styles))

    doc.build(story)
    return buf.getvalue()


def build_plan_simple_pdf(case: Case, user: User, db: Session) -> bytes:
    """PDF de la versión accesible del plan (Plan Sencillo · Pet Owners)."""
    body = _latest_entry_content(case.id, "plan_simple", db)
    if not body:
        raise ValueError("El caso no tiene aún plan sencillo generado.")
    return _build_simple_pdf(
        case, user, db,
        section_title="Plan sencillo · Pet Owners",
        body_md=body,
        pdf_title_prefix="Plan sencillo",
    )


def build_abc_explained_pdf(case: Case, user: User, db: Session) -> bytes:
    """PDF de la versión accesible del análisis ABC (Cecilia te explica)."""
    body = _latest_entry_content(case.id, "abc_explained", db)
    if not body:
        raise ValueError("El caso no tiene aún explicación accesible del análisis ABC.")
    return _build_simple_pdf(
        case, user, db,
        section_title="Cecilia te explica",
        body_md=body,
        pdf_title_prefix="Análisis explicado",
    )


def build_simple_pdf_filename(case: Case, db: Session, *, kind: str) -> str:
    """Filename para los PDFs accesibles. kind ∈ {'plan-simple','abc-explained'}."""
    dog_label = _resolve_dog_label(case, db)
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", dog_label.strip()) or "caso"
    prefix = {
        "plan-simple": "plan_sencillo",
        "abc-explained": "analisis_explicado",
    }.get(kind, "informe")
    return f"{prefix}_{slug}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
