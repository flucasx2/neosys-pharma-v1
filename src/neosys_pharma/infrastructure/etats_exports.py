"""Adaptateurs d'export autonomes pour l'application (aucun outil d'auteur requis)."""
import csv
import io
from datetime import datetime, date
from decimal import Decimal
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED

MIME={'csv':'text/csv; charset=utf-8','xlsx':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','pdf':'application/pdf'}

def exporter(report, format):
    return {'csv':csv_export,'xlsx':xlsx_export,'pdf':pdf_export}[format](report)

def csv_safe(value):
    if value is None:return ''
    value=str(value)
    return "'"+value if value.lstrip().startswith(('=','+','-','@','\t','\r')) else value

def csv_export(report):
    out=io.StringIO(newline='');w=csv.writer(out,delimiter=';')
    metadata=['organisation_id','site_id','reference','genere_le']
    w.writerow(metadata+[c['key'] for c in report['columns']])
    for row in report['items']:
        w.writerow([report[k] for k in metadata]+[row.get(c['key']) if isinstance(row.get(c['key']),(int,float,Decimal)) else csv_safe(row.get(c['key'])) for c in report['columns']])
    return ('\ufeff'+out.getvalue()).encode('utf-8')

def letter(index):
    result=''
    while index:
        index,rest=divmod(index-1,26);result=chr(65+rest)+result
    return result

def xlsx_export(report):
    # OOXML minimal : strings explicites (jamais interprétées comme formules),
    # nombres typés, dates numériques, formules uniquement écrites par l'exporteur.
    ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    def cell(value, ref, style=0):
        if value is None:return f'<c r="{ref}"/>'
        if isinstance(value,(date,datetime)):
            if isinstance(value,datetime):value=value.replace(tzinfo=None)
            else:value=datetime.combine(value,datetime.min.time())
            n=(value-datetime(1899,12,30)).total_seconds()/86400
            return f'<c r="{ref}" s="2"><v>{n}</v></c>'
        if isinstance(value,(int,float,Decimal)) and not isinstance(value,bool):return f'<c r="{ref}" s="3"><v>{value}</v></c>'
        # XML 1.0 forbids low controls; preserve accented Unicode and line breaks.
        value=''.join(c for c in str(value) if ord(c)>=32 or c in '\n\r\t')
        return f'<c r="{ref}" s="{style}" t="inlineStr"><is><t xml:space="preserve">{escape(value)}</t></is></c>'
    def sheet(rows, data=False):
        content=[]
        for n,row in enumerate(rows,1):content.append(f'<row r="{n}">'+''.join(cell(v,letter(i)+str(n),1 if data and n==1 else 0) for i,v in enumerate(row,1))+'</row>')
        last=len(report['items'])+1;end=letter(len(report['columns']))
        if data and report['items']:
            formulas=[cell('Totaux des quantités',f'A{last+1}',1)]
            totals=report['synthese']['totaux_quantites']
            for i,c in enumerate(report['columns'],1):
                k=c['key'];col=letter(i)
                if k in totals:formulas.append(f'<c r="{col}{last+1}" s="3"><f>SUBTOTAL(109,{col}2:{col}{last})</f><v>{totals[k]}</v></c>')
            content.append(f'<row r="{last+1}">'+''.join(formulas)+'</row>')
        cols=''.join(f'<col min="{i}" max="{i}" width="{40 if c["key"] in ("produit","justification","motif_valorisation") else 24}" customWidth="1"/>' for i,c in enumerate(report['columns'],1)) if data else '<col min="1" max="1" width="36" customWidth="1"/><col min="2" max="2" width="110" customWidth="1"/>'
        return f'<worksheet xmlns="{ns}"><sheetViews><sheetView workbookViewId="0">'+('<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>' if data else '')+f'</sheetView></sheetViews><cols>{cols}</cols><sheetData>'+''.join(content)+f'</sheetData>'+ (f'<autoFilter ref="A1:{end}{max(1,last)}"/>' if data else '')+'<pageMargins left="0.3" right="0.3" top="0.5" bottom="0.5" header="0.2" footer="0.2"/><pageSetup orientation="landscape" paperSize="9" fitToWidth="1" fitToHeight="0"/></worksheet>'
    rows=[[c['label'] for c in report['columns']]]
    for row in report['items']:
        cells=[]
        for c in report['columns']:
            v=row.get(c['key'])
            if v is not None and c['key'] in ('date','peremption'):v=datetime.fromisoformat(v)
            if v is not None and c['key'] in ('cout_unitaire','montant'):v=Decimal(v)
            cells.append(v)
        rows.append(cells)
    summary=[['État',report['titre']],['Organisation',report['organisation']],['Site',report['site']],['Référence',report['reference']],['Généré le (UTC)',datetime.fromisoformat(report['genere_le'])],['Filtres',str(report['filtres'])],['Nombre de lignes',report['total']],['Lignes non valorisables',report['synthese']['lignes_non_valorisables']],['Valorisation définitive',Decimal(report['synthese']['total_valorisation']) if report['synthese']['total_valorisation'] is not None else 'INDISPONIBLE — coûts historiques manquants'],['Devise',report['synthese']['devise']]]
    if report['inventaire']:summary += [[k,str(v) if v is not None else None] for k,v in report['inventaire'].items()]
    summary += [['Méthode / limite',n] for n in report['notes']]
    out=io.BytesIO()
    with ZipFile(out,'w',ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'+''.join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in (1,2))+'</Types>')
        z.writestr('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr('xl/workbook.xml',f'<workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Synthèse" sheetId="1" r:id="rId1"/><sheet name="Données" sheetId="2" r:id="rId2"/></sheets><definedNames><definedName name="_xlnm.Print_Titles" localSheetId="1">Données!$1:$1</definedName></definedNames><calcPr calcId="191029" fullCalcOnLoad="1"/></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+''.join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in (1,2))+'<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
        z.writestr('xl/styles.xml',f'<styleSheet xmlns="{ns}"><numFmts count="1"><numFmt numFmtId="164" formatCode="dd/mm/yyyy hh:mm"/></numFmts><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF176B69"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="4"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"><alignment vertical="top" wrapText="1"/></xf><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0"><alignment wrapText="1"/></xf><xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="3" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>')
        z.writestr('xl/worksheets/sheet1.xml',sheet(summary));z.writestr('xl/worksheets/sheet2.xml',sheet(rows,True))
    return out.getvalue()

def pdf_export(report):
    import reportlab
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, LongTable, TableStyle
    from reportlab.pdfgen.canvas import Canvas
    font=Path(reportlab.__file__).parent/'fonts'/'Vera.ttf'
    if 'NeoSys' not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont('NeoSys',str(font)))
    styles=getSampleStyleSheet();style=ParagraphStyle('cell',fontName='NeoSys',fontSize=7,leading=10,wordWrap='CJK')
    normal=ParagraphStyle('normal',fontName='NeoSys',fontSize=9,leading=13)
    def p(v,sty=style):return Paragraph(escape(str(v)) if v is not None else '—',sty)
    out=io.BytesIO();width,height=landscape(A4)
    class Numbered(Canvas):
        def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);self.states=[]
        def showPage(self):self.states.append(dict(self.__dict__));self._startPage()
        def save(self):
            total=len(self.states)
            for state in self.states:
                self.__dict__.update(state);self.setFont('NeoSys',7)
                self.drawString(26,18,'NeoSys Pharma · '+report['reference'])
                self.drawRightString(width-26,18,f'Page {self._pageNumber} / {total}')
                self.drawString(26,height-20,(report['organisation']+' · '+report['site'])[:145]);super().showPage()
            super().save()
    story=[p(report['titre'],normal),p(report['organisation']+' · '+report['site'],normal),p('Généré le (UTC) : '+report['genere_le'],normal),p('Référence : '+report['reference'],normal),p('Filtres : '+str(report['filtres']),normal)]
    if report['inventaire']:story.append(p('Inventaire : '+str(report['inventaire']),normal))
    if report['genre'] in ('valorisation','ecarts','comptabilite'):story.append(p(f"{report['synthese']['lignes_non_valorisables']} ligne(s) non valorisable(s). Valorisation définitive : "+(report['synthese']['total_valorisation'] or 'INDISPONIBLE'),normal))
    story += [p(n,normal) for n in report['notes']]+[Spacer(1,12)]
    # Identifiants internes conservés intégralement dans CSV/Excel, références de
    # document et ligne dans le PDF ; éviter une grille de 30 colonnes illisible.
    keys={'stocks':['produit','conditionnement','emplacement','lot','peremption','physique','reserve','vendable'], 'valorisation':['produit','conditionnement','emplacement','lot','physique','cout_unitaire','montant','motif_valorisation'], 'peremptions':['produit','conditionnement','emplacement','lot','peremption','physique','etat_peremption'], 'mouvements':['date','type','produit','conditionnement','emplacement','lot','delta_physique','delta_reserve','origine','auteur'], 'comptabilite':['date','type','produit','conditionnement','emplacement','lot','delta_physique','montant','motif_valorisation'], 'inventaire':['zone','produit','conditionnement','lot','peremption','theorique','theorique_au_comptage','compte','ecart'], 'ecarts':['zone','produit','conditionnement','lot','compte','ecart','montant','motif','motif_valorisation']}[report['genre']]
    labels={c['key']:c['label'] for c in report['columns']}
    table=[[p(labels[k]) for k in keys]]+[[p(row.get(k)) for k in keys] for row in report['items']]
    if not report['items']:story.append(p('Aucune ligne pour ces filtres.',normal))
    else:
        widths=[(width-52)/len(keys)]*len(keys)
        t=LongTable(table,colWidths=widths,repeatRows=1,hAlign='LEFT',splitInRow=1)
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#dbecea')),('VALIGN',(0,0),(-1,-1),'TOP'),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f3f7f7')]),('LINEBELOW',(0,0),(-1,0),.5,colors.grey),('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4)]));story.append(t)
    story.append(Spacer(1,12));story.append(p('Totaux des quantités : '+str(report['synthese']['totaux_quantites']),normal))
    if report['inventaire']:story.append(p('Validation : '+('validée le '+str(report['inventaire']['valide_le'])+' par '+str(report['inventaire']['valide_par']) if report['inventaire']['statut']=='VALIDE' else 'BROUILLON — inventaire non validé'),normal))
    SimpleDocTemplate(out,pagesize=(width,height),leftMargin=26,rightMargin=26,topMargin=36,bottomMargin=34,title=report['titre'],author=report['organisation']).build(story,canvasmaker=Numbered)
    return out.getvalue()
