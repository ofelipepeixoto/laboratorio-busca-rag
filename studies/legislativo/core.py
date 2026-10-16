# Copyright (c) 2026 Carlos Felipe
# SPDX-License-Identifier: MIT
"""Original offline study. No network, model, training or execution authority."""
from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from urllib.parse import urlsplit

MAX_BYTES = 1024 * 1024
MAX_DOCUMENTS = 500
MAX_CASES = 200
SOURCE = 'https://github.com/BaruqueRodrigues/llm-legislativo/tree/6951114da14782ae1433a19f2c4bd1d2442f0ccb'
FIELDS = {'id', 'family_id', 'house', 'kind', 'status', 'version', 'split', 'valid_from', 'valid_until', 'source_url', 'text', 'text_sha256', 'synthetic'}
CASE_FIELDS = {'id','question','split','house','kind','as_of','expected'}


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()


def sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Campo JSON duplicado.')
        result[key] = value
    return result


def read_json(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Entrada deve ser arquivo regular sem link simbólico.')
    with path.open('rb') as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('Entrada excede 1 MiB.')
    return json.loads(raw, object_pairs_hook=_pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Número JSON inválido.')))


def _label(value):
    if type(value) is not str or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,120}', value):
        raise ValueError('Identificador inválido.')


def validate_documents(documents):
    if type(documents) is not list or not 1 <= len(documents) <= MAX_DOCUMENTS:
        raise ValueError('Selecione de 1 a 500 documentos.')
    ids, versions, families, texts = set(), set(), {}, {}
    for d in documents:
        if type(d) is not dict or set(d) != FIELDS:
            raise ValueError('Schema de documento inválido.')
        for name in ['id','family_id']:
            _label(d[name])
        if d['id'] in ids or type(d['version']) is not int or d['version'] < 1:
            raise ValueError('ID duplicado ou versão inválida.')
        ids.add(d['id'])
        vkey = (d['family_id'],d['house'],d['version'])
        if vkey in versions:
            raise ValueError('Versão de família duplicada.')
        versions.add(vkey)
        if d['house'] not in {'camara','senado'} or d['kind'] not in {'bill','law','report'} or d['status'] not in {'proposed','enacted','historical'}:
            raise ValueError('Casa, tipo ou estado inválido.')
        if d['kind'] == 'bill' and d['status'] == 'enacted':
            raise ValueError('Projeto não pode ser tratado como lei promulgada.')
        if d['split'] not in {'train','validation','test'} or type(d['synthetic']) is not bool:
            raise ValueError('Split ou origem inválido.')
        if families.setdefault(d['family_id'],d['split']) != d['split']:
            raise ValueError('Família cruza splits.')
        start = date.fromisoformat(d['valid_from'])
        if start.isoformat() != d['valid_from']:
            raise ValueError('Data deve usar YYYY-MM-DD.')
        end = date.fromisoformat(d['valid_until']) if d['valid_until'] else None
        if end is not None and end.isoformat() != d['valid_until']:
            raise ValueError('Data deve usar YYYY-MM-DD.')
        if end is not None and end <= start:
            raise ValueError('Intervalo de versão inválido.')
        # This interval is reviewed fixture metadata, never inferred legal validity.
        if type(d['text']) is not str or not d['text'].strip() or len(d['text'].encode()) > 16384:
            raise ValueError('Texto vazio ou acima de 16 KiB.')
        digest = hashlib.sha256(d['text'].encode()).hexdigest()
        if d['text_sha256'] != digest:
            raise ValueError('Hash do texto divergente.')
        if texts.setdefault(digest,d['split']) != d['split']:
            raise ValueError('Texto idêntico cruza splits.')
        url = urlsplit(d['source_url'])
        if url.scheme != 'https' or not url.hostname or url.username or url.password or url.fragment:
            raise ValueError('URL de origem inválida.')
        if d['synthetic'] and not url.hostname.endswith('.invalid'):
            raise ValueError('Fixture deve usar domínio .invalid.')
        if not d['synthetic'] and url.hostname not in {'www.camara.leg.br','www2.camara.leg.br','dadosabertos.camara.leg.br','www12.senado.leg.br','www25.senado.leg.br','legis.senado.leg.br','www.planalto.gov.br'}:
            raise ValueError('Origem fora do recorte permitido; revisar adaptador.')
    # No two versions of a family may overlap in this experiment.
    for key in families:
        group = sorted((d for d in documents if d['family_id']==key), key=lambda d:d['valid_from'])
        for left,right in zip(group,group[1:]):
            if not left['valid_until'] or left['valid_until'] > right['valid_from']:
                raise ValueError('Versões sobrepostas exigem revisão.')
    return documents


def validate_cases(cases, documents):
    if type(cases) is not list or not 1 <= len(cases) <= MAX_CASES:
        raise ValueError('Casos devem conter de 1 a 200 itens.')
    by_id={d['id']:d for d in documents}; seen=set()
    for c in cases:
        if type(c) is not dict or set(c) != CASE_FIELDS:
            raise ValueError('Schema de caso inválido.')
        _label(c['id'])
        if c['id'] in seen or type(c['question']) is not str or not 1 <= len(c['question']) <= 2000:
            raise ValueError('Caso repetido ou pergunta inválida.')
        seen.add(c['id'])
        if date.fromisoformat(c['as_of']).isoformat() != c['as_of']:
            raise ValueError('Data deve usar YYYY-MM-DD.')
        if c['split'] not in {'train','validation','test'} or c['house'] not in {'camara','senado'} or c['kind'] not in {'bill','law','report'}:
            raise ValueError('Escopo de caso inválido.')
        if c['expected'] is not None:
            if c['expected'] not in by_id or not eligible(by_id[c['expected']], c):
                raise ValueError('Gabarito fora do escopo ou versão.')
    return cases


def eligible(d, c):
    return (d['split']==c['split'] and d['house']==c['house'] and d['kind']==c['kind'] and
            d['valid_from'] <= c['as_of'] and (not d['valid_until'] or c['as_of'] < d['valid_until']) and
            (c['kind']!='law' or d['status']=='enacted'))


def terms(text):
    text=''.join(c for c in unicodedata.normalize('NFKD',text.lower()) if not unicodedata.combining(c))
    return set(re.findall(r'[a-z0-9]+',text))-{'qual','o','a','de','da','do','em','para','que','e','lei','projeto','prazo'}


def retrieve(question, candidates):
    scored=sorted(((len(terms(question)&terms(d['text'])),d['id']) for d in candidates),key=lambda x:(-x[0],x[1]))
    return scored[0][1] if scored and scored[0][0]>0 else None


def evaluate(documents, cases):
    validate_documents(documents); validate_cases(cases, documents)
    by_id={d['id']:d for d in documents};rows=[]
    for c in cases:
        selected=retrieve(c['question'],[d for d in documents if eligible(d,c)])
        citation=None
        if selected:
            d=by_id[selected]
            citation={k:d[k] for k in ['id','family_id','version','house','kind','source_url','text_sha256']}
            citation.update(start=0,end=len(d['text']),review_status='pending')
        rows.append({'id':c['id'],'esperado':c['expected'],'obtido':selected,'citation':citation})
    return {'schema':'radar-legislative-replay/v1','source_study':SOURCE,'mode':'offline_lexical',
            'corpus_sha256':sha(documents),'cases_sha256':sha(cases),'synthetic_only':all(d['synthetic'] for d in documents),
            'authorization_to_execute':False,'rows':rows,'limits':{'max_documents':MAX_DOCUMENTS,'max_cases':MAX_CASES},
            'claims':['Retrieval only; no generated answer or legal correctness evaluated.','Source URLs and intervals are declared; no remote verification.','Pending citations do not authorize publication.']}
