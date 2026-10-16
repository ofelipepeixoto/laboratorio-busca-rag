# Copyright (c) 2026 Carlos Felipe
# SPDX-License-Identifier: MIT
"""Generate declared synthetic documents, not official legislation."""
import hashlib
from .core import canonical, sha


def fixture():
    documents=[];cases=[]
    for index,topic in enumerate(['mobilidade','saneamento','educacao','energia','cultura']):
        split=['train','validation','test','test','test'][index]
        for house in ['camara','senado']:
            for kind in ['law','bill']:
                if topic=='cultura' and (house!='camara' or kind!='bill'):
                    continue
                family=f'{house}:{kind}:{topic}'
                for version in [1,2]:
                    text=f'Texto sintético sem validade jurídica. {topic}: prazo ilustrativo de {10+version} dias. Casa {house}; espécie {kind}; versão {version}.'
                    item=f'{family}:v{version}'
                    documents.append({'id':item,'family_id':family,'house':house,'kind':kind,'status':'enacted' if kind=='law' else 'proposed','version':version,'split':split,'valid_from':'2020-01-01' if version==1 else '2024-01-01','valid_until':'2024-01-01' if version==1 else None,'source_url':f'https://legislativo.example.invalid/{item}','text':text,'text_sha256':hashlib.sha256(text.encode()).hexdigest(),'synthetic':True})
                    cases.append({'id':f'{item}:q','question':f'Qual prazo {topic}?','split':split,'house':house,'kind':kind,'as_of':'2022-01-01' if version==1 else '2026-01-01','expected':item})
                cases.append({'id':f'{family}:future','question':f'Qual prazo {topic}?','split':split,'house':house,'kind':kind,'as_of':'2018-01-01','expected':None})
    for label,question,house,kind in [('bill-not-law','cultura','camara','law'),('wrong-house','cultura','senado','bill'),('unsupported','zzzzsemfonte','camara','law')]:
        cases.append({'id':label,'question':question,'split':'test','house':house,'kind':kind,'as_of':'2026-01-01','expected':None})
    return documents,cases
