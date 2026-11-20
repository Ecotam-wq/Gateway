"use strict";
const $ = (id) => document.getElementById(id);
const format = (v, decimals=2) => v == null || !Number.isFinite(Number(v)) ? '—' : Number(v).toLocaleString('pt-BR',{minimumFractionDigits:decimals,maximumFractionDigits:decimals});
const colors = {temperature:'#f9bd7b',pressure:'#76a8ff',humidity:'#42dbbc',altitude:'#d9b8ff',latitude:'#62d6e3',longitude:'#bb9cff',gpsAltitude:'#ffe19d',satellites:'#8be2b7',fix:'#7ac8ff'};
const DEF = [
 {id:'temperature',key:'temperature_c',decimal:2,color:colors.temperature},
 {id:'pressure',key:'pressure_pa',calc:v=>v/100,decimal:2,color:colors.pressure},
 {id:'humidity',key:'humidity_pct',decimal:2,color:colors.humidity},
 {id:'altitude',key:'altitude_m',decimal:2,color:colors.altitude},
 {id:'latitude',key:'latitude',decimal:7,color:colors.latitude,fixOnly:true},
 {id:'longitude',key:'longitude',decimal:7,color:colors.longitude,fixOnly:true},
 {id:'gps-altitude',key:'gps_altitude_m',decimal:2,color:colors.gpsAltitude,fixOnly:true},
 {id:'satellites',key:'satellites',decimal:0,color:colors.satellites},
 {id:'fix',key:'gps_fix',decimal:0,color:colors.fix,boolean:true}
];
let initialized=false, previousBucket='SEU_BUCKET', pollBusy=false;
function isFiniteNum(v) { return v!==null && v!==undefined && v!=='' && Number.isFinite(Number(v)); }
function sampleValue(s,def){
 if(!s || (def.fixOnly && s.gps_fix!==true))return null;
 const v=s[def.key];
 if(def.boolean) return typeof v==='boolean'?(v?1:0):null;
 if(!isFiniteNum(v))return null;
 const n=Number(v);return def.calc?def.calc(n):n;
}
function svgText(x,y,txt,anchor='start',size=11){return `<text x="${x}" y="${y}" text-anchor="${anchor}" fill="#91aab9" font-size="${size}">${txt}</text>`;}
function blank(id,note){const el=$(id);el.innerHTML=svgText(260,104,note,'middle',13);}
function chart(def, samples){
 const el=$('chart-'+def.id),meta=$('meta-'+def.id),W=520,H=210,L=71,R=15,T=16,B=37;
 const vals=samples.map(s=>sampleValue(s,def));
 const available=vals.map((v,i)=>v===null?null:{v,i}).filter(v=>v!==null);
 if(!available.length){blank('chart-'+def.id,'Sem dados válidos nesta janela');meta.textContent='Aguardando pacotes com este campo.';return;}
 let lo=Math.min(...available.map(p=>p.v)),hi=Math.max(...available.map(p=>p.v));
 if(def.boolean){lo=-.15;hi=1.15;} else if(def.key==='humidity_pct'){lo=Math.max(0,lo-4);hi=Math.min(100,hi+4);if(hi-lo<1){lo-=1;hi+=1;}}
 else {const span=Math.max(hi-lo,def.decimal>=6?0.00001:0.1);lo-=span*.2;hi+=span*.2;}
 const x=i=>L+(samples.length<=1?.5:i/(samples.length-1))*(W-L-R);
 const y=v=>T+(hi-v)/(hi-lo)*(H-T-B);
 let grid='';for(let i=0;i<=3;i++){let value=hi-(hi-lo)*i/3;let digits=def.decimal>=6?6:(def.boolean?0:(hi-lo<10?2:1));grid+=`<line x1="${L}" x2="${W-R}" y1="${T+i*(H-T-B)/3}" y2="${T+i*(H-T-B)/3}" stroke="#264255" stroke-dasharray="4 5"/>`+svgText(L-8,T+i*(H-T-B)/3+4,value.toFixed(digits),'end',10);}
 let segments=[],part=[];
 vals.forEach((v,i)=>{if(v===null){if(part.length)segments.push(part);part=[];}else part.push({v,i});});if(part.length)segments.push(part);
 let paths=segments.map(part=>`<path d="${part.map((p,i)=>`${i?'L':'M'}${x(p.i).toFixed(2)} ${y(p.v).toFixed(2)}`).join(' ')}" stroke="${def.color}" fill="none" stroke-width="2.7" stroke-linecap="round" stroke-linejoin="round"/>`).join('');
 const last=available.at(-1);paths+=`<circle cx="${x(last.i)}" cy="${y(last.v)}" r="4" fill="${def.color}" stroke="#0e1d2c" stroke-width="2"/>`;
 const timestamps=samples.map(s=>Number(s.timestamp_ms));
 const fmtTime=t=>Number.isFinite(t)?new Date(t).toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit',second:'2-digit'}):'—';
 let axes=svgText(L,H-11,fmtTime(timestamps[0]),'start',10)+svgText(W-R,H-11,fmtTime(timestamps.at(-1)),'end',10);
 el.innerHTML=grid+paths+axes;
 meta.textContent=`${available.length}/${samples.length} amostras com valor válido · último: ${format(last.v,def.decimal)}`;
}
function chartTrack(samples){
 const el=$('chart-track'),meta=$('meta-track'),valid=samples.filter(s=>s.gps_fix===true&&isFiniteNum(s.latitude)&&isFiniteNum(s.longitude));
 if(!valid.length){blank('chart-track','Sem posições GPS válidas');meta.textContent='Requer fix GPS e protocolo V3.';return;}
 const W=520,H=210,L=64,R=21,T=17,B=39;
 const lat=valid.map(s=>Number(s.latitude)),lon=valid.map(s=>Number(s.longitude));
 let a=Math.min(...lat),b=Math.max(...lat),c=Math.min(...lon),d=Math.max(...lon);
 // Manter desenho visível se o módulo estiver parado, sem inventar deslocamento.
 const latSpan=Math.max(b-a,.00001),lonSpan=Math.max(d-c,.00001);
 const y=v=>T+(b+latSpan*.1-v)/(latSpan*1.2)*(H-T-B);
 const x=v=>L+(v-c+lonSpan*.1)/(lonSpan*1.2)*(W-L-R);
 const line=valid.map((s,i)=>`${i?'L':'M'}${x(Number(s.longitude)).toFixed(2)},${y(Number(s.latitude)).toFixed(2)}`).join(' ');
 const first=valid[0],last=valid.at(-1);
 el.innerHTML=`<rect x="${L}" y="${T}" width="${W-L-R}" height="${H-T-B}" rx="5" fill="#091827" stroke="#24475a"/><path d="${line}" fill="none" stroke="#42dbbc" stroke-width="2.4"/><circle cx="${x(Number(first.longitude))}" cy="${y(Number(first.latitude))}" r="4" fill="#76a8ff"/><circle cx="${x(Number(last.longitude))}" cy="${y(Number(last.latitude))}" r="5" fill="#f9bd7b"/>`+svgText(L,H-13,'Oeste / longitude','start',10)+svgText(W-R,H-13,'Leste','end',10)+svgText(L+7,T+15,'N ↑','start',11);
 meta.textContent=`${valid.length} posições válidas · azul: início, amarelo: última · variações podem ser ruído GPS`;
}
function lastDefined(samples,def){for(let i=samples.length-1;i>=0;i--){const v=sampleValue(samples[i],def);if(v!==null)return v;}return null;}
function updateFlux(){ $('flux').textContent=`from(bucket: ${JSON.stringify(previousBucket)})\n  |> range(start: -30m)\n  |> filter(fn: (r) => r._measurement == "ecotam_telemetry")\n  |> filter(fn: (r) => contains(value: r._field, set: [\n    "temperature_c", "pressure_pa", "humidity_pct",\n    "altitude_m", "latitude", "longitude",\n    "gps_altitude_m", "satellites", "gps_fix"]))`;}
function message(id,txt,err=false){const el=$(id);el.textContent=txt;el.classList.toggle('err',err);}
async function post(endpoint,payload){const r=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const out=await r.json();if(!r.ok)throw Error(out.error||`HTTP ${r.status}`);return out;}
async function refresh(){
 if(pollBusy)return;pollBusy=true;
 try{
  const resp=await fetch('/api/status',{cache:'no-store'});if(!resp.ok)throw Error(`HTTP ${resp.status}`);
  const state=await resp.json();
  if(!initialized){$('source-mode').value=state.source;$('source-port').value=state.port||'COM3';initialized=true;}
  const expectedSource=state.source==='rx'?'rx_serial':'sim';
  const samples=state.samples.filter(s=>s.source===expectedSource).slice(-Number($('window-size').value||120));
  const last=samples.at(-1),age=last?Math.max(0,(Date.now()-Number(last.timestamp_ms))/1000):null;
  const fresh=age!==null&&age<8;
  $('dot').classList.toggle('on',fresh);
  $('mode-label').textContent=state.source==='rx'?'RX • '+state.port:'SIMULAÇÃO';
  $('fresh-label').textContent=fresh?'Atualizando em tempo real':age!==null?`Sem novas amostras há ${Math.round(age)} s`:'Aguardando primeiras amostras';
  $('last-sample-time').textContent='Última leitura: '+(last?new Date(last.timestamp_ms).toLocaleTimeString('pt-BR'):'—');
  const version=last?.protocol_version;
  $('protocol-label').textContent=`Protocolo: ${version===3?'V3 / 84 B':version===2?'V2 / 64 B':state.source==='sim'?'simulador':'aguardando'}`;
  const v3=version===3;
  $('bme-status').textContent=last&&isFiniteNum(last.temperature_c)?(fresh?'Recebendo':'Sem dados recentes'):'Aguardando';
  $('gps-status').textContent=v3?(last?.gps_fix===true?'Fix válido':last?.gps_fix===false?'Sem fix':'Aguardando'):'Requer V3';
  for(const def of DEF){
   const v=last?sampleValue(last,def):null;
   if(def.id!=='fix'){
    const textNode=$(def.id==='gps-altitude'?'gps-altitude':def.id);
    if(textNode)textNode.textContent=format(v,def.decimal);
   }
   chart(def,samples);
  }
  chartTrack(samples);
  $('samples-total').textContent=state.count.toLocaleString('pt-BR');
  $('rx-frames').textContent=state.rx_frames.toLocaleString('pt-BR');
  $('queue-drops').textContent=state.queue_drops.toLocaleString('pt-BR');
  $('influx-ok').textContent=state.influx_writes.toLocaleString('pt-BR');
  $('influx-fail').textContent=state.influx_failed.toLocaleString('pt-BR');
  $('last-write').textContent=state.last_write||'—';
  $('influx-status').textContent=state.influx_status;
  $('error-status').textContent=[state.csv_error,state.rx_error,state.influx_error].filter(Boolean).join(' | ');
  $('rx-live').textContent=state.source==='rx'?`COM ${state.port} · ${state.rx_lines} linhas · ${state.rx_headers} cabeçalhos · ${state.rx_frames} frames · ${state.rx_last_age_s??'—'} s desde o último frame`:'Simulador selecionado: dados artificiais. Mude para RX/COM3 para observar os sensores.';
  if(state.influx_bucket&&state.influx_bucket!==previousBucket){previousBucket=state.influx_bucket;updateFlux();}
 }catch(err){$('mode-label').textContent='Gateway desconectado';$('dot').classList.remove('on');$('error-status').textContent=String(err);}
 finally{pollBusy=false;}
}
$('influx-form').addEventListener('submit',async e=>{e.preventDefault();message('connect-message','Conectando ao InfluxDB…');try{const out=await post('/api/connect',{url:$('influx-url').value,org:$('influx-org').value,bucket:$('influx-bucket').value,token:$('influx-token').value});$('influx-token').value='';previousBucket=$('influx-bucket').value;updateFlux();message('connect-message',out.message);}catch(err){message('connect-message',String(err),true);}});
$('disconnect-button').addEventListener('click',async()=>{try{const out=await post('/api/disconnect',{});message('connect-message',out.message);}catch(err){message('connect-message',String(err),true);}});
$('source-apply').addEventListener('click',async()=>{try{const out=await post('/api/source',{mode:$('source-mode').value,port:$('source-port').value});message('source-message',out.message);await refresh();}catch(err){message('source-message',String(err),true);}});
$('copy-flux').addEventListener('click',()=>{navigator.clipboard.writeText($('flux').textContent).then(()=>message('connect-message','Consulta Flux copiada.')).catch(()=>message('connect-message','Selecione e copie a consulta.',true));});
$('window-size').addEventListener('change',refresh);
updateFlux();refresh();setInterval(refresh,1000);
