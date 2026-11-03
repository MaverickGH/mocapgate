// Animator tools use existing Studio API and viewers. No external capture product.
let ctx, issues=[], comparison=null, comparisonViewer=null, request=0, qualityRequest=0, lastQuality='', profileList=[], queueSignature='', queueLoading=false;
const $=id=>document.getElementById(id);
const ru=()=>ctx().lang==='ru';
const text=(a,b)=>ru()?a:b;
const node=(tag,content)=>{const n=document.createElement(tag);n.textContent=content;return n;};
const safe=fn=>async()=>{try{await fn();}catch(e){ctx().fail(e);}};
export function init(context){
  ctx=context;
  $('issue-list').addEventListener('change',()=>{if($('issue-list').value)ctx().seek(Number($('issue-list').value)-1);});
  for(const [id,delta] of [['issue-prev',-1],['issue-next',1]]) $(id).onclick=()=>{
    const f=ctx().frame()+1;const list=[...new Set(issues.map(i=>i.frame))].sort((a,b)=>a-b);
    const target=delta>0?list.find(n=>n>f):list.slice().reverse().find(n=>n<f);
    if(target!=null)ctx().seek(target-1);
  };
  $('compare-create').onclick=safe(async()=>{
    const c=ctx();if(!c.take)return;
    const d=await c.api(`/api/takes/${c.take.id}/compare`,{backend:$('compare-backend').value});
    await c.loadTakes();await queueRefresh();
    $('compare-state').textContent=text('Новый дубль добавлен в очередь. Нажмите «Запустить очередь».','New take queued. Click Start queue.');
  });
  $('compare-select').onchange=safe(loadComparison);$('compare-person').onchange=safe(loadComparison);
  $('queue-resume').onclick=safe(async()=>{await ctx().api('/api/queue',{action:'resume'});await queueRefresh();});
  $('queue-pause').onclick=safe(async()=>{await ctx().api('/api/queue',{action:'pause'});await queueRefresh();});
  $('diagnose').onclick=safe(async()=>{
    $('diagnose').disabled=true;$('diagnosis').textContent=text('Проверяю окружение…','Checking environment…');
    try{
      const d=await ctx().api('/api/diagnostics',{});$('diagnosis').replaceChildren();
      $('diagnosis').append(node('p',d.gpu.name));
      for(const check of d.checks){const row=node('p',`${check.ok?'✓':'○'} ${check.id}: `+text(check.ok?'найдено':'нужно настроить',check.ok?'found':'needs setup'));if(check.detail){row.append(node('small',typeof check.detail==='object'?`PyTorch ${check.detail.version} · ${check.detail.cuda?'CUDA':text('CPU — CUDA недоступна','CPU — CUDA unavailable')}`:check.detail));}if(!check.ok){const button=node('button',text('Показать настройки','Show settings'));button.className='small';button.onclick=()=>{if(check.action==='maya')ctx().showView('settings');else{ctx().showView('status');$('status-cards').scrollIntoView({block:'start',behavior:'smooth'});}};row.append(button);} $('diagnosis').append(row);}
      if(d.gvhmr_missing.length)$('diagnosis').append(node('p','GVHMR: '+d.gvhmr_missing.map(k=>({folder:text('папка репозитория','repository folder'),checkpoints:text('веса модели','model weights'),smplx:'SMPL-X',python:text('Python окружения','environment Python'),cuda:text('видеокарта NVIDIA / CUDA','NVIDIA GPU / CUDA'),environment:text('окружение','environment')}[k]||k)).join(', ')));
      $('diagnosis').append(node('small',text('Это проверка обнаруженного окружения. Готовность распознавания подтверждается обработкой тестового видео. Maya нужна только для открытия сцены.','Checks detect configuration; process a test video to verify inference. Maya is optional for opening scenes.')));
    }finally{$('diagnose').disabled=false;}
  });
  $('profile-auto').onclick=safe(async()=>{
    const c=ctx();if(!c.take?.bvh||c.person===0)throw Error(text('Откройте обработанный дубль и выберите участника.','Open a processed take and select a participant.'));
    const body={take:c.take.id,person:c.person,rig:$('profile-rig').value};
    if($('profile-upload').files.length)body.rig_upload=(await c.upload($('profile-upload').files[0])).id;
    const data=await c.api('/api/rig-mapping',body);$('profile-map').value=JSON.stringify(data.mapping,null,2);
    $('profile-state').textContent=text(`Сопоставлено: ${Object.keys(data.mapping).length}. Не сопоставлено: ${data.unmatched.length}. Проверьте имена перед сохранением.`,`Matched: ${Object.keys(data.mapping).length}. Unmatched: ${data.unmatched.length}. Review names before saving.`);
  });
  $('profile-save').onclick=safe(async()=>{
    const profile={name:$('profile-name').value,rig:$('profile-rig').value,mapping:JSON.parse($('profile-map').value),scale:Number($('profile-scale').value),yaw:Number($('profile-yaw').value)};
    if($('profile-upload').files.length){const u=await ctx().upload($('profile-upload').files[0]);profile.rig_upload=u.id;}
    await ctx().api('/api/rig-profiles',profile);$('profile-upload').value='';await refreshProfiles();$('profile-select').value=profile.name;
    $('profile-state').textContent=text('Профиль сохранён. Нажмите «Использовать профиль».','Profile saved. Click Use profile.');
  });
  $('profile-select').onchange=()=>{const p=profileList.find(p=>p.name===$('profile-select').value);if(p){$('profile-name').value=p.name;$('profile-rig').value=p.rig;$('profile-map').value=JSON.stringify(p.mapping,null,2);$('profile-scale').value=p.scale;$('profile-yaw').value=p.yaw;}};
  $('profile-use').onclick=safe(async()=>{await ctx().api('/api/settings',{settings:{rig_profile:$('profile-select').value}});await ctx().refreshStatus();$('profile-state').textContent=text('Профиль выбран для кнопки открытия в Maya. Скачиваемая .ma остаётся подготовленным Man_Rig.','Profile selected for Open in Maya. Downloaded .ma remains the prepared Man_Rig.');});
  setInterval(()=>queueRefresh().catch(()=>{}),2000);
}
export function labels(){
  const items={
    'quality-title':['Проверка движения','Motion review'], 'quality-note':['Метки — кандидаты для ручной проверки, не доказанные ошибки. Пропуски можно показать только при наличии данных наблюдения.','Markers are review candidates, not proven errors. Missing detections require observation data.'],
    'compare-person-label':['Участник второго дубля','Participant in comparison take'],
    'compare-title':['Сравнение распознаваний','Compare recognition'], 'compare-note':['Создайте отдельный дубль другой моделью. Сравнение идёт по времени от начала видео; выберите нужного участника.','Create a separate take with another model. Comparison synchronizes by time from video start; select a participant.'],
    'compare-create':['Добавить другую модель в очередь','Queue another model'], 'compare-select-label':['Готовый дубль для сравнения','Completed take to compare'],
    'queue-title':['Очередь обработки','Processing queue'], 'queue-note':['Дубли обрабатываются по одному; новые запускают очередь сами. После перезапуска Studio прерванные продолжаются кнопкой «Запустить очередь». Пауза не прерывает текущий дубль.','Takes run one at a time; adding a take starts the queue. After restarting Studio, resume interrupted takes with Start queue. Pause lets the current take finish.'],
    'queue-resume':['Запустить очередь','Start queue'], 'queue-pause':['Пауза очереди','Pause queue'],
    'batch-label':['Каждое видео — отдельный дубль в очереди','Each video becomes a separate queued take'], 'diagnose':['Проверить готовность системы','Check system readiness'],
    'profile-upload-note':['Выберите .ma или укажите путь выше. Файл сохраняется локально в настройках приложения.','Choose a .ma or enter its path above. Uploaded rigs stay in local app settings.'],
    'profile-auto':['Подобрать знакомые кости','Match familiar joints'], 'profile-auto-note':['Откройте готовый дубль, затем выберите риг. Автоподбор работает для знакомых скелетов; другие имена добавьте в сопоставление ниже.','Open a completed take, then choose a rig. Matching supports familiar skeletons; add other names below.'],
    'profile-title':['Профили персонажей Maya','Maya character profiles'], 'profile-note':['Укажите локальный .ma и соответствие костей JSON. Масштаб меняет траекторию корня, а не геометрию рига. Профиль применяется при открытии в Maya; произвольные IK/FK-контроллеры не поддерживаются.','Choose a local .ma and a JSON bone mapping. Scale changes root trajectory, not rig geometry. Applied when opening in Maya; arbitrary IK/FK controllers are not supported.'],
    'profile-select-label':['Активный профиль','Active profile'], 'profile-save':['Сохранить профиль','Save profile'], 'profile-use':['Использовать профиль','Use profile']};
  for(const [id,pair] of Object.entries(items))$(id).textContent=pair[ru()?0:1];
  $('issue-prev').title=text('Предыдущая метка','Previous marker');$('issue-next').title=text('Следующая метка','Next marker');
}
export async function refreshProfiles(){profileList=await ctx().api('/api/rig-profiles');$('profile-select').replaceChildren(new Option(text('Без профиля — настройки рига','No profile — rig settings'),''),...profileList.map(p=>new Option(p.name,p.name)));$('profile-select').value=ctx().status?.settings.rig_profile||'';}
export async function queueRefresh(){
  if(queueLoading)return;queueLoading=true;
  try {
  const q=await ctx().api('/api/queue');const signature=JSON.stringify(q)+ctx().lang;
  if(signature===queueSignature)return;queueSignature=signature;
  await ctx().loadTakes();
  const active=q.items.find(i=>i.id===ctx().take?.id&&i.state==='running');
  if(active&&active.job!==ctx().take?.job)ctx().openTake(active.id,active.job);
  const states=ru()?{waiting:'ожидает',running:'обработка',done:'готово',failed:'ошибка',cancelled:'отменено',interrupted:'прервано'}:{};
  $('queue-items').replaceChildren(node('p',text(q.paused?'Очередь на паузе':'Очередь запущена',q.paused?'Queue paused':'Queue running')));
  for(const item of q.items){const take=ctx().takes.find(t=>t.id===item.id);const row=node('div',`${take?.name||item.id} · ${states[item.state]||item.state}`);if(item.error)row.append(node('small',item.error));const open=node('button',text('Открыть','Open'));open.className='small ghost';open.onclick=()=>ctx().openTake(item.id,item.job);row.append(open);if(item.state!=='running'){const remove=node('button','×');remove.title=text('Убрать из очереди','Remove from queue');remove.onclick=safe(async()=>{await ctx().api('/api/queue',{action:'remove',id:item.id});await queueRefresh();});row.append(remove);} $('queue-items').append(row);}
  } finally {queueLoading=false;}
}
export async function review(take,person){
  labels();const key=[take.id,person,take.status,take.bvh,take.job,take.frames,document.documentElement.lang].join(':');  // язык — заново подписать метки
  const options=ctx().takes.filter(t=>t.id!==take.id&&t.status==='done');const selected=$('compare-select').value;
  $('compare-select').replaceChildren(new Option(text('Не сравнивать','No comparison'),''),...options.map(t=>new Option(`${t.name} · ${t.backend}`,t.id)));$('compare-select').value=options.some(t=>t.id===selected)?selected:'';
  if(key===lastQuality)return;lastQuality=key;issues=[];qualityRequest++;request++;comparison=null;comparisonViewer?.clear();$('t-viewer').classList.remove('comparing');$('compare-three').classList.add('hidden');$('compare-select').value='';
  if(!take.bvh||person===0){$('issue-list').replaceChildren(new Option(text('Выберите обработанного участника','Select a processed participant'),''));return;}
  const current=qualityRequest;$('issue-list').replaceChildren(new Option(text('Проверяю кадры…','Checking frames…'),''));
  try{const data=await ctx().api(`/api/takes/${take.id}/motion-events${person?'?person='+person:''}`);if(current!==qualityRequest)return;issues=data.events;
    const quality=take.report?.per_frame||[];for(let i=0;i<quality.length&&issues.length<1000;i++)if(quality[i]===0)issues.push({frame:i+1,kind:'missing',joint:''});
    issues.sort((a,b)=>a.frame-b.frame);
    $('issue-list').replaceChildren(new Option(text(`Метки: ${issues.length}${data.total>1000?' (первые 1000)':''}`,`Markers: ${issues.length}${data.total>1000?' (first 1000)':''}`),''),...issues.map(i=>new Option(`${i.frame} · ${i.joint} · ${i.kind==='missing'?text('нет наблюдения','missing detection'):i.kind==='root_jump'?text('скачок траектории','root jump'):text('скачок вращения','rotation jump')}`,i.frame)));
    ctx().redraw();
  }catch(e){if(current===qualityRequest){$('issue-list').replaceChildren(new Option(text('Проверка не удалась','Review failed'),''));ctx().fail(e);}}
}
export function paint(canvas,count){if(!count)return;const g=canvas.getContext('2d');g.fillStyle='#ef966e';for(const issue of issues)g.fillRect((issue.frame-1)/count*canvas.width,0,Math.max(2,canvas.width/count),canvas.height);}
async function loadComparison(){
  const id=$('compare-select').value;const generation=++request;comparison=null;comparisonViewer?.clear();$('t-viewer').classList.remove('comparing');$('compare-three').classList.add('hidden');if(!id)return;
  $('compare-state').textContent=text('Загружаю сравнение…','Loading comparison…');
  const t=await ctx().api(`/api/takes/${id}`);let chosen=t;
  $('compare-person-wrap').classList.toggle('hidden', !t.people?.length);
  if(t.people?.length){
    const previous=$('compare-person').dataset.take===id?Number($('compare-person').value):ctx().person;
    $('compare-person').dataset.take=id;$('compare-person').replaceChildren(...t.people.map(p=>new Option('ID '+p.id,p.id)));
    chosen=t.people.find(p=>p.id===previous)||t.people[0];$('compare-person').value=chosen.id;
  }
  if(!chosen.bvh)throw Error('No completed BVH');
  const response=await fetch(ctx().withT(`/files/${id}/${encodeURIComponent(chosen.bvh)}`));if(!response.ok)throw Error(response.statusText);
  const bvh=await response.text();if(generation!==request)return;
  comparisonViewer ||= await import('/ui/viewer3d.js').then(m=>m.createViewer($('compare-three')));
  if(generation!==request)return;
  comparisonViewer.setMode('bones');comparisonViewer.setView($('camera-view').value);comparisonViewer.setFollow($('camera-follow').checked);comparisonViewer.loadScene([{text:bvh,color:0xe7a876}]);comparison={fps:chosen.fps||t.fps,frames:chosen.frames||t.frames,label:`${t.name} · ${t.backend}`};$('t-viewer').classList.add('comparing');$('compare-three').classList.remove('hidden');comparisonViewer.resize();ctx().resizeViewer();
  $('compare-state').textContent=`${t.name} · ${t.backend} · ${t.fps} FPS · `+text('Скелет. Сопоставьте одного человека и одно начало видео.','Skeleton. Match the same person and video start.');sync(ctx().frame(),ctx().fps());
}
export function camera(view,follow){comparisonViewer?.setView(view);comparisonViewer?.setFollow(follow);}
export function sync(frame,fps){if(comparison&&comparisonViewer){const f=frame/fps*comparison.fps;
  $('compare-state').textContent=f>=comparison.frames?text('Сравниваемый дубль закончился.','Comparison take has ended.'):`${comparison.label} · ${comparison.fps} FPS · ${Math.floor(f)+1} / ${comparison.frames} · ${(frame/fps).toFixed(3)} s`;
  comparisonViewer.setFrame(Math.min(comparison.frames-1,f));}}
