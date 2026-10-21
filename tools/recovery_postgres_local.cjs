// Ensaio LOCAL, sem URL/conexao de rede e sem executar funcoes/triggers do VENDRA.
// Auth e simulado apenas por UUID para validar FKs; nao restaura login/Supabase.
const fs = require('fs');
const crypto = require('crypto');
const path = require('path');
const assert = require('assert/strict');
const args = process.argv.slice(2);
function arg(name) { const i=args.indexOf(name); if(i<0 || !args[i+1]) throw Error(`Falta ${name}`); return args[i+1]; }
const {PGlite}=require(path.join(path.resolve(arg('--runtime')),'node_modules/@electric-sql/pglite'));
const schema=JSON.parse(fs.readFileSync(arg('--schema'),'utf8'));
const output=path.resolve(arg('--output'));
const quote=s=>'"'+s.replaceAll('"','""')+'"';
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const checks=[];
function check(n,c) { assert.ok(c,n); checks.push(n); console.log('OK '+n); }
const uuid=n=>`00000000-0000-4000-8000-${String(n).padStart(12,'0')}`;

async function digestDB(pg,names) {
 const result={};
 for(const name of names) {
  const rows=(await pg.query(`SELECT to_jsonb(t) AS row FROM public.${quote(name)} t ORDER BY to_jsonb(t)::text`)).rows;
  result[name]={rows:rows.length,sha256:sha(JSON.stringify(rows))};
 }
 return result;
}

(async()=>{
 assert.equal(schema.format,'vendra-schema-v1');
 if(args.includes('--verify-only')) {
  const pg=await PGlite.create({loadDataDir:new Blob([fs.readFileSync(path.join(output,'database.pglite.tar.gz'))])});
  try {
   const expected=JSON.parse(fs.readFileSync(path.join(output,'expected.json'),'utf8'));
   check('Dump decifrado reabre e hashes de26tabelas conferem',JSON.stringify(await digestDB(pg,Object.keys(expected)))===JSON.stringify(expected));
   const files=(await pg.query('SELECT storage_path,size_bytes,checksum_sha256 FROM public.attachments')).rows;
   const mapFile=path.join(output,'storage-map.json');
   const storageMap=fs.existsSync(mapFile)?JSON.parse(fs.readFileSync(mapFile,'utf8')):null;
   for(const file of files) {
    const relative=storageMap?storageMap[file.storage_path]:file.storage_path;
    assert.ok(relative,'Arquivo do banco ausente no mapa de Storage.');
    const target=path.resolve(output,'storage',relative);
    assert.ok(target.startsWith(path.resolve(output,'storage')+path.sep),'Caminho de anexo fora do destino.');
    const data=fs.readFileSync(target);
    check('Anexo restaurado corresponde a tamanho e hash do banco',data.length===file.size_bytes&&sha(data)===file.checksum_sha256);
   }
   const isSynthetic=!fs.existsSync(path.join(output,'business-snapshot.json'));
   const result={total:checks.length,checks,synthetic_only:isSynthetic,network_target:false};
   fs.writeFileSync(path.join(output,'verify-result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
  } finally {await pg.close();}
  return;
 }
 assert.equal(schema.sequences.length,0,'Sequencias exigem procedimento dedicado; nao ignorar.');
 assert.ok(!schema.columns.some(c=>c.generated||c.identity),'Colunas geradas exigem suporte dedicado.');
 const snapshotPath=args.includes('--snapshot')?arg('--snapshot'):null;
 const business=snapshotPath?JSON.parse(fs.readFileSync(snapshotPath,'utf8')):null;
 if(business)assert.equal(business.format,'vendra-business-snapshot-v1');
 assert.ok(!fs.existsSync(path.join(output,'database.pglite.tar.gz')),'Dump anterior deve ser preservado.');
 fs.mkdirSync(output,{recursive:true});
 const names=[...new Set(schema.columns.map(c=>c.table))].sort();
 const pg=await PGlite.create();
 let restored;
 try {
  await pg.exec('CREATE SCHEMA auth; CREATE TABLE auth.users(id uuid PRIMARY KEY);');
  for(const name of names) {
   const columns=schema.columns.filter(c=>c.table===name).map(c=>`${quote(c.name)} ${c.type}${c.default?' DEFAULT '+c.default:''}${c.not_null?' NOT NULL':''}`);
   await pg.exec(`CREATE TABLE public.${quote(name)} (${columns.join(',')});`);
  }
  for(const c of schema.constraints.filter(c=>c.kind!=='f')) await pg.exec(`ALTER TABLE public.${quote(c.table)} ADD CONSTRAINT ${quote(c.name)} ${c.definition};`);
  check('26 tabelas com PK unique e checks reais reconstruidas',names.length===26);
  const fixtures={
   profiles:[{id:uuid(1),full_name:'CODEX-RECUPERACAO',role:'responsavel',access_level:'comercial',status:'active'}],
   customers:[{id:uuid(2),name:'Cliente ficticio de recuperacao'}],
   sales_funnels:[{id:uuid(3),name:'CODEX-RECUPERACAO'}],
   funnel_stages:[{id:uuid(4),funnel_id:uuid(3),name:'Novo Lead',position:1}],
   tickets:[{id:uuid(5),customer_id:uuid(2),title:'CODEX-RECUPERACAO',source:'whatsapp',automation_mode:'human'}],
   opportunities:[{id:uuid(6),customer_id:uuid(2),ticket_id:uuid(5),funnel_id:uuid(3),stage_id:uuid(4),title:'Lead ficticio'}],
   messages:[{id:uuid(7),ticket_id:uuid(5),body:'Restauração "VENDRA" — çã',channel:'whatsapp',direction:'inbound',external_message_id:'CODEX-RECOVERY-WAMID'}],
   attachments:[{id:uuid(8),message_id:uuid(7),file_name:'arquivo-sintetico.pdf',storage_path:'recovery/synthetic.pdf',size_bytes:17,checksum_sha256:sha('arquivo-sintetico')}],
   whatsapp_outbox:[{id:uuid(9),customer_id:uuid(2),ticket_id:uuid(5),message_id:uuid(7),phone:'5500000000000',status:'cancelled'}],
  };
  if(business) {
   assert.ok(!Object.keys(business.tables).some(t=>!names.includes(t)||['app_sessions','user_invitations'].includes(t)),'Tabela fora do escopo autorizado.');
   for(const profile of business.tables.profiles||[])await pg.query('INSERT INTO auth.users(id) VALUES($1)',[profile.id]);
   for(const [name,rows] of Object.entries(business.tables))if(rows.length)await pg.query(`INSERT INTO public.${quote(name)} SELECT * FROM jsonb_populate_recordset(NULL::public.${quote(name)},$1::jsonb)`,[JSON.stringify(rows)]);
  } else {
   await pg.query('INSERT INTO auth.users(id) VALUES($1)',[uuid(1)]);
   for(const [name,rows] of Object.entries(fixtures)) for(const row of rows) {
    const keys=Object.keys(row);
    await pg.query(`INSERT INTO public.${quote(name)} (${keys.map(quote).join(',')}) VALUES (${keys.map((_,i)=>'$'+(i+1)).join(',')})`,Object.values(row));
   }
  }
  for(const c of schema.constraints.filter(c=>c.kind==='f')) await pg.exec(`ALTER TABLE public.${quote(c.table)} ADD CONSTRAINT ${quote(c.name)} ${c.definition};`);
  for(const index of schema.indexes) await pg.exec(index);
  check('Relacionamentos e indices restaurados sem violacoes',true);
  const before=await digestDB(pg,names);
  const dump=await pg.dumpDataDir();fs.writeFileSync(path.join(output,'database.pglite.tar.gz'),Buffer.from(await dump.arrayBuffer()));
  fs.writeFileSync(path.join(output,'expected.json'),JSON.stringify(before,null,2));
  await pg.close();
  restored=await PGlite.create({loadDataDir:new Blob([fs.readFileSync(path.join(output,'database.pglite.tar.gz'))])});
  const after=await digestDB(restored,names);
  check('Banco reaberto de dump e todas as contagens/hashes conferem',JSON.stringify(before)===JSON.stringify(after));
  if(business) {
   check('Sessoes e convites excluidos da restauracao',after.app_sessions.rows===0&&after.user_invitations.rows===0);
   const result={total:checks.length,checks,tables:names.length,business_rows:Object.values(before).reduce((n,t)=>n+t.rows,0),source:'authorized_business_snapshot',auth_restored:false,functions_and_triggers_restored:false,network_target:false};
   fs.writeFileSync(path.join(output,'result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));return;
  }
  const joined=(await restored.query('SELECT m.body,a.file_name,o.stage_id FROM public.messages m JOIN public.attachments a ON a.message_id=m.id JOIN public.opportunities o ON o.ticket_id=m.ticket_id')).rows;
  check('Cliente chat anexo e card continuam vinculados',joined.length===1&&joined[0].stage_id===uuid(4));
  check('Texto UTF8 e aspas preservados',joined[0].body==='Restauração "VENDRA" — çã');
  let duplicate=false;try {await restored.query("INSERT INTO public.messages(ticket_id,external_message_id) VALUES($1,'CODEX-RECOVERY-WAMID')",[uuid(5)]);}catch(e){duplicate=e.code==='23505';}
  check('Protecao contra WAMID duplicado continua aplicada',duplicate);
  let foreign=false;try {await restored.query("INSERT INTO public.tickets(customer_id,title) VALUES($1,'invalido')",[uuid(999)]);}catch(e){foreign=e.code==='23503';}
  check('FK continua impedindo ticket de cliente inexistente',foreign);
  const result={total:checks.length,checks,tables:names.length,synthetic_rows:Object.values(before).reduce((n,t)=>n+t.rows,0),source:'schema_only_and_synthetic_data',production_rows_exported:0,auth_restored:false,functions_and_triggers_restored:false,network_target:false};
  fs.writeFileSync(path.join(output,'result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 } finally { if(!pg.closed)await pg.close();if(restored&&!restored.closed)await restored.close(); }
})().catch(e=>{console.error(e.message);process.exitCode=1;});
