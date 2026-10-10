"""PDF émis puis conservé octet pour octet ; aucune lecture de données courantes."""
from io import BytesIO
from xml.sax.saxutils import escape
from datetime import date,datetime
from decimal import Decimal
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,KeepTogether
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pathlib import Path


def proforma_pdf(s):
    import reportlab
    font='Helvetica'
    for path in (Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),Path(reportlab.__file__).parent/'fonts'/'Vera.ttf'):
        if path.exists():
            if 'ProformaUnicode' not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont('ProformaUnicode',str(path)))
            font='ProformaUnicode';break
    out=BytesIO();green=colors.HexColor('#176B50');styles=getSampleStyleSheet()
    normal=ParagraphStyle('PF',fontName=font,fontSize=8.5,leading=12,spaceAfter=5,wordWrap='LTR')
    small=ParagraphStyle('PFSmall',parent=normal,fontSize=7.5,leading=10)
    title=ParagraphStyle('PFTitle',parent=normal,fontSize=18,leading=23,textColor=green,spaceAfter=12)
    def p(v,style=normal):return Paragraph(escape(str(v or '')).replace('\n','<br/>'),style)
    def money(v):return f'{Decimal(str(v)):,.0f}'.replace(',',' ')+' FCFA'
    def day(v):return date.fromisoformat(str(v)[:10]).strftime('%d/%m/%Y')
    org=s['organisation'];site=s['site'];dest=s['destinataire']
    doc=SimpleDocTemplate(out,pagesize=A4,leftMargin=32,rightMargin=32,topMargin=92,bottomMargin=48,title='Facture proforma '+s['reference'],author=org['nom'],pageCompression=1)
    story=[p(org['nom']),*[p(org[k],small) for k in ('raison_sociale','coordonnees','informations_legales') if org.get(k)],p('Site : '+site['code']+' - '+site['nom'],small),*[p(site[k],small) for k in ('adresse','telephone','email') if site.get(k)],Spacer(1,8),p('FACTURE PROFORMA',title),p(f"Référence : {s['reference']}  |  Version : {s['numero']}"),p(f"Émise le {day(s['emis_le'])}  |  Valable jusqu'au {day(s['valide_jusqu_au'])} inclus"),Spacer(1,10),p('DESTINATAIRE',title),p(dest['nom'])]
    for key in ('adresse','telephone'):
        if dest.get(key):story.append(p(dest[key]))
    story.append(Spacer(1,12))
    rows=[[p(x,small) for x in ('Référence / désignation','Conditionnement','Qté','PU TTC','Remises TTC','Total TTC')]]
    for row in s['lignes']:
        m=row['montants_appliques'];discount=Decimal(m['remise_ligne'])+Decimal(m['remise_globale'])
        rows.append([p((row.get('reference')+'\n' if row.get('reference') else '')+row['designation'],small),p(row['conditionnement'],small),p(row['quantite'],small),p(money(row['instantane_tarif']['montant_ttc']),small),p(money(discount),small),p(money(m['ttc']),small)])
    table=Table(rows,colWidths=[175,105,28,74,74,75],repeatRows=1,hAlign='LEFT')
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#DDEEE6')),('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),.3,colors.HexColor('#C8D8CF')),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F4F8F6')])]))
    story.extend([table,Spacer(1,12)])
    totals=s['totaux'];summary=[]
    for label,key in [('TTC avant remises','ttc_initial'),('Remises individuelles','remise_ligne'),('Remise globale','remise_globale'),('Montant HT','ht'),('TVA','tva'),('TOTAL TTC','ttc')]:summary.append([p(label),p(money(totals[key]))])
    amounts=Table(summary,colWidths=[200,155],hAlign='RIGHT');amounts.setStyle(TableStyle([('BACKGROUND',(0,-1),(-1,-1),colors.HexColor('#DDEEE6')),('VALIGN',(0,0),(-1,-1),'TOP')]))
    fiscal={}
    for row in s['lignes']:
        rate=str(row['instantane_tarif']['taux_tva']);m=row['montants_appliques'];base,tax=fiscal.get(rate,(Decimal(0),Decimal(0)));fiscal[rate]=(base+Decimal(m['ht']),tax+Decimal(m['tva']))
    tax_note=[p('TVA '+rate+' % : base HT '+money(base)+' ; taxe '+money(tax),small) for rate,(base,tax) in sorted(fiscal.items())]
    story.append(KeepTogether([amounts,Spacer(1,8),*tax_note,p('Offre commerciale uniquement. Aucun stock réservé, aucun encaissement, aucune créance. Les prix et disponibilités sont revalidés à la reprise.',small)]))
    def page(canvas,doc):
        canvas.saveState();canvas.setFont(font,10);canvas.setFillColor(green);canvas.drawString(32,A4[1]-30,org['nom'][:90]);canvas.setFillColor(colors.black);canvas.setFont(font,8)
        # Long identity fields wrap in a constrained header box.
        header=p(site['code']+' - '+site['nom'],small);_,height=header.wrap(A4[0]-64,48);header.drawOn(canvas,32,A4[1]-42-height)
        canvas.setStrokeColor(green);canvas.line(32,40,A4[0]-32,40);canvas.setFont(font,7);canvas.drawString(32,28,s['reference']+' / V'+str(s['numero'])+' - '+day(s['emis_le']));canvas.drawRightString(A4[0]-32,28,'Page '+str(doc.page));canvas.restoreState()
    doc.build(story,onFirstPage=page,onLaterPages=page);return out.getvalue()
