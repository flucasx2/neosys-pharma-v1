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
        cells=[]
        for c in report['columns']:
            value=row.get(c['key'])
            if value is not None and c['key'] in ('cout_unitaire','montant'):value=Decimal(value)
            cells.append(value if isinstance(value,(int,float,Decimal)) else csv_safe(value))
        w.writerow([report[k] for k in metadata]+cells)
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
        if isinstance(value,(int,float,Decimal)) and not isinstance(value,bool):return f'<c r="{ref}" s="{4 if isinstance(value,Decimal) else 3}"><v>{value}</v></c>'
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
        z.writestr('xl/styles.xml',f'<styleSheet xmlns="{ns}"><numFmts count="1"><numFmt numFmtId="164" formatCode="dd/mm/yyyy hh:mm"/></numFmts><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF176B69"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="5"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"><alignment vertical="top" wrapText="1"/></xf><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0"><alignment wrapText="1"/></xf><xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="3" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="4" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>')
        z.writestr('xl/worksheets/sheet1.xml',sheet(summary));z.writestr('xl/worksheets/sheet2.xml',sheet(rows,True))
    return out.getvalue()

def pdf_export(report):
    """Présentation PDF uniquement ; aucun changement des calculs ni des autres formats."""
    import reportlab
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, LongTable, TableStyle, KeepTogether
    from reportlab.pdfgen.canvas import Canvas
    for name, filename in (('NeoSys','Vera.ttf'),('NeoSysBold','VeraBd.ttf')):
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name,str(Path(reportlab.__file__).parent/'fonts'/filename)))
    normal=ParagraphStyle('normal',fontName='NeoSys',fontSize=8,leading=11,spaceAfter=4)
    cell=ParagraphStyle('cell',parent=normal,fontSize=7,leading=9,spaceAfter=0)
    heading=ParagraphStyle('heading',parent=normal,fontName='NeoSysBold',fontSize=10,leading=13,spaceBefore=10,spaceAfter=7)
    title=ParagraphStyle('title',parent=heading,fontSize=13,leading=16)
    def p(value,style=normal):return Paragraph(escape(str(value)) if value is not None else '-',style)
    def human_date(value):
        if not value:return '-'
        try:
            if len(str(value))==10:return date.fromisoformat(str(value)).strftime('%d/%m/%Y')
            return datetime.fromisoformat(str(value)).strftime('%d/%m/%Y à %H:%M')+' UTC'
        except ValueError:return str(value)
    labels={c['key']:c['label'] for c in report['columns']}
    def pretty(key,value):
        if key in ('date','peremption','debut','fin','reference','valide_le','genere_le'):return human_date(value)
        return value
    out=io.BytesIO();width,height=landscape(A4);available=width-56
    class Numbered(Canvas):
        def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);self.states=[]
        def showPage(self):self.states.append(dict(self.__dict__));self._startPage()
        def save(self):
            total=len(self.states)
            for state in self.states:
                self.__dict__.update(state)
                header=Paragraph(escape(report['organisation']+' / '+report['site'])+'<br/>'+escape(report['titre']+' / '+human_date(report['genere_le'])),cell)
                _,h=header.wrap(available,50);header.drawOn(self,28,height-20-h)
                self.setFont('NeoSys',7)
                self.drawString(28,21,'NeoSys Pharma / '+report['reference'])
                self.drawRightString(width-28,21,f'Page {self._pageNumber} / {total}')
                super().showPage()
            super().save()
    story=[p(report['titre'],title),p('Date de génération : '+human_date(report['genere_le'])),p('Référence du document : '+report['reference'])]
    filter_labels={'emplacement_id':'Emplacement (référence)','produit_id':'Produit (référence)','conditionnement_id':'Conditionnement (référence)','lot_id':'Lot (référence)','q':'Recherche','debut':'Du','fin':'Au','reference':'Date de référence','horizon':'Horizon (jours)'}
    story.append(p('Filtres : '+('; '.join(filter_labels.get(k,k)+' : '+str(pretty(k,v)) for k,v in report['filtres'].items()) or 'Aucun filtre supplémentaire')))
    inv=report.get('inventaire')
    if inv:
        story += [p('Inventaire : '+inv['nom'],heading),p('Référence inventaire : '+inv['id']),p('Type : '+inv['type']+' / Statut : '+inv['statut']),p('Date : '+human_date(inv['date'])+' / Séquence de photographie : '+str(inv['snapshot_sequence']))]
        if inv['statut']=='VALIDE':
            story.append(p('Validation : '+human_date(inv['valide_le'])+' / Responsable : '+(report.get('responsable_validation') or 'Nom indisponible')))
            story.append(p('Référence du validateur : '+(inv.get('valide_par') or 'Non disponible')))
        else:story.append(p('BROUILLON - inventaire non validé',heading))
    if report['genre'] in ('valorisation','ecarts','comptabilite'):
        value=report['synthese']['total_valorisation']
        story.append(p(f"{report['synthese']['lignes_non_valorisables']} ligne(s) non valorisable(s). Valorisation définitive : "+(str(value)+' '+str(report['synthese'].get('devise') or '') if value is not None else 'INDISPONIBLE')))
    story += [p(n) for n in report['notes']]+[Spacer(1,10)]
    keys={'stocks':['produit','conditionnement','emplacement','lot','peremption','physique','reserve','vendable'], 'valorisation':['produit','conditionnement','emplacement','lot','physique','cout_unitaire','montant','motif_valorisation'], 'peremptions':['produit','conditionnement','emplacement','lot','peremption','physique','etat_peremption'], 'mouvements':['date','type','produit','conditionnement','emplacement','lot','delta_physique','delta_reserve','origine','auteur'], 'comptabilite':['date','type','produit','conditionnement','emplacement','lot','delta_physique','montant','motif_valorisation'], 'inventaire':['zone','emplacement','produit','conditionnement','lot','peremption','theorique','theorique_au_comptage','compte','ecart'], 'ecarts':['zone','emplacement','produit','conditionnement','lot','compte','ecart','montant','motif','motif_valorisation']}[report['genre']]
    weights={'produit':3.4,'conditionnement':2.0,'emplacement':1.8,'zone':1.5,'lot':1.7,'date':1.8,'peremption':1.4,'type':1.8,'origine':1.7,'auteur':1.7,'motif':2,'motif_valorisation':2.4,'theorique':1.5,'theorique_au_comptage':1.5}
    def table(rows,widths):
        t=LongTable(rows,colWidths=widths,repeatRows=1,hAlign='LEFT',splitInRow=1)
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#dbecea')),('VALIGN',(0,0),(-1,-1),'TOP'),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f3f7f7')]),('LINEBELOW',(0,0),(-1,0),.5,colors.grey),('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
        return t
    if report['items']:
        total_weight=sum(weights.get(k,1) for k in keys)
        widths=[available*weights.get(k,1)/total_weight for k in keys]
        story.append(table([[p(labels[k],cell) for k in keys]]+[[p(pretty(k,row.get(k)),cell) for k in keys] for row in report['items']],widths))
    else:story.append(p('Aucune ligne pour ces filtres.'))
    if inv:
        # Homogénéité par UUID de conditionnement, jamais par simple libellé.
        groups={}
        for row in report['items']:
            group=groups.setdefault(row['conditionnement_id'],dict(produit=row['produit'],conditionnement=row['conditionnement'],theorique=0,theorique_au_comptage=0,compte=0,ecart=0,manquants=0,connus=0))
            for key in ('theorique','theorique_au_comptage','compte','ecart'):
                if row.get(key) is not None:group[key]+=row[key]
            group['manquants']+=row.get('compte') is None
            group['connus']+=row.get('compte') is not None
        story.append(p('Récapitulatif par conditionnement (unités homogènes)',heading))
        story.append(p('Aucun total global entre conditionnements différents. Les lignes non comptées sont signalées ; leurs quantités ne sont pas assimilées à zéro.'))
        headers=['Produit / conditionnement','Photographie','Théorique au comptage','Compté','Écart','Non comptées']
        rows=[[p(v,cell) for v in headers]]
        for g in groups.values():
            rows.append([p(g['produit']+' / '+g['conditionnement'],cell)]+[p('-' if k!='theorique' and not g['connus'] else str(g[k])+(' (partiel)' if g['manquants'] and k!='theorique' else ''),cell) for k in ('theorique','theorique_au_comptage','compte','ecart')]+[p(g['manquants'],cell)])
        if groups:story.append(table(rows,[available*.44]+[available*.112]*5))
        story.append(KeepTogether([p('Signatures des responsables',heading),p('Nom, qualité, date et signature - à compléter par les responsables habilités.'),table([[p('Responsable du comptage',cell),p('Responsable de validation',cell)],[p('Nom : __________________________',cell),p('Nom : '+(report.get('responsable_validation') or '__________________________'),cell)],[p('Date / signature :',cell),p('Date / signature :',cell)],[Spacer(1,38),Spacer(1,38)]],[available/2]*2)]))
    else:
        story.append(p('Rapprochement des quantités (conditionnements différents : ne pas interpréter comme un total homogène)',heading))
        story += [p(labels.get(k,k)+' : '+str(v)) for k,v in report['synthese']['totaux_quantites'].items()]
    SimpleDocTemplate(out,pagesize=(width,height),leftMargin=28,rightMargin=28,topMargin=65,bottomMargin=40,title=report['titre'],author=report['organisation']).build(story,canvasmaker=Numbered)
    return out.getvalue()
