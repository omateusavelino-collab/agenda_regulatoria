#!/usr/bin/env python3
import json, os, sys, uuid, urllib.request, urllib.error
from pathlib import Path
from datetime import datetime, timezone
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
CFG=json.loads((HERE/'agenda_config.json').read_text(encoding='utf-8'))

def call(url, method='GET', payload=None):
    headers={
      'User-Agent':'Mozilla/5.0', 'Accept':'application/json, text/plain, */*',
      'Origin':'https://app.powerbi.com','Referer':'https://app.powerbi.com/',
      'ActivityId':str(uuid.uuid4()),'RequestId':str(uuid.uuid4()),
      'X-PowerBI-ResourceKey':CFG['resource_key']
    }
    data=None
    if payload is not None:
      data=json.dumps(payload,separators=(',',':'),ensure_ascii=False).encode('utf-8')
      headers['Content-Type']='application/json'
    req=urllib.request.Request(url,data=data,headers=headers,method=method)
    with urllib.request.urlopen(req,timeout=90) as r:
      return json.loads(r.read().decode('utf-8'))

def model_info():
    u=f"{CFG['api_base']}/public/reports/{CFG['report_id']}/modelsAndExploration?preferReadOnlySession=true"
    return call(u)

def query_template(name):
    q=json.loads((HERE/name).read_text(encoding='utf-8'))
    # HAR template already contains the correct semantic query; update version if model endpoint gives one.
    return q

def query(q):
    u=f"{CFG['api_base']}/public/reports/querydata?synchronous=true"
    return call(u,'POST',q)

def extract_rows(resp):
    results=resp.get('results') or []
    if not results: return []
    data=results[0].get('result',{}).get('data',{})
    select=data.get('descriptor',{}).get('Select',[])
    names=[x.get('Name','') for x in select]
    ds=data.get('dsr',{}).get('DS',[{}])[0]
    dm0=ds.get('PH',[{}])[0].get('DM0',[])
    if not dm0: return []
    schema=dm0[0].get('S',[])
    dicts=ds.get('ValueDicts',{})
    # Map physical Power BI group/measure names to semantic descriptor columns.
    phys_to_sem=[]
    for col in schema:
        n=col.get('N','')
        if n.startswith('G'):
            gi=int(n[1:]); sem=gi+1  # G0=descricao, G1=instrumento, G2=fase
        elif n.startswith('M'):
            sem=0                    # M0=#
        else: sem=len(phys_to_sem)
        phys_to_sem.append(sem)
    rows=[]; prev=[None]*len(schema)
    for ri,dm in enumerate(dm0):
        raw=dm.get('C',[]); mask=dm.get('R',0); vi=0; vals=[]
        for ci,col in enumerate(schema):
            if ri>0 and (mask & (1<<ci)): v=prev[ci]
            else:
                if vi < len(raw): v=raw[vi]; vi+=1
                else: v=dm.get(col.get('N'))
                dn=col.get('DN')
                if dn and isinstance(v,int) and dn in dicts and 0 <= v < len(dicts[dn]): v=dicts[dn][v]
            vals.append(v)
        prev=vals
        out=[None]*len(names)
        for ci,v in enumerate(vals):
            si=phys_to_sem[ci]
            if si < len(out): out[si]=v
        rows.append(dict(zip(names,out)))
    return rows

def extract_scalar_values(resp, suffix):
    results=resp.get('results') or []
    if not results: return []
    data=results[0].get('result',{}).get('data',{})
    names=[x.get('Name','') for x in data.get('descriptor',{}).get('Select',[])]
    ds=data.get('dsr',{}).get('DS',[{}])[0]
    dm0=ds.get('PH',[{}])[0].get('DM0',[])
    target=next((i for i,n in enumerate(names) if n.endswith(suffix)),0)
    vals=[]
    for dm in dm0:
        key=f'G{target}'
        if key in dm: vals.append(dm[key])
        elif target==0 and 'G0' in dm: vals.append(dm['G0'])
    return vals

def compact(row):
    def get(suffix):
      for k,v in row.items():
        if k.endswith(suffix): return v
    return {
      'numero': get('Sum(Agenda Regulatória 2026-2027.#)'),
      'descricao': get('.Descrição'),
      'instrumento': get('.Instrumento'),
      'fase': get('.Fase')
    }

def main():
  info=model_info(); models=info.get('models') or []
  model=models[0] if models else {}
  resp=query(query_template('query_full.json'))
  raw=extract_rows(resp)
  items=[compact(r) for r in raw]
  items=[x for x in items if x.get('descricao')]
  # Theme query is separate in the report, so publish verified theme list without guessing row-to-theme relationships.
  tema_resp=query(query_template('query_temas.json'))
  temas=[]
  for v in extract_scalar_values(tema_resp,'.Tema'):
    if v is not None and v not in temas: temas.append(v)
  out={
    'schema_version':1,
    'fonte':'Power BI público - Agenda Regulatória MCom',
    'fonte_url':CFG['source_page'], 'powerbi_url':CFG['powerbi_url'],
    'extraido_em_utc':datetime.now(timezone.utc).isoformat(timespec='seconds'),
    'bi_ultima_atualizacao':model.get('LastRefreshTime'),
    'agenda':'2026-2027', 'total':len(items),
    'resumo':{'em_andamento':sum(x.get('fase')=='Em andamento' for x in items),'a_iniciar':sum(x.get('fase')=='A iniciar' for x in items)},
    'temas':temas, 'iniciativas':items
  }
  if len(items)<15: raise RuntimeError(f'Consulta retornou somente {len(items)} iniciativas; arquivo anterior foi preservado para evitar publicação incompleta.')
  tmp=ROOT/'agenda_regulatoria.json.tmp'; final=ROOT/'agenda_regulatoria.json'
  tmp.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8'); tmp.replace(final)
  print(f"OK: {len(items)} iniciativas; BI atualizado em {model.get('LastRefreshTime')}")
if __name__=='__main__': main()
