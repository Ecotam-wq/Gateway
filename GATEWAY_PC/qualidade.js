'use strict';
const node = id => document.getElementById(id);
let report = null;
const fmtNum = n => typeof n === 'number' ? n.toLocaleString('pt-BR') : '—';
const fmtDate = text => {const date = new Date(text); return Number.isNaN(+date) ? '—' : date.toLocaleString('pt-BR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit'});};
function banner(msg, error=false, ok=false, busy=false){const x=node('quality-status');x.textContent=msg;x.classList.toggle('error',error);x.classList.toggle('ok',ok);x.classList.toggle('is-busy',busy);}
function linkState(online,text){node('dot').classList.toggle('on',online);document.body.classList.toggle('is-offline',!online);node('mode-label').textContent=text;}
// Categoria do evento: sequência (laranja), tempo (azul), campo/faixa (terracota).
const EVENT_TONE={campo_ausente:'terra',faixa_basica:'terra',sequencia_ausente:'orange',sequencia_duplicada:'orange',sequencia_retrocesso:'orange',salto_sequencia:'orange',lacuna_temporal:'blue'};
function tagCell(text,tone,parent){const td=document.createElement('td'),tag=document.createElement('span');tag.className='tag'+(tone?' tag--'+tone:'');tag.textContent=text;td.appendChild(tag);parent.appendChild(td);return td;}
function scoreRing(pct){const arc=node('q-score-arc'),v=typeof pct==='number'?Math.max(0,Math.min(100,pct)):0;arc.setAttribute('stroke-dasharray',`${v} ${100-v}`);arc.classList.toggle('is-warn',typeof pct==='number'&&pct<90);arc.classList.toggle('is-err',typeof pct==='number'&&pct<70);}
function setText(id, text){node(id).textContent=text;}
function makeCell(text, parent){const x=document.createElement('td');x.textContent=String(text??'—');parent.appendChild(x);return x;}
function blank(tbody, cols, message){const tr=document.createElement('tr'),td=document.createElement('td');td.colSpan=cols;td.className='empty-row';td.textContent=message;tr.appendChild(td);tbody.replaceChildren(tr);}
function safeCsv(value){let s=String(value??'');if(/^[=+@\-\t\r]/.test(s)&&!/^\-?\d+(\.\d+)?$/.test(s))s="'"+s;return '"'+s.replaceAll('"','""')+'"';}
function eventLabel(type){return ({campo_ausente:'Campo ausente',faixa_basica:'Faixa básica',sequencia_ausente:'Sem sequência',sequencia_duplicada:'Sequência duplicada',sequencia_retrocesso:'Regressão',salto_sequencia:'Salto de sequência',lacuna_temporal:'Lacuna temporal'})[type]||type;}
function display(){if(!report)return;
 setText('q-samples',fmtNum(report.samples));setText('q-score',report.score_pct===null?'N/D':`${report.score_pct.toLocaleString('pt-BR')}%`);scoreRing(report.score_pct);
 setText('q-gaps',fmtNum(report.gaps));setText('q-bad',fmtNum(report.bad_samples));
 setText('q-lost',fmtNum(report.estimated_missing));setText('q-dups',fmtNum(report.duplicates));
 setText('q-last',report.last_age_s===null?'—':`${Math.round(report.last_age_s)}s atrás`);
 setText('quality-explain',`${report.last_status} · ${report.sessions.length} sessão(ões) · ${report.events_total} alerta(s) detectado(s). Índice baseado em amostras presentes, campos problemáticos e ausências inferidas; não é medição do rádio.`);
 setText('q-events-caption',`${report.events.length} / ${report.events_total} eventos`);
 const tbody=node('q-sessions');tbody.replaceChildren();
 for(const session of report.sessions){const tr=document.createElement('tr');
  makeCell(`${session.device} · ${session.approximate?'inferida':'identificada'} · ${session.id.slice(-22)}`,tr);makeCell(fmtDate(session.start),tr);
  makeCell(fmtNum(session.samples),tr);makeCell(fmtNum(session.problem_samples),tr);makeCell(fmtNum(session.gaps),tr);makeCell(fmtNum(session.missing_est),tr);tbody.appendChild(tr);}
 if(!report.sessions.length)blank(tbody,6,'Nenhuma sessão encontrada no período.');
 const events=node('q-events');events.replaceChildren();
 for(const item of report.events){const tr=document.createElement('tr');makeCell(fmtDate(item.time),tr);tagCell(eventLabel(item.kind),EVENT_TONE[item.kind],tr);makeCell(item.field||'—',tr);makeCell(item.detail,tr);events.appendChild(tr);}
 if(!report.events.length)blank(events,4,report.samples?'Nenhum alerta encontrado nas amostras consultadas.':'Sem dados no intervalo selecionado.');
}
async function analyze(){node('quality-run').disabled=true;setText('quality-run','Analisando...');banner('Consultando registros brutos no InfluxDB...',false,false,true);
 try{const payload={period:node('quality-period').value};if(payload.period==='custom'){
  if(!node('quality-start').value||!node('quality-stop').value)throw new Error('Preencha início e fim do intervalo.');
  payload.start=new Date(node('quality-start').value).toISOString();payload.stop=new Date(node('quality-stop').value).toISOString();}
  const response=await fetch('/api/quality',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  const body=await response.json();if(!response.ok)throw new Error(body.error||`HTTP ${response.status}`);
  report=body;display();banner(`Auditoria concluída: ${body.samples} amostras, ${body.events_total} alertas.`,false,true);
 }catch(err){banner(err.message,true);}
 finally{node('quality-run').disabled=false;setText('quality-run','Analisar qualidade');}
}
async function refreshRuntime(){try{const response=await fetch('/api/status',{cache:'no-store'});if(!response.ok)throw new Error('Gateway indisponível');const s=await response.json();linkState(true,s.influx_configured?'INFLUXDB • '+s.influx_bucket:'GATEWAY ONLINE');
 setText('q-write-ok',fmtNum(s.influx_writes));setText('q-write-fail',fmtNum(s.influx_failed));setText('q-queue',fmtNum(s.queue_drops));
 setText('q-runtime-status',s.influx_configured?'Influx configurado':'Influx desconectado');node('q-runtime-status').className='tag '+(s.influx_error?'tag--terra':s.influx_configured?'tag--blue':'tag--orange');
 const issues=[s.csv_error,s.rx_error,s.influx_error].filter(Boolean);setText('q-runtime-detail',issues.join(' · ')||`Fonte: ${s.source==='sim'?'simulador':'RX USB'} · ${s.influx_status}`);
 return s;
 }catch(err){linkState(false,'Gateway desconectado');setText('q-runtime-status','Gateway indisponível');setText('q-runtime-detail',err.message);return null;}}
function exportReport(){if(!report){banner('Faça uma análise antes de exportar.',true);return;}
 const columns=['time','session_key','kind','severity','field','detail'];
 const lines=[columns.join(','),...report.events.map(item=>columns.map(k=>safeCsv(item[k])).join(','))];
 const blob=new Blob(['\ufeff',lines.join('\r\n')+'\r\n'],{type:'text/csv;charset=utf-8'});
 const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='ECOTAM_Sprint13_alertas.csv';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),15000);
 banner(`Relatório exportado (${report.events.length} alertas da prévia). Os totais continuam disponíveis na tela.`,false,true);
}
async function init(){const now=new Date(),hour=new Date(now.valueOf()-3600000);const local=d=>new Date(d.valueOf()-d.getTimezoneOffset()*60000).toISOString().slice(0,16);
 node('quality-start').value=local(hour);node('quality-stop').value=local(now);
 const status=await refreshRuntime();if(status?.influx_configured){await analyze();}else banner('Conecte o InfluxDB em Tempo real e volte para esta página.',true);
 setInterval(refreshRuntime,5000);
}
node('quality-period').addEventListener('change',()=>node('quality-custom').classList.toggle('hidden',node('quality-period').value!=='custom'));
node('quality-run').addEventListener('click',analyze);
node('quality-export').addEventListener('click',exportReport);
init();
