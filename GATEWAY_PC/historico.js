'use strict';
const $ = id => document.getElementById(id);
const META = {
 altitude_m:['Altitude BME280','m'], pressure_pa:['Pressão','Pa'], temperature_c:['Temperatura','°C'],
 humidity_pct:['Umidade relativa','% UR'], gps_altitude_m:['Altitude GPS','m'], latitude:['Latitude','graus'], longitude:['Longitude','graus'], satellites:['Satélites','nº'],
 battery_v:['Bateria','V'], accel_x:['Aceleração X','m/s²'], accel_y:['Aceleração Y','m/s²'],
 accel_z:['Aceleração Z','m/s²'], gyro_x:['Giroscópio X','unid. simulada'],
 gyro_y:['Giroscópio Y','unid. simulada'], gyro_z:['Giroscópio Z','unid. simulada']
};
const COLORS = ['#42dbbc','#76a8ff'];
const fnum = (v,d=2) => v===null || v===undefined || !Number.isFinite(Number(v)) ? '—' : Number(v).toLocaleString('pt-BR',{minimumFractionDigits:d,maximumFractionDigits:d});
const fmtDate = iso => new Date(iso).toLocaleString('pt-BR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit'});
let history = null;
let activeSeries = [];
function banner(message,error=false,ok=false){const node=$('history-status');node.textContent=message;node.classList.toggle('error',error);node.classList.toggle('ok',ok);}
async function post(endpoint,payload){const response=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const data=await response.json();if(!response.ok)throw new Error(data.error||`HTTP ${response.status}`);return data;}
function metricInfo(){return META[$('metric').value]||['Medição',''];}
function emptyGraph(message){const svg=$('historic-chart');svg.innerHTML='';const t=document.createElementNS('http://www.w3.org/2000/svg','text');t.setAttribute('x','50%');t.setAttribute('y','50%');t.setAttribute('text-anchor','middle');t.setAttribute('fill','#9aadc0');t.setAttribute('font-size','14');t.textContent=message;svg.appendChild(t);$('chart-tooltip').classList.add('hidden');}
function escapeCsv(value){let out=String(value??'');if(/^[=+@\-\t\r]/.test(out) && !/^\-?\d+(?:\.\d+)?$/.test(out))out="'"+out;return '"'+out.replaceAll('"','""')+'"';}
function getSelection(id){return $('session-'+id).value;}
function getSessionRows(sessionKey,metric){if(!history||!sessionKey)return [];const points=history.rows.filter(p=>p.session_key===sessionKey&&Number.isFinite(p[metric]));if(!points.length)return [];const start=Date.parse(points[0].time);return points.map(p=>({time:p.time,elapsed:(Date.parse(p.time)-start)/1000,value:p[metric],source:p.source,device:p.device}));}
function makeSvg(tag,attrs,parent){const node=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [name,value] of Object.entries(attrs||{}))node.setAttribute(name,String(value));if(parent)parent.appendChild(node);return node;}
function addText(svg,x,y,content,anchor='start',size=11){const t=makeSvg('text',{x,y,fill:'#90aab9','text-anchor':anchor,'font-size':size},svg);t.textContent=content;}
function renderChart(){
 const svg=$('historic-chart'),metric=$('metric').value,[name,unit]=metricInfo();svg.innerHTML='';activeSeries=[];
 const ids=[getSelection('a'),getSelection('b')];
 ids.forEach((id,i)=>{const points=getSessionRows(id,metric);if(points.length)activeSeries.push({id,points,color:COLORS[i],slot:i});});
 if(!activeSeries.length){emptyGraph('Sem pontos para a variável e sessão selecionadas.');return;}
 const all=activeSeries.flatMap(s=>s.points),vals=all.map(p=>p.value),maxX=Math.max(1,...all.map(p=>p.elapsed));
 let minY=Math.min(...vals),maxY=Math.max(...vals);const spread=Math.max(.001,maxY-minY);minY-=spread*.13;maxY+=spread*.13;
 const W=940,H=300,L=88,R=18,T=24,B=46,plotW=W-L-R,plotH=H-T-B;
 svg.setAttribute('viewBox',`0 0 ${W} ${H}`);
 const x=v=>L+v/maxX*plotW,y=v=>T+(maxY-v)/(maxY-minY)*plotH;
 for(let i=0;i<=4;i++){
  const gy=T+i*plotH/4;
  makeSvg('line',{x1:L,x2:W-R,y1:gy,y2:gy,stroke:'#254055','stroke-dasharray':'4 5'},svg);
  addText(svg,L-10,gy+4,fnum(maxY-i*(maxY-minY)/4,maxY-maxY/2>10000?0:2),'end');
 }
 for(let i=0;i<=5;i++){
  const sx=L+i*plotW/5;makeSvg('line',{x1:sx,x2:sx,y1:H-B,y2:H-B+5,stroke:'#446274'},svg);
  addText(svg,sx,H-18,fnum(i*maxX/5,maxX<100?0:0)+' s','middle');
 }
 activeSeries.forEach(series=>{
  const d=series.points.map((p,i)=>`${i?'L':'M'}${x(p.elapsed).toFixed(2)} ${y(p.value).toFixed(2)}`).join(' ');
  makeSvg('path',{d,fill:'none',stroke:series.color,'stroke-width':2.5,'stroke-linejoin':'round','stroke-linecap':'round'},svg);
  const last=series.points.at(-1);makeSvg('circle',{cx:x(last.elapsed),cy:y(last.value),r:4,fill:series.color},svg);
 });
 $('axis-label').textContent=`Tempo decorrido (s) · ${name} (${unit})`;
 svg.onpointermove=e=>{
  const rect=svg.getBoundingClientRect();const px=(e.clientX-rect.left)/rect.width*W;const elapsed=Math.max(0,Math.min(maxX,(px-L)/plotW*maxX));
  const near=activeSeries.map(series=>{
   const points=series.points;let lo=0,hi=points.length-1;while(lo<hi){const mid=Math.floor((lo+hi)/2);if(points[mid].elapsed<elapsed)lo=mid+1;else hi=mid;}const prev=points[Math.max(0,lo-1)],p=Math.abs(prev.elapsed-elapsed)<Math.abs(points[lo].elapsed-elapsed)?prev:points[lo];return {series,p};
  });
  const tooltip=$('chart-tooltip');tooltip.replaceChildren();
  for(const {series,p} of near){const line=document.createElement('div');line.style.color=series.color;line.textContent=`${series.slot?'B':'A'} · ${fnum(p.value,3)} ${unit} · ${fnum(p.elapsed,0)} s`;tooltip.appendChild(line);}
  tooltip.classList.remove('hidden');tooltip.style.left=Math.max(6,Math.min(rect.width-205,e.clientX-rect.left+12))+'px';tooltip.style.top=Math.max(4,e.clientY-rect.top-46)+'px';
 };
 svg.onpointerleave=()=> $('chart-tooltip').classList.add('hidden');
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
async function queryHistory(){const button=$('load-history');button.disabled=true;button.textContent='Consultando...';banner('Consultando dados históricos no InfluxDB...');
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
 const blob=new Blob(['\ufeff',data.join('\r\n')+'\r\n'],{type:'text/csv;charset=utf-8'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`ECOTAM_historico_${new Date().toISOString().replaceAll(':','-').slice(0,19)}.csv`;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),15000);banner(`CSV gerado com ${rows.length} pontos consultados das sessões selecionadas.`,false,true);
}
async function startup(){const now=new Date(),oneHour=new Date(now.getTime()-3600000);const local=v=>{const date=new Date(v.getTime()-v.getTimezoneOffset()*60000);return date.toISOString().slice(0,16)};$('custom-start').value=local(oneHour);$('custom-stop').value=local(now);
 try{const s=await (await fetch('/api/status',{cache:'no-store'})).json();if(s.influx_configured){banner(`Conectado ao InfluxDB · ${s.influx_org} / ${s.influx_bucket}`,false,true);await queryHistory();}else banner('InfluxDB não conectado. Abra Tempo real, conecte usando sua organização, bucket e token, e retorne aqui.',true);}
 catch(error){banner('Não foi possível consultar o gateway: '+error.message,true);}
}
$('period').addEventListener('change',()=> $('custom-period').classList.toggle('hidden',$('period').value!=='custom'));
$('load-history').addEventListener('click',queryHistory);
$('metric').addEventListener('change',redraw);
$('session-a').addEventListener('change',redraw);
$('session-b').addEventListener('change',redraw);
$('export-csv').addEventListener('click',exportCsv);
startup();
