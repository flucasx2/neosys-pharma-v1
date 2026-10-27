"""Documents administratifs sans mentions fiscales inventées, montants serveur."""
from html import escape
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, LongTable, TableStyle


def document_pdf(snapshot, *, definitif=False):
    out=BytesIO();styles=getSampleStyleSheet()
    def p(value):return Paragraph(escape(str(value)),styles['Normal'])
    label={'BORDEREAU':'BORDEREAU DE PRESENTATION','FACTURE':'FACTURE ORGANISME','RECAPITULATIF':'RECAPITULATIF DE FACTURES','LOT':'LOT DE RECAPITULATIFS'}[snapshot['genre']]
    mark='RECETTE ISOLEE - SANS VALIDITE FISCALE' if definitif else 'BROUILLON - NON EMIS - NE PAS TRANSMETTRE'
    story=[Paragraph(label,styles['Title']),p(mark),Spacer(1,12)]
    for key in ('reference','reference_validation','emetteur','destinataire','convention','periode','auteur_id','date'):
        value=snapshot.get(key)
        if isinstance(value,dict):
            if key=='emetteur':value=' / '.join(str(x) for x in (value.get('nom'),value.get('raison_sociale'),value.get('coordonnees'),value.get('site',{}).get('nom')) if x)
            elif key=='destinataire':value=' / '.join(str(x) for x in (value.get('nom'),value.get('code')) if x)
            elif key=='convention':value=f"{value['code']} version {value['version']} / {value.get('reference_contractuelle') or 'Référence contractuelle non renseignée'}"
        if value is not None:story.extend([p(key.replace('_',' ').capitalize()+' : '+str(value)),Spacer(1,4)])
    rows=[[p(x) for x in ('Creance / piece source','Vente / beneficiaire / convention','Montant XAF')]]
    for line in snapshot['lignes']:
        rows.append([p(line['reference']),p(line.get('detail','')),p(line['montant_xaf'])])
    table=LongTable(rows,colWidths=[170,265,75],repeatRows=1)
    table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('BACKGROUND',(0,0),(-1,0),colors.lightgrey),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
    story.extend([table,Spacer(1,12),p('Total : '+str(snapshot['total_xaf'])+' XAF'),Spacer(1,8),p('Ce document ne constate aucun reglement organisme ni aucune ecriture de caisse.')])
    def footer(canvas,doc):
        canvas.saveState();canvas.setFont('Helvetica',7);canvas.drawString(42,24,mark);canvas.drawRightString(A4[0]-42,24,'Page '+str(doc.page));canvas.restoreState()
    SimpleDocTemplate(out,pagesize=A4,leftMargin=42,rightMargin=42,title=label,bottomMargin=42).build(story,onFirstPage=footer,onLaterPages=footer)
    return out.getvalue()
