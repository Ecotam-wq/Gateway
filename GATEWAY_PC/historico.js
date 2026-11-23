'use strict';
/* CANIDÉ · Histórico: usa EcoUI.LineChart (definido em /dashboard.js, carregado antes). */
const $ = id => document.getElementById(id);
const META = {
 altitude_m:['Altitude BME280','m',2], pressure_pa:['Pressão','Pa',0], temperature_c:['Temperatura','°C',2],
 humidity_pct:['Umidade relativa','% UR',2], gps_altitude_m:['Altitude GPS','m',2], latitude:['Latitude','graus',7], longitude:['Longitude','graus',7], satellites:['Satélites','nº',0],
 battery_v:['Bateria','V',2], accel_x:['Aceleração X','m/s²',3], accel_y:['Aceleração Y','m/s²',3],
 accel_z:['Aceleração Z','m/s²',3], gyro_x:['Giroscópio X','unid. simulada',3],
 gyro_y:['Giroscópio Y','unid. simulada',3], gyro_z:['Giroscópio Z','unid. simulada',3]
};
const fnum = (v,d=2) => v===null || v===undefined || !Number.isFinite(Number(v)) ? '—' : Number(v).toLocaleString('pt-BR',{minimumFractionDigits:d,maximumFractionDigits:d});
const fmtDate = iso => new Date(iso).toLocaleString('pt-BR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit'});
const fmtElapsed = s => {s=Math.max(0,Math.round(s));const h=Math.floor(s/3600),m=Math.floor(s%3600/60),r=s%60;return h?`${h}h${String(m).padStart(2,'0')}`:m?`${m}:${String(r).padStart(2,'0')}`:`${r} s`;};
let history = null;
const chart = new EcoUI.LineChart($('historic-chart'), {
 series:[{name:'Sessão A',tone:'blue'},{name:'Sessão B',tone:'orange'}],
 tooltip:$('chart-tooltip'), pad:{l:84,r:20,t:28,b:32},
 empty:'Sem pontos para a variável e sessão selecionadas.',
 head:q=>`T+ ${fmtElapsed(q.x)} desde o início da sessão`,
 detail:q=>q.time?fmtDate(q.time):''
});
function banner(message,error=false,ok=false,busy=false){const node=$('history-status');node.textContent=message;node.classList.toggle('error',error);node.classList.toggle('ok',ok);node.classList.toggle('is-busy',busy);}
function linkState(online,text){$('dot').classList.toggle('on',online);document.body.classList.toggle('is-offline',!online);$('mode-label').textContent=text;}
async function post(endpoint,payload){const response=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const data=await response.json();if(!response.ok)throw new Error(data.error||`HTTP ${response.status}`);return data;}
function metricInfo(){return META[$('metric').value]||['Medição','',2];}
function emptyGraph(message){chart.update({series:[],empty:message});}
function escapeCsv(value){let out=String(value??'');if(/^[=+@\-\t\r]/.test(out) && !/^\-?\d+(?:\.\d+)?$/.test(out))out="'"+out;return '"'+out.replaceAll('"','""')+'"';}
function getSelection(id){return $('session-'+id).value;}
function getSessionRows(sessionKey,metric){if(!history||!sessionKey)return [];const points=history.rows.filter(p=>p.session_key===sessionKey&&Number.isFinite(p[metric]));if(!points.length)return [];const start=Date.parse(points[0].time);return points.map(p=>({time:p.time,elapsed:(Date.parse(p.time)-start)/1000,value:p[metric],source:p.source,device:p.device}));}
function renderChart(){
 const metric=$('metric').value,[name,unit,decimals]=metricInfo();
 const sets=[getSelection('a'),getSelection('b')].map(id=>getSessionRows(id,metric));
 if(!sets.some(s=>s.length)){emptyGraph('Sem pontos para a variável e sessão selecionadas.');$('axis-label').textContent=`Tempo decorrido · ${name} (${unit})`;return;}
 const maxX=Math.max(1,...sets.flat().map(p=>p.elapsed));
 const step=EcoUI.niceStep(maxX,5),xTicks=[];for(let v=0;v<=maxX+1e-9&&xTicks.length<8;v+=step)xTicks.push({x:v,label:fmtElapsed(v)});
 const vals=sets.flat().map(p=>p.value);let lo=Math.min(...vals),hi=Math.max(...vals);const spread=Math.max(.001,hi-lo);lo-=spread*.13;hi+=spread*.13;
 chart.update({series:sets.map(s=>s.map(p=>({x:p.elapsed,y:p.value,t:Date.parse(p.time),time:p.time}))),x0:0,x1:maxX,xTicks,yDomain:[lo,hi],unit,decimals});
 $('axis-label').textContent=`Tempo decorrido · ${name} (${unit})`;
 $('historic-chart').setAttribute('aria-label',`${name} por tempo decorrido: ${sets.map((s,i)=>s.length?`sessão ${i?'B':'A'} com ${s.length} pontos`:'').filter(Boolean).join(', ')}. Use as setas para inspecionar.`);
}
function renderStats(letter){
 const metric=$('metric').value,points=getSessionRows(getSelection(letter),metric),container=$('stats-'+letter),subtitle=$('summary-'+letter);
 container.replaceChildren();if(!points.length){subtitle.textContent='Sem dados para esta seleção.';return;}
 const values=points.map(p=>p.value),minimum=Math.min(...values),maximum=Math.max(...values),average=values.reduce((a,b)=>a+b,0)/values.length;
 subtitle.textContent=`${fmtDate(points[0].time)} · ${points.length} pontos amostrados`;
 [['Mínimo',minimum],['Máximo',maximum],['Média',average],['Pontos',values.length]].forEach(([key,value])=>{
  const cell=document.createElement('div'),label=document.createElement('small'),number=document.createElement('strong');label.textContent=key;number.textContent=fnum(value,key==='Pontos'?0:2);cell.append(label,number);container.appendChild(cell);
 });
}
function renderTable(){const tbody=$('history-tbody');tbody.replaceChildren();$('table-metric').textContent=metricInfo()[0];
 if(!history){const tr=document.createElement('tr'),td=document.createElement('td');td.colSpan=4;td.className='empty-row';td.textContent='Aguardando consulta.';tr.appendChild(td);tbody.appendChild(tr);return;}
 const ids=[getSelection('a'),getSelection('b')].filter(Boolean),rows=history.rows.filter(r=>ids.includes(r.session_key)&&Number.isFinite(r[$('metric').value])).slice(-80).reverse();
 if(!rows.length){const tr=document.createElement('tr'),td=document.createElement('td');td.colSpan=4;td.className='empty-row';td.textContent='Sem registros neste período.';tr.appendChild(td);tbody.appendChild(tr);return;}
 for(const record of rows){const tr=document.createElement('tr');const cells=[fmtDate(record.time),record.session_key===getSelection('a')?'A':'B',record.source,`${fnum(record[$('metric').value],3)} ${metricInfo()[1]}`];for(const value of cells){const td=document.createElement('td');td.textContent=value;tr.appendChild(td);}tbody.appendChild(tr);}
}
function redraw(){renderChart();renderStats('a');renderStats('b');renderTable();const a=getSelection('a'),b=getSelection('b');$('history-note').textContent=history&&history.downsampled?'Nota: estatísticas calculadas sobre pontos agregados por janela, não sobre cada amostra original. Sessões sem ID são inferidas por pausas e reinícios de sequência.':'Sessões sem ID são inferidas por pausas e reinícios de sequência. As estatísticas usam os pontos exibidos.';if(a&&b&&a===b)$('history-note').textContent+=' Você selecionou a mesma sessão em A e B.';}
function populateSelects(){const choices=history.sessions;
 for(const letter of ['a','b']){
  const node=$('session-'+letter),old=node.value;node.replaceChildren();const blank=document.createElement('option');blank.value='';blank.textContent=letter==='b'?'Não comparar':'Selecione uma sessão';node.appendChild(blank);
  for(const session of choices){const option=document.createElement('option');option.value=session.id;option.textContent=`${fmtDate(session.start)} · ${session.device} · ${session.points} pts${session.approximate?' (inferida)':''}`;node.appendChild(option);}
  if(choices.some(s=>s.id===old))node.value=old;
  else node.value=letter==='a'?(choices[0]?.id||''):(choices[1]?.id||'');
 }
}
function renderOverview(){if(!history)return;$('hist-count').textContent=history.rows.length.toLocaleString('pt-BR');$('hist-sessions').textContent=String(history.sessions.length);$('hist-window').textContent=history.resolution_s===1?'1 segundo':`${history.resolution_s}s`; $('hist-range').textContent=`${fmtDate(history.start)} a ${fmtDate(history.stop)}`;const mode=history.downsampled?'pontos agregados':'dados em resolução de 1s';$('query-detail').textContent=`Consultados ${history.rows.length} pontos (${mode}) no bucket configurado. A origem real ou simulada depende da coluna source.`;}
async function queryHistory(){const button=$('load-history');button.disabled=true;button.textContent='Consultando...';banner('Consultando dados históricos no InfluxDB...',false,false,true);
 try{
  const payload={period:$('period').value};if(payload.period==='custom'){const a=$('custom-start').value,b=$('custom-stop').value;if(!a||!b)throw new Error('Preencha as duas datas do período personalizado.');payload.start=new Date(a).toISOString();payload.stop=new Date(b).toISOString();}
  const result=await post('/api/history',payload);history=result;populateSelects();renderOverview();redraw();
  banner(result.rows.length?`Consulta concluída: ${result.rows.length} pontos em ${result.sessions.length} sessão(ões).`:'Consulta concluída, mas não há dados nesse intervalo. Tente 24 horas ou 7 dias.',false,true);
 }catch(error){banner(error.message,true);$('query-detail').textContent='Se o banco foi reiniciado, conecte novamente em Tempo real.';}
 finally{button.disabled=false;button.textContent='Consultar histórico';}
}
function exportCsv(){if(!history||!history.rows.length){banner('Nenhum dado disponível para exportar. Consulte primeiro.',true);return;}
 const ids=[getSelection('a'),getSelection('b')].filter(Boolean),rows=history.rows.filter(x=>ids.includes(x.session_key));if(!rows.length){banner('Selecione pelo menos uma sessão.',true);return;}
 const headers=['time','session_key','source','device',...history.fields];const data=[headers.join(',')];for(const row of rows)data.push(headers.map(h=>escapeCsv(row[h])).join(','));
 const blob=new Blob(['﻿',data.join('\r\n')+'\r\n'],{type:'text/csv;charset=utf-8'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`CANIDE_historico_${new Date().toISOString().replaceAll(':','-').slice(0,19)}.csv`;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),15000);banner(`CSV gerado com ${rows.length} pontos consultados das sessões selecionadas.`,false,true);
}
async function startup(){const now=new Date(),oneHour=new Date(now.getTime()-3600000);const local=v=>{const date=new Date(v.getTime()-v.getTimezoneOffset()*60000);return date.toISOString().slice(0,16)};$('custom-start').value=local(oneHour);$('custom-stop').value=local(now);
 emptyGraph('Consulte o histórico para ver as sessões.');
 try{const s=await (await fetch('/api/status',{cache:'no-store'})).json();linkState(true,s.influx_configured?'INFLUXDB • '+s.influx_bucket:'GATEWAY ONLINE');if(s.influx_configured){banner(`Conectado ao InfluxDB · ${s.influx_org} / ${s.influx_bucket}`,false,true);await queryHistory();}else banner('InfluxDB não conectado. Abra Tempo real, conecte usando sua organização, bucket e token, e retorne aqui.',true);}
 catch(error){linkState(false,'Gateway desconectado');banner('Não foi possível consultar o gateway: '+error.message,true);}
}
$('period').addEventListener('change',()=> $('custom-period').classList.toggle('hidden',$('period').value!=='custom'));
$('load-history').addEventListener('click',queryHistory);
$('metric').addEventListener('change',redraw);
$('session-a').addEventListener('change',redraw);
$('session-b').addEventListener('change',redraw);
$('export-csv').addEventListener('click',exportCsv);
startup();
