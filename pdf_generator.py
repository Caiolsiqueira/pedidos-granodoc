import io
from datetime import datetime
from typing import Dict, Any, List, Optional
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

def generate_consolidated_pdf(data_consolidada: Dict[str, Any]) -> io.BytesIO:
    """
    Gera um relatório PDF elegante e profissional da lista consolidada de compras.
    Retorna um buffer BytesIO pronto para streaming de download HTTP.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    
    # Estilos customizados
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#1E293B'),
        spaceAfter=4
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#64748B'),
        spaceAfter=12
    )

    section_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#0F172A'),
        spaceBefore=12,
        spaceAfter=6
    )

    table_cell = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#334155')
    )

    table_cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#0F172A')
    )

    table_header = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.white
    )

    story = []

    # Cabeçalho Principal
    story.append(Paragraph("PEDIDOS GRANODOC", title_style))
    story.append(Paragraph(
        f"ORDEM CONSOLIDADA DE SUPRIMENTOS & COMPRAS | Data dos Pedidos: <b>{data_consolidada.get('data', '')}</b> | Emitido em: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        subtitle_style
    ))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0284C7'), spaceBefore=0, spaceAfter=10))

    # Resumo Geral
    resumo = data_consolidada.get("resumo", {})
    tot_pedidos = resumo.get("total_pedidos", 0) or 0
    tot_pendentes = resumo.get("total_pendentes", 0) or 0
    tot_aprovados = resumo.get("total_aprovados", 0) or 0
    tot_comprados = resumo.get("total_comprados", 0) or 0
    setores_atv = resumo.get("total_setores_ativos", 0) or 0

    resumo_text = f"<b>Total de Pedidos na Data:</b> {tot_pedidos} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Praças Solicitantes:</b> {setores_atv} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Status:</b> {tot_pendentes} Pendentes, {tot_aprovados} Aprovados, {tot_comprados} Comprados"
    story.append(Paragraph(resumo_text, table_cell))
    story.append(Spacer(1, 10))

    # 1. Tabela de Insumos de Catálogo
    catalogo = data_consolidada.get("catalogo", [])
    story.append(Paragraph(f"1. Insumos Oficiais do Catálogo ({len(catalogo)} itens)", section_heading))

    if catalogo:
        cat_table_data = [[
            Paragraph("Produto", table_header),
            Paragraph("Categoria", table_header),
            Paragraph("Qtd Total", table_header),
            Paragraph("Unidade", table_header),
            Paragraph("Praças Solicitantes", table_header),
        ]]

        for item in catalogo:
            # Formatar quantidade (ex: 2.0 -> 2, 2.5 -> 2.5)
            qtd = item.get("quantidade_total", 0)
            qtd_str = f"{qtd:g}" if isinstance(qtd, (int, float)) else str(qtd)

            cat_table_data.append([
                Paragraph(item.get("produto_nome", ""), table_cell_bold),
                Paragraph(item.get("categoria", "Geral"), table_cell),
                Paragraph(qtd_str, table_cell_bold),
                Paragraph(item.get("unidade_medida", ""), table_cell),
                Paragraph(item.get("setores_solicitantes", "").replace(",", ", "), table_cell),
            ])

        cat_table = Table(cat_table_data, colWidths=[2.2 * inch, 1.3 * inch, 0.8 * inch, 0.8 * inch, 2.4 * inch])
        cat_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
        ]))
        story.append(cat_table)
    else:
        story.append(Paragraph("<i>Nenhum insumo de catálogo solicitado para esta data.</i>", table_cell))

    story.append(Spacer(1, 14))

    # 2. Tabela de Itens Avulsos / Extras
    avulsos = data_consolidada.get("avulsos", [])
    story.append(Paragraph(f"2. Itens Avulsos / Especiais Fora de Catálogo ({len(avulsos)} itens)", section_heading))

    if avulsos:
        av_table_data = [[
            Paragraph("Descrição do Item", table_header),
            Paragraph("Qtd Total", table_header),
            Paragraph("Unidade", table_header),
            Paragraph("Praças Solicitantes", table_header),
            Paragraph("Observações Relevantes", table_header),
        ]]

        for av in avulsos:
            qtd = av.get("quantidade_total", 0)
            qtd_str = f"{qtd:g}" if isinstance(qtd, (int, float)) else str(qtd)

            av_table_data.append([
                Paragraph(av.get("descricao_item", ""), table_cell_bold),
                Paragraph(qtd_str, table_cell_bold),
                Paragraph(av.get("unidade_medida", ""), table_cell),
                Paragraph(av.get("setores_solicitantes", "").replace(",", ", "), table_cell),
                Paragraph(av.get("notas_relevantes", "") or "-", table_cell),
            ])

        av_table = Table(av_table_data, colWidths=[2.2 * inch, 0.8 * inch, 0.8 * inch, 1.5 * inch, 2.2 * inch])
        av_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#D97706')),  # tom âmbar para avulsos
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#FCD34D')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FEFCE8')]),
        ]))
        story.append(av_table)
    else:
        story.append(Paragraph("<i>Nenhum item avulso solicitado para esta data.</i>", table_cell))

    story.append(Spacer(1, 24))

    # Assinatura e Aprovação
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#94A3B8'), spaceBefore=10, spaceAfter=20))
    
    sig_data = [
        [
            Paragraph("___________________________________________<br/><b>Responsável pelas Cotações / Compras</b><br/>Granodoc Restaurante & Pizzaria", table_cell),
            Paragraph("___________________________________________<br/><b>Gerência / Administração Geral</b><br/>Data de Liberação: ____/____/________", table_cell)
        ]
    ]
    sig_table = Table(sig_data, colWidths=[3.7 * inch, 3.7 * inch])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(sig_table)

    doc.build(story)
    buffer.seek(0)
    return buffer


def generate_daily_orders_pdf(
    orders: List[Dict[str, Any]],
    date_str: str,
    sector: Optional[str] = None
) -> io.BytesIO:
    """
    Gera um relatório PDF elegante e profissional dos pedidos da Aba 1 (Visão Diária).
    Suporta exportação individual de uma praça ou relatório geral diário com quebra de página por setor.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'DailyTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=19,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=2
    )

    subtitle_style = ParagraphStyle(
        'DailySubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#475569')
    )

    section_heading = ParagraphStyle(
        'DailySectionHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor('#0F172A'),
        spaceBefore=10,
        spaceAfter=5
    )

    table_cell = ParagraphStyle(
        'DailyTableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#334155')
    )

    table_cell_bold = ParagraphStyle(
        'DailyTableCellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#0F172A')
    )

    table_cell_center = ParagraphStyle(
        'DailyTableCellCenter',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        alignment=1,
        textColor=colors.HexColor('#334155')
    )

    table_cell_center_bold = ParagraphStyle(
        'DailyTableCellCenterBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        alignment=1,
        textColor=colors.HexColor('#0F172A')
    )

    conferencia_style = ParagraphStyle(
        'DailyConferenciaStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=12,
        alignment=1,
        textColor=colors.HexColor('#64748B')
    )

    table_header = ParagraphStyle(
        'DailyTableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.white
    )

    table_header_center = ParagraphStyle(
        'DailyTableHeaderCenter',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        alignment=1,
        textColor=colors.white
    )

    obs_style = ParagraphStyle(
        'DailyObsStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#334155')
    )

    story = []

    # Formatação da data (YYYY-MM-DD -> DD/MM/YYYY)
    parts = date_str.split('-')
    date_formatted = f"{parts[2]}/{parts[1]}/{parts[0]}" if len(parts) == 3 else date_str
    now_str = datetime.now().strftime("%d/%m/%Y às %H:%M")

    # Filtra por setor se especificado
    if sector and sector.lower() != "todos":
        filtered_orders = [o for o in orders if o.get("nome_setor", "").lower() == sector.lower()]
    else:
        filtered_orders = list(orders)

    # Organizar por praça na ordem padrão
    standard_sectors = ["Pizza", "Cozinha", "Bar", "Salão"]
    grouped_sectors: Dict[str, List[Dict[str, Any]]] = {}

    if sector and sector.lower() != "todos":
        target_name = sector.capitalize()
        grouped_sectors[target_name] = filtered_orders
    else:
        for sec in standard_sectors:
            sec_orders = [o for o in filtered_orders if o.get("nome_setor", "").lower() == sec.lower()]
            if sec_orders:
                grouped_sectors[sec] = sec_orders

        for o in filtered_orders:
            s_name = o.get("nome_setor", "Outro")
            if s_name not in grouped_sectors and not any(k.lower() == s_name.lower() for k in standard_sectors):
                grouped_sectors.setdefault(s_name, []).append(o)

    # Caso geral sem nenhum pedido
    if not grouped_sectors:
        story.append(Paragraph("GRANODOC SUPRIMENTOS - GESTÃO DE REQUISIÇÕES", title_style))
        story.append(Paragraph(
            f"Relatório Diário de Pedidos | Data: <b>{date_formatted}</b> | Emitido em: {now_str}",
            subtitle_style
        ))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#BE123C'), spaceBefore=4, spaceAfter=20))
        story.append(Paragraph("<i>Nenhum pedido registrado para a data selecionada.</i>", table_cell))
        doc.build(story)
        buffer.seek(0)
        return buffer

    # Renderiza cada setor (com quebra de página se for relatório consolidado de múltiplos setores)
    for idx, (sec_name, sec_orders) in enumerate(grouped_sectors.items()):
        if idx > 0:
            story.append(PageBreak())

        # Status geral do setor na data
        if sec_orders:
            statuses = list(dict.fromkeys([o.get("status", "Pendente") for o in sec_orders]))
            status_display = ", ".join(statuses)
            horarios = [o.get("data_hora", "").split(" ")[1][:5] for o in sec_orders if " " in o.get("data_hora", "")]
            horarios_str = ", ".join(horarios) if horarios else "-"
        else:
            status_display = "Sem Pedido"
            horarios_str = "-"

        # 1. Cabeçalho Oficial
        story.append(Paragraph("GRANODOC SUPRIMENTOS - GESTÃO DE REQUISIÇÕES", title_style))
        header_text = (
            f"<b>Praça: {sec_name.upper()}</b> &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"Data do Pedido: <b>{date_formatted}</b> &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"Status: <b>{status_display}</b> &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"Horário: <b>{horarios_str}</b><br/>"
            f"<font color='#64748B'>Emitido em: {now_str} &nbsp;&bull;&nbsp; Painel da Administração</font>"
        )
        story.append(Paragraph(header_text, subtitle_style))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#BE123C'), spaceBefore=4, spaceAfter=10))

        if not sec_orders:
            story.append(Spacer(1, 15))
            story.append(Paragraph(f"<i>Nenhum pedido registrado para a Praça {sec_name} nesta data ({date_formatted}).</i>", table_cell))
            story.append(Spacer(1, 30))
            continue

        # Coletar itens de catálogo e itens avulsos
        cat_items = []
        av_items = []
        observacoes_list = []

        for ord_data in sec_orders:
            if ord_data.get("itens_catalogo"):
                cat_items.extend(ord_data["itens_catalogo"])
            if ord_data.get("itens_avulsos"):
                av_items.extend(ord_data["itens_avulsos"])
            obs = ord_data.get("observacoes", "")
            if obs and obs.strip():
                observacoes_list.append(obs.strip())

        # 2. Tabela de Insumos Oficiais do Catálogo
        story.append(Paragraph(f"1. Insumos Oficiais do Catálogo ({len(cat_items)} itens)", section_heading))

        if cat_items:
            cat_table_data = [[
                Paragraph("Item / Insumo", table_header),
                Paragraph("Categoria", table_header),
                Paragraph("Qtd Solicitada", table_header_center),
                Paragraph("Unidade", table_header_center),
                Paragraph("Conferência ( [  ] )", table_header_center),
            ]]

            for item in cat_items:
                qtd = item.get("quantidade_pedida", 0)
                qtd_str = f"{qtd:g}" if isinstance(qtd, (int, float)) else str(qtd)
                nome = item.get("nome_produto", "")
                cat = item.get("categoria", "Geral")
                un = item.get("unidade_medida", "un")

                cat_table_data.append([
                    Paragraph(nome, table_cell_bold),
                    Paragraph(cat, table_cell),
                    Paragraph(qtd_str, table_cell_center_bold),
                    Paragraph(un, table_cell_center),
                    Paragraph("[ &nbsp;&nbsp;&nbsp;&nbsp; ]", conferencia_style),
                ])

            cat_table = Table(cat_table_data, colWidths=[2.5 * inch, 1.5 * inch, 1.0 * inch, 1.0 * inch, 1.5 * inch])
            cat_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
                ('ALIGN', (0, 0), (1, -1), 'LEFT'),
                ('ALIGN', (2, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
            ]))
            story.append(cat_table)
        else:
            story.append(Paragraph("<i>Nenhum insumo de catálogo solicitado nesta praça.</i>", table_cell))

        story.append(Spacer(1, 10))

        # 3. Tabela de Itens Avulsos / Extras (se houver)
        if av_items:
            story.append(Paragraph(f"2. Itens Avulsos / Extras Fora de Catálogo ({len(av_items)} itens)", section_heading))
            av_table_data = [[
                Paragraph("Descrição do Item Avulso", table_header),
                Paragraph("Qtd Solicitada", table_header_center),
                Paragraph("Unidade", table_header_center),
                Paragraph("Conferência ( [  ] )", table_header_center),
            ]]

            for av in av_items:
                qtd = av.get("quantidade", 0)
                qtd_str = f"{qtd:g}" if isinstance(qtd, (int, float)) else str(qtd)
                desc = av.get("descricao_item", "")
                un = av.get("unidade_medida", "un")

                av_table_data.append([
                    Paragraph(desc, table_cell_bold),
                    Paragraph(qtd_str, table_cell_center_bold),
                    Paragraph(un, table_cell_center),
                    Paragraph("[ &nbsp;&nbsp;&nbsp;&nbsp; ]", conferencia_style),
                ])

            av_table = Table(av_table_data, colWidths=[3.5 * inch, 1.25 * inch, 1.25 * inch, 1.5 * inch])
            av_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#D97706')),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#FCD34D')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FEFCE8')]),
            ]))
            story.append(av_table)
            story.append(Spacer(1, 10))

        # 4. Observações Gerais
        if observacoes_list:
            story.append(Paragraph("3. Observações do Operador", section_heading))
            obs_joined = "<br/>&bull; ".join(observacoes_list)
            obs_box_data = [[Paragraph(f"&bull; {obs_joined}", obs_style)]]
            obs_table = Table(obs_box_data, colWidths=[7.5 * inch])
            obs_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F1F5F9')),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ]))
            story.append(obs_table)
            story.append(Spacer(1, 12))

        # 5. Rodapé com Assinaturas
        story.append(Spacer(1, 14))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#94A3B8'), spaceBefore=5, spaceAfter=15))

        sig_data = [
            [
                Paragraph(f"___________________________________________<br/><b>Responsável pela Praça ({sec_name})</b><br/>Assinatura: ____________________", table_cell_center),
                Paragraph("___________________________________________<br/><b>Visto da Administração</b><br/>Conferido em: ____/____/________", table_cell_center)
            ]
        ]
        sig_table = Table(sig_data, colWidths=[3.75 * inch, 3.75 * inch])
        sig_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(sig_table)

    doc.build(story)
    buffer.seek(0)
    return buffer

def generate_completed_orders_pdf(
    orders: List[Dict[str, Any]],
    date_str: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    sector: Optional[str] = None
) -> io.BytesIO:
    """
    Gera um relatório PDF executivo dos pedidos concluídos (arquivados com status 'Comprado').
    Exibe dados consolidados por pedido, itens atendidos (catálogo e avulsos) e observações.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CompletedDocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        textColor=colors.HexColor('#064E3B'),
        spaceAfter=4
    )

    subtitle_style = ParagraphStyle(
        'CompletedDocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#475569'),
        spaceAfter=10
    )

    card_header_style = ParagraphStyle(
        'CardHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=colors.white
    )

    section_heading = ParagraphStyle(
        'CompletedSectionHeading',
        parent=styles['Heading3'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=colors.HexColor('#0F172A'),
        spaceBefore=6,
        spaceAfter=4
    )

    table_cell = ParagraphStyle(
        'CompletedTableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#334155')
    )

    table_cell_bold = ParagraphStyle(
        'CompletedTableCellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#0F172A')
    )

    table_cell_center = ParagraphStyle(
        'CompletedTableCellCenter',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        alignment=1,
        textColor=colors.HexColor('#334155')
    )

    table_cell_center_bold = ParagraphStyle(
        'CompletedTableCellCenterBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        alignment=1,
        textColor=colors.HexColor('#065F46')
    )

    table_header = ParagraphStyle(
        'CompletedTableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.white
    )

    table_header_center = ParagraphStyle(
        'CompletedTableHeaderCenter',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        alignment=1,
        textColor=colors.white
    )

    obs_style = ParagraphStyle(
        'CompletedObsStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor('#334155')
    )

    story = []

    # Cabeçalho Principal
    story.append(Paragraph("PEDIDOS GRANODOC - HISTÓRICO DE PEDIDOS CONCLUÍDOS", title_style))

    # Formatação do Período
    if date_str and date_str.lower() not in ("todos", "all"):
        p_parts = date_str.split("-")
        periodo_str = f"{p_parts[2]}/{p_parts[1]}/{p_parts[0]}" if len(p_parts) == 3 else date_str
    elif start_date and end_date:
        s_parts = start_date.split("-")
        e_parts = end_date.split("-")
        s_fmt = f"{s_parts[2]}/{s_parts[1]}/{s_parts[0]}" if len(s_parts) == 3 else start_date
        e_fmt = f"{e_parts[2]}/{e_parts[1]}/{e_parts[0]}" if len(e_parts) == 3 else end_date
        periodo_str = f"{s_fmt} até {e_fmt}"
    elif start_date:
        periodo_str = f"A partir de {start_date}"
    else:
        periodo_str = "Todos os Concluídos"

    setor_str = sector if (sector and sector.lower() != "todos") else "Todas as Praças"
    emitido_em = datetime.now().strftime("%d/%m/%Y %H:%M")

    meta_text = (
        f"<b>Período:</b> {periodo_str} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<b>Praça:</b> {setor_str} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<b>Total Concluídos:</b> {len(orders)} pedidos &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<b>Emitido em:</b> {emitido_em}"
    )
    story.append(Paragraph(meta_text, subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#059669'), spaceBefore=0, spaceAfter=12))

    if not orders:
        empty_box = [[Paragraph("<i>Nenhum pedido concluído encontrado para os filtros selecionados.</i>", table_cell)]]
        t = Table(empty_box, colWidths=[7.5 * inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('PADDING', (0, 0), (-1, -1), 16),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        story.append(t)
    else:
        for idx, order in enumerate(orders):
            sec_name = order.get("nome_setor", "Praça")
            dt_raw = order.get("data_hora", "")
            try:
                dt_obj = datetime.strptime(str(dt_raw).split(".")[0], "%Y-%m-%d %H:%M:%S")
                dt_str = dt_obj.strftime("%d/%m/%Y %H:%M")
            except Exception:
                dt_str = str(dt_raw)

            # Barra de identificação do Pedido
            order_header_text = f"<b>PRAÇA: {sec_name.upper()}</b> &nbsp;&bull;&nbsp; Pedido #{order.get('id')} &nbsp;&bull;&nbsp; Data: {dt_str} &nbsp;&bull;&nbsp; Status: COMPRADO / CONCLUÍDO"
            card_head_table = Table(
                [[Paragraph(order_header_text, card_header_style)]],
                colWidths=[7.5 * inch]
            )
            card_head_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#065F46')),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ]))
            story.append(card_head_table)

            # Itens de Catálogo
            cat_items = order.get("itens_catalogo", [])
            av_items = order.get("itens_avulsos", [])
            obs = order.get("observacoes")

            if cat_items:
                story.append(Paragraph(f"<b>Insumos do Catálogo ({len(cat_items)} itens):</b>", section_heading))
                cat_data = [[
                    Paragraph("Produto", table_header),
                    Paragraph("Categoria", table_header),
                    Paragraph("Qtd Atendida", table_header_center),
                    Paragraph("Unidade", table_header_center),
                    Paragraph("Situação", table_header_center),
                ]]
                for ci in cat_items:
                    qtd = ci.get("quantidade_pedida", 0)
                    qtd_str = f"{qtd:g}" if isinstance(qtd, (int, float)) else str(qtd)
                    cat_data.append([
                        Paragraph(ci.get("nome_produto", ""), table_cell_bold),
                        Paragraph(ci.get("categoria", "Geral") or "Geral", table_cell),
                        Paragraph(qtd_str, table_cell_center_bold),
                        Paragraph(ci.get("unidade_medida", "un"), table_cell_center),
                        Paragraph("Concluído", table_cell_center),
                    ])
                t_cat = Table(cat_data, colWidths=[2.7 * inch, 1.8 * inch, 1.0 * inch, 1.0 * inch, 1.0 * inch])
                t_cat.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
                    ('ALIGN', (0, 0), (1, -1), 'LEFT'),
                    ('ALIGN', (2, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                    ('TOPPADDING', (0, 0), (-1, -1), 3),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
                ]))
                story.append(t_cat)

            if av_items:
                story.append(Paragraph(f"<b>Itens Avulsos / Fora de Catálogo ({len(av_items)} itens):</b>", section_heading))
                av_data = [[
                    Paragraph("Descrição do Item Avulso", table_header),
                    Paragraph("Qtd Atendida", table_header_center),
                    Paragraph("Unidade", table_header_center),
                    Paragraph("Situação", table_header_center),
                ]]
                for ai in av_items:
                    qtd = ai.get("quantidade", 0)
                    qtd_str = f"{qtd:g}" if isinstance(qtd, (int, float)) else str(qtd)
                    av_data.append([
                        Paragraph(ai.get("descricao_item", ""), table_cell_bold),
                        Paragraph(qtd_str, table_cell_center_bold),
                        Paragraph(ai.get("unidade_medida", "un"), table_cell_center),
                        Paragraph("Concluído", table_cell_center),
                    ])
                t_av = Table(av_data, colWidths=[3.7 * inch, 1.3 * inch, 1.2 * inch, 1.3 * inch])
                t_av.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#D97706')),
                    ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                    ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                    ('TOPPADDING', (0, 0), (-1, -1), 3),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#FDE68A')),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FFFBEB')]),
                ]))
                story.append(t_av)

            if obs:
                story.append(Spacer(1, 3))
                obs_box = [[Paragraph(f"<b>Nota do Operador:</b> {obs}", obs_style)]]
                t_obs = Table(obs_box, colWidths=[7.5 * inch])
                t_obs.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F1F5F9')),
                    ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('LEFTPADDING', (0, 0), (-1, -1), 6),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ]))
                story.append(t_obs)

            story.append(Spacer(1, 14))

    doc.build(story)
    buffer.seek(0)
    return buffer
