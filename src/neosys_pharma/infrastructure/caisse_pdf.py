"""Documents locaux, sans confirmation bancaire ni valorisation inventée."""
from io import BytesIO
from datetime import datetime
from html import escape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,LongTable,TableStyle,PageBreak

def recu_pdf(data):
    out=BytesIO();styles=getSampleStyleSheet();styles.add(ParagraphStyle(name='CelluleCaisse',fontName='Helvetica',fontSize=9,leading=12,wordWrap='CJK'))
    def p(x):return Paragraph(escape(str(x)),styles['CelluleCaisse'])
    story=[Paragraph('REÇU D’ENCAISSEMENT',styles['Title']),p(data['organisation']),p(data['site']),Spacer(1,12),p('Encaissement '+data['numero_encaissement']+' · Période Z '+str(data['periode_z'])),p('Vente '+data['id']),p(datetime.fromisoformat(data['date']).strftime('%d/%m/%Y %H:%M UTC')),Spacer(1,12)]
    if data.get('encaissement_groupe'):
        group=data['encaissement_groupe']
        story.extend([p('Encaissement groupé '+group['reference']),p('Reçu collectif n° '+str(group['numero'])),Spacer(1,8)])
    rows=[[p(x) for x in ('Produit / conditionnement','Qté','Net TTC (XAF)')]]
    for x in data['lignes']:rows.append([p(x['designation']+' / '+x['conditionnement']),p(x['quantite']),p(x['montants_appliques']['ttc'])])
    table=LongTable(rows,colWidths=[340,45,110],repeatRows=1,hAlign='LEFT');table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e8f1f2')),('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),8),('LINEBELOW',(0,0),(-1,0),.5,colors.grey),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f6f8f9')])]))
    story.extend([table,Spacer(1,14)])
    for k,label in [('ht','Total HT'),('tva','TVA'),('ttc','Net TTC de la vente')]:story.append(p(label+' : '+str(data['totaux'][k])+' XAF'))
    coverage=data.get('prise_en_charge')
    if coverage:
        story.extend([Spacer(1,8),Paragraph('Répartition de la prise en charge',styles['Heading2']),
            p('Part client encaissée : '+str(coverage['part_client_xaf'])+' XAF'),
            p('Parts organismes : '+str(coverage['total_organismes_xaf'])+' XAF')])
        for payer in coverage.get('organismes',[]):
            story.append(p(payer['nom']+' : '+str(payer['montant_xaf'])+' XAF'))
        split=[[p(x) for x in ('Ligne','Net TTC','Part client','Parts organismes')]]
        sale_lines={row['id']:row for row in data['lignes']}
        for split_line in coverage.get('lignes',[]):
            sale_line=sale_lines.get(split_line['ligne_vente_id'],{})
            organisms=', '.join(f"{x['nom']} {x['montant_xaf']}" for x in split_line.get('organismes',[])) or '—'
            split.append([p(sale_line.get('designation','Ligne de vente')),
                p(split_line['net_xaf']),p(split_line['part_client_xaf']),p(organisms)])
        table=LongTable(split,colWidths=[210,70,70,145],repeatRows=1,hAlign='LEFT')
        table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e8f1f2')),
            ('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),6),
            ('LINEBELOW',(0,0),(-1,0),.5,colors.grey)]))
        story.append(table)
    else:
        story.append(p('Net réglé TTC : '+str(data['totaux']['ttc'])+' XAF'))
    story.extend([Spacer(1,12),Paragraph('Règlements acquis',styles['Heading2'])])
    for x in data['reglements']:
        c=x.get('confirmation');label=x['mode']+' : '+str(x['montant'])+' XAF · rendu '+str(x['rendu'])+' XAF'
        if c:label+=' · Réf. '+c['reference']+' · '+c['source']
        story.append(p(label))
    if data.get('fidelite'):story.extend([Spacer(1,12),p('Fidélité : '+str(data['fidelite'].get('points_acquis',data['fidelite'].get('points',0)))+' point(s) acquis. Aucun point utilisé.')])
    def footer(canvas,doc):
        canvas.saveState();canvas.setFont('Helvetica',8);canvas.drawString(42,25,'Vente '+data['id']);canvas.drawRightString(A4[0]-42,25,'Page '+str(doc.page));canvas.restoreState()
    SimpleDocTemplate(out,pagesize=A4,rightMargin=42,leftMargin=42,topMargin=36,bottomMargin=48,title='Reçu '+data['numero_encaissement']).build(story,onFirstPage=footer,onLaterPages=footer)
    return out.getvalue()

def recu_groupe_pdf(data):
    """Reçu collectif; les reçus individuels restent les pièces comptables par vente."""
    out=BytesIO();styles=getSampleStyleSheet();styles.add(ParagraphStyle(name='CelluleGroupe',fontName='Helvetica',fontSize=9,leading=12,wordWrap='CJK'))
    def p(value):return Paragraph(escape(str(value)),styles['CelluleGroupe'])
    story=[
        Paragraph('REÇU COLLECTIF D’ENCAISSEMENT',styles['Title']),
        p(data['organisation']),p(data['site']),Spacer(1,10),
        p('Référence '+data['reference']+' · Reçu n° '+str(data['numero'])+' · Période Z '+str(data['periode_z'])),
        p(datetime.fromisoformat(data['date']).strftime('%d/%m/%Y %H:%M UTC')),
        Spacer(1,12),Paragraph('Ventes et reçus individuels',styles['Heading2']),
    ]
    with_coverage=any(int(sale.get('total_organismes_xaf',0)) for sale in data['ventes'])
    labels=('Vente','Reçu','Net vente','Organismes','Part client') if with_coverage else ('Vente','Reçu individuel','Montant XAF')
    sales=[[p(x) for x in labels]]
    for sale in data['ventes']:
        cells=[p(sale['vente_id']),p(str(sale['numero']).zfill(4))]
        if with_coverage:cells.extend([p(sale['total_vente_xaf']),p(sale['total_organismes_xaf'])])
        cells.append(p(sale['total_xaf']));sales.append(cells)
    table=LongTable(sales,colWidths=[205,45,85,80,80] if with_coverage else [300,90,105],repeatRows=1,hAlign='LEFT')
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e8f1f2')),('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),7),('LINEBELOW',(0,0),(-1,0),.5,colors.grey),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f6f8f9')])]))
    story.extend([table,Spacer(1,12),Paragraph('Règlements du groupe',styles['Heading2'])])
    payments=[[p(x) for x in ('Moyen','Montant présenté','Rendu','Net encaissé','Référence')]]
    for payment in data['reglements']:
        confirmation=payment.get('confirmation') or {}
        payments.append([p(payment['mode']),p(payment['montant']),p(payment['rendu']),p(payment['net']),p(confirmation.get('reference','—'))])
    table=LongTable(payments,colWidths=[90,95,65,95,150],repeatRows=1,hAlign='LEFT')
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e8f1f2')),('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),7),('LINEBELOW',(0,0),(-1,0),.5,colors.grey),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f6f8f9')])]))
    story.extend([table,Spacer(1,12),Paragraph('Total du groupe : '+escape(str(data['total_xaf']))+' XAF',styles['Heading2'])])
    if with_coverage:
        story.extend([p('Net des ventes : '+str(data['total_ventes_xaf'])+' XAF'),
                      p('Parts organismes : '+str(data['total_organismes_xaf'])+' XAF'),
                      p('Parts clients encaissées : '+str(data['total_xaf'])+' XAF')])
    def footer(canvas,doc):
        canvas.saveState();canvas.setFont('Helvetica',8);canvas.drawString(42,25,'Reçu collectif '+data['reference']);canvas.drawRightString(A4[0]-42,25,'Page '+str(doc.page));canvas.restoreState()
    SimpleDocTemplate(out,pagesize=A4,rightMargin=42,leftMargin=42,topMargin=36,bottomMargin=48,title='Reçu collectif '+data['reference']).build(story,onFirstPage=footer,onLaterPages=footer)
    return out.getvalue()

def appel_pdf(org,site,vente,appel):
    out=BytesIO();styles=getSampleStyleSheet();story=[]
    for i,label in enumerate(('CLIENT','PANIER DE PRÉPARATION')):
        if i:story.append(PageBreak())
        for value in (org,site,'TICKET D’APPEL',appel['affichage'],label):story.append(Paragraph(escape(value),styles['Title'] if value==appel['affichage'] else styles['Heading2']))
        story.append(Paragraph('Vente '+escape(str(vente.id)),styles['Normal']));story.append(Paragraph('Document de préparation - ne vaut pas reçu de paiement.',styles['Normal']))
    SimpleDocTemplate(out,pagesize=A4,title='Ticket appel '+appel['affichage']).build(story)
    return out.getvalue()
