"""Pièces P4.5 historiques, lisibles et paginées ; aucune valorisation inventée."""
from io import BytesIO
from datetime import datetime
from html import escape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib.pagesizes import A4,landscape
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,LongTable,TableStyle,KeepTogether

def document_pdf(data):
    out=BytesIO();styles=getSampleStyleSheet();styles.add(ParagraphStyle(name='FinanceCell',fontName='Helvetica',fontSize=8,leading=11,splitLongWords=True))
    def p(value):return Paragraph(escape(str(value if value is not None else 'NON DISPONIBLE')),styles['FinanceCell'])
    wide=any(len(x['colonnes'])>4 for x in data['sections']);paper=landscape(A4) if wide else A4;width=paper[0]-80
    story=[Paragraph(escape(data['titre']),styles['Title']),p(data['organisation']+' / '+data['site']),p('Référence : '+data['reference']),p('Émis le '+datetime.fromisoformat(data['date']).strftime('%d/%m/%Y à %H:%M UTC')),p('Responsable : '+(data.get('responsable') or 'IDENTITÉ NON DISPONIBLE')),Spacer(1,14)]
    for section in data['sections']:
        rows=[[p(x) for x in section['colonnes']]]+[[p(x) for x in row] for row in section['lignes']]
        if len(rows)==1:rows.append([p('Aucune opération')]+[p('') for _ in section['colonnes'][1:]])
        n=len(section['colonnes']);weights=([2]+[1]*(n-1));unit=width/sum(weights)
        table=LongTable(rows,colWidths=[w*unit for w in weights],repeatRows=1,hAlign='LEFT');table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e3efeb')),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),('LINEBELOW',(0,0),(-1,0),.5,colors.HexColor('#34705c')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f6f8f7')])]))
        story.extend([Paragraph(escape(section['titre']),styles['Heading2']),table,Spacer(1,12)])
    story.append(KeepTogether([p('Responsable : ____________________     Date : ______________'),Spacer(1,24),p('Signature : ____________________')]))
    def footer(canvas,doc):
        canvas.saveState();canvas.setFont('Helvetica',8);canvas.drawString(40,24,data['reference']);canvas.drawRightString(paper[0]-40,24,'Page '+str(doc.page));canvas.restoreState()
    SimpleDocTemplate(out,pagesize=paper,leftMargin=40,rightMargin=40,topMargin=36,bottomMargin=45,title=data['titre']).build(story,onFirstPage=footer,onLaterPages=footer)
    return out.getvalue()
