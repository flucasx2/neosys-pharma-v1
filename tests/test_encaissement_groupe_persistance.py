"""Persistance ciblée sur SQLite mémoire ; aucune base conservée."""
from dataclasses import replace
from decimal import Decimal
from uuid import UUID,uuid4
import os
from pathlib import Path
import pytest
from sqlalchemy import select, text, literal, Text, JSON
from sqlalchemy.exc import DBAPIError
from sqlalchemy.dialects.postgresql import insert as pg_insert
from test_caisse import raw_client,account,ready,db,final
from test_vente import create,line,act
from neosys_pharma.domain.encaissement_groupe import DossierEncaissementGroupe,SelectionGroupe
from neosys_pharma.infrastructure.encaissement_groupe_repository import SqlAlchemyEncaissementGroupeRepository
from neosys_pharma.infrastructure.encaissement_groupe_models import DossierEncaissementGroupeModel,VentilationEncaissementModel
from neosys_pharma.infrastructure.caisse_models import EncaissementModel,SessionCaisseModel
from neosys_pharma.infrastructure.database import Base


def verifier_base_tests(url, confirmation=None):
    if not url:
        return
    from sqlalchemy.engine import make_url
    parsed=make_url(url)
    if parsed.get_backend_name()=='sqlite' and parsed.database in (None,':memory:'):
        return
    database=parsed.database or ''
    if parsed.get_backend_name()=='postgresql':
        allowed=parsed.host in ('localhost','127.0.0.1','::1') and database.startswith('neosys_eg32_jetable_')
    elif parsed.get_backend_name()=='sqlite':
        allowed=Path(database).is_absolute() and Path(database).name.startswith('neosys_eg32_jetable_')
    else:
        allowed=False
    if not allowed or confirmation!=database:
        raise ValueError('Tests refusés : base jetable eg32 explicitement confirmée requise.')


@pytest.fixture(scope='session',autouse=True)
def eg32_garde_base():
    # Exécutée avant les fixtures de données de ce module.
    verifier_base_tests(os.getenv('TEST_DATABASE_URL'),os.getenv('EG32_AUTORISER_BASE_JETABLE'))


@pytest.mark.parametrize('url,confirmation,ok',[
    (None,None,True),('sqlite:///:memory:',None,True),
    ('postgresql://localhost/neosys_pharma_v1','neosys_pharma_v1',False),
    ('postgresql://localhost/neosys_p46_recette_20261012','neosys_p46_recette_20261012',False),
    ('postgresql://localhost/neosys_eg32_jetable_validation',None,False),
    ('postgresql://localhost/neosys_eg32_jetable_validation','neosys_eg32_jetable_validation',True),
])
def test_garde_bases_jetables(url,confirmation,ok):
    if ok:verifier_base_tests(url,confirmation)
    else:
        with pytest.raises(ValueError):verifier_base_tests(url,confirmation)


def sample(c,a):
    v,se,p,pack,poste,caisse=ready(c,a,q=1)
    w=line(c,a,create(c,a,poste),p,pack,1);w=act(c,a,w,'valider');w=act(c,a,w,'transmettre',caisse_id=caisse)
    gen=db(c);s=next(gen);session=s.get(SessionCaisseModel,UUID(se['id']))
    d=DossierEncaissementGroupe(organisation_id=a['org'],site_id=a['site'],emplacement_id=a['location'],
        caisse_id=UUID(caisse),session_id=session.id,auteur_id=session.caissier_id,
        selections=(SelectionGroupe(vente_id=UUID(v['id']),revision_vente=v['revision'],ordre=1),SelectionGroupe(vente_id=UUID(w['id']),revision_vente=w['revision'],ordre=2)),empreinte_selection='a'*64)
    return v,w,se,d,s,gen


def enc(s,se,vente=None,dossier=None,period=None):
    from neosys_pharma.infrastructure.caisse_models import PeriodeCaisseSiteModel
    if period is None:
        period=s.scalar(select(PeriodeCaisseSiteModel.id))
    number=10 if vente else 20
    row=EncaissementModel(id=uuid4(),organisation_id=se.organisation_id,vente_id=vente,
        type_encaissement='INDIVIDUEL' if vente else 'GROUPE',dossier_groupe_id=dossier,
        session_id=se.id,periode_id=period,numero=number,total_xaf=0,instantane={'fictif':True},pdf=b'PDF FICTIF',pdf_sha256='b'*64)
    s.add(row);s.flush();return row


def vent(s,e,vente):
    row=VentilationEncaissementModel(organisation_id=e.organisation_id,encaissement_id=e.id,vente_id=vente,
        revision_vente=1,montant_ht=0,montant_tva=0,net_ttc=0,instantane={'fictif':True})
    s.add(row);s.flush();return row


def test_repository_portee_et_pas_de_commit(raw_client,account):
    v,w,se,d,s,gen=sample(raw_client,account)
    try:
        repo=SqlAlchemyEncaissementGroupeRepository(s,d.organisation_id);repo.ajouter_dossier(d);s.flush()
        assert repo.dossier(d.id)==d
        updated=d.changer_selection(d.selections,'b'*64);repo.modifier_selection(updated,d.revision);s.flush();assert repo.dossier(d.id)==updated
        with pytest.raises(ValueError):repo.modifier_selection(updated,d.revision)
        assert SqlAlchemyEncaissementGroupeRepository(s,uuid4()).dossier(d.id) is None
        with pytest.raises(ValueError):repo.ajouter_dossier(replace(d,id=uuid4(),organisation_id=uuid4()))
        s.rollback();assert repo.dossier(d.id) is None
    finally:gen.close()


@pytest.mark.parametrize('historique_premier',[True,False])
def test_registre_refuse_double_encaissement_dans_les_deux_sens(raw_client,account,historique_premier):
    v,w,se,d,s,gen=sample(raw_client,account)
    try:
        repo=SqlAlchemyEncaissementGroupeRepository(s,d.organisation_id);repo.ajouter_dossier(d);s.flush()
        sess=s.get(SessionCaisseModel,UUID(se['id']))
        if historique_premier:
            old=enc(s,sess,vente=UUID(v['id']));new=enc(s,sess,dossier=d.id);s.commit()
            with pytest.raises(DBAPIError,match='Vente deja encaissee'):vent(s,new,UUID(v['id']))
            s.rollback();assert repo.encaissement_de_vente(UUID(v['id']))==old.id
        else:
            new=enc(s,sess,dossier=d.id);vent(s,new,UUID(v['id']));s.commit()
            with pytest.raises(DBAPIError,match='Vente deja encaissee'):enc(s,sess,vente=UUID(v['id']))
            s.rollback();assert repo.encaissement_de_vente(UUID(v['id']))==new.id
    finally:gen.close()


def test_meme_encaissement_et_immutabilite(raw_client,account):
    v,w,se,d,s,gen=sample(raw_client,account)
    try:
        e=enc(s,s.get(SessionCaisseModel,UUID(se['id'])),vente=UUID(v['id']));x=vent(s,e,UUID(v['id']));s.commit()
        assert s.scalar(text('SELECT count(*) FROM caisse_ventes_encaissees'))==1
        for table in ('caisse_ventes_encaissees','caisse_ventilations'):
            with pytest.raises(DBAPIError):s.execute(text(f'DELETE FROM {table}'));s.commit()
            s.rollback()
    finally:gen.close()


def test_selection_figee_et_export_fictif_optionnel(raw_client,account):
    v,w,se,d,s,gen=sample(raw_client,account)
    try:
        destination=os.getenv('EG32_EXPORT_SQL')
        if destination:
            # Données de test générées par fixtures ; aucun accès à une base extérieure.
            sql=[]
            for table in Base.metadata.sorted_tables:
                for row in s.execute(select(table)).mappings():
                    if table.name=='permissions' and row['code']=='caisse.encaisser.groupe':continue
                    row={k:(str(UUID(value)) if k=='role_scope' and value!='systeme' else value) for k,value in row.items()}
                    values={k:literal(__import__('json').dumps(value),type_=Text).cast(JSON) if isinstance(table.c[k].type,JSON) else value for k,value in row.items() if table.c[k].computed is None}
                    stmt=pg_insert(table).values(**values).on_conflict_do_nothing()
                    from sqlalchemy.dialects.postgresql import dialect
                    sql.append(str(stmt.compile(dialect=dialect(paramstyle='named'),compile_kwargs={'literal_binds':True}))+';')
            Path(destination).write_text('\n'.join(sql))
            Path(destination+'.json').write_text(__import__('json').dumps({'org':str(d.organisation_id),'site':str(d.site_id),'loc':str(d.emplacement_id),'caisse':str(d.caisse_id),'session':str(d.session_id),'user':str(d.auteur_id),'ventes':[v['id'],w['id']],'lignes':[v['lignes'][0]['id'],w['lignes'][0]['id']]}))
        repo=SqlAlchemyEncaissementGroupeRepository(s,d.organisation_id);repo.ajouter_dossier(d);s.flush()
        row=s.get(DossierEncaissementGroupeModel,d.id);row.etat='EN_REGLEMENT';s.commit()
        with pytest.raises(DBAPIError,match='Selection figee'):s.execute(text('DELETE FROM caisse_selections_groupes'));s.commit()
        s.rollback()
    finally:gen.close()
