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
    rows=[[p(x) for x in ('Produit / conditionnement','Qté','Net TTC (XAF)')]]
    for x in data['lignes']:rows.append([p(x['designation']+' / '+x['conditionnement']),p(x['quantite']),p(x['montants_appliques']['ttc'])])
    table=LongTable(rows,colWidths=[340,45,110],repeatRows=1,hAlign='LEFT');table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e8f1f2')),('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),8),('LINEBELOW',(0,0),(-1,0),.5,colors.grey),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f6f8f9')])]))
    story.extend([table,Spacer(1,14)])
    for k,label in [('ht','Total HT'),('tva','TVA'),('ttc','Net réglé TTC')]:story.append(p(label+' : '+str(data['totaux'][k])+' XAF'))
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
    """Reçu unique, avec les références et les montants de chaque vente du groupe."""
    out=BytesIO();styles=getSampleStyleSheet();styles.add(ParagraphStyle(name='CelluleGroupe',fontName='Helvetica',fontSize=9,leading=12,wordWrap='CJK'))
    def p(value):return Paragraph(escape(str(value)),styles['CelluleGroupe'])
    story=[Paragraph('REÇU D’ENCAISSEMENT GROUPÉ',styles['Title']),p(data['organisation']),p(data['site']),
        p('Encaissement '+data['numero_encaissement']+' · Période Z '+str(data['periode_z'])),
        p(datetime.fromisoformat(data['date']).strftime('%d/%m/%Y %H:%M UTC')),Spacer(1,12)]
    for sale in data['ventes']:
        story.extend([Paragraph('Vente '+sale['vente_id']+((' · Appel '+sale['numero_appel']) if sale.get('numero_appel') else ''),styles['Heading2'])])
        rows=[[p(x) for x in ('Produit / conditionnement','Qté','Net TTC (XAF)')]]
        for line in sale['lignes']:
            rows.append([p(line['designation']+' / '+line['conditionnement']),p(line['quantite']),p(line['montants_appliques']['ttc'])])
        table=LongTable(rows,colWidths=[340,45,110],repeatRows=1,hAlign='LEFT')
        table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e8f1f2')),('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),8),('LINEBELOW',(0,0),(-1,0),.5,colors.grey),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f6f8f9')])]))
        story.extend([table,p('Total TTC de cette vente : '+sale['totaux']['ttc']+' XAF'),Spacer(1,10)])
    story.extend([Paragraph('Total groupé : '+str(data['total_xaf'])+' XAF',styles['Heading2']),Paragraph('Règlements acquis',styles['Heading2'])])
    for payment in data['reglements']:
        confirmation=payment.get('confirmation');label=payment['mode']+' : '+str(payment['montant'])+' XAF · rendu '+str(payment['rendu'])+' XAF'
        if confirmation:label+=' · Réf. '+confirmation['reference']+' · '+confirmation['source']
        story.append(p(label))
    if data.get('fidelite'):
        story.extend([Spacer(1,10),p('Fidélité : '+str(data['fidelite'].get('points_acquis',0))+' point(s) acquis au total. Aucun point utilisé.')])
    def footer(canvas,doc):
        canvas.saveState();canvas.setFont('Helvetica',8);canvas.drawString(42,25,'Encaissement '+data['numero_encaissement']+' · '+data['id']);canvas.drawRightString(A4[0]-42,25,'Page '+str(doc.page));canvas.restoreState()
    SimpleDocTemplate(out,pagesize=A4,rightMargin=42,leftMargin=42,topMargin=36,bottomMargin=48,title='Reçu groupé '+data['numero_encaissement']).build(story,onFirstPage=footer,onLaterPages=footer)
    return out.getvalue()

def appel_pdf(org,site,vente,appel):
    out=BytesIO();styles=getSampleStyleSheet();story=[]
    for i,label in enumerate(('CLIENT','PANIER DE PRÉPARATION')):
        if i:story.append(PageBreak())
        for value in (org,site,'TICKET D’APPEL',appel['affichage'],label):story.append(Paragraph(escape(value),styles['Title'] if value==appel['affichage'] else styles['Heading2']))
        story.append(Paragraph('Vente '+escape(str(vente.id)),styles['Normal']));story.append(Paragraph('Document de préparation - ne vaut pas reçu de paiement.',styles['Normal']))
    SimpleDocTemplate(out,pagesize=A4,title='Ticket appel '+appel['affichage']).build(story)
    return out.getvalue()
