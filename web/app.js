"use strict";
const el=id=>document.getElementById(id);
const titles={silence:"قص السكوت",transcribe:"كابشن AI",burn:"دمج الترجمة",resize:"تغيير المقاس",compress:"ضغط الفيديو",audio:"استخراج الصوت",scenes:"كشف المشاهد",thumbnail:"صورة مصغرة",denoise:"تنظيف الصوت"};
let files=[],jobs=[],action="silence";
const elem=(tag,cls,txt)=>{const x=document.createElement(tag);if(cls)x.className=cls;if(txt!==undefined)x.textContent=txt;return x;};
async function api(url,options){
 const r=await fetch(url,options),d=await r.json();
 if(!r.ok)throw new Error(d.error||"Request failed");
 return d;
}
function notice(message,error=false){
 const x=el("toast");x.textContent=message;x.className="toast show"+(error?" error":"");
 clearTimeout(notice.timer);notice.timer=setTimeout(()=>x.className="toast",6000);
}
const configs={
 silence:'<label class="field">حساسية السكوت dB<input name="threshold" type="number" min="-60" max="-15" value="-35"></label><label class="field">أقل مدة سكوت<input name="minimum" type="number" step=".05" value=".35"></label><label class="field">هامش القص<input name="padding" type="number" step=".05" value=".12"></label>',
 transcribe:'<label class="field">اللغة<select name="language"><option value="auto">تلقائي</option><option value="ar">العربية</option><option value="en">English</option></select></label><label class="field">الموديل<select name="model"><option>tiny</option><option selected>base</option><option>small</option><option>medium</option></select></label>',
 burn:'<label class="field">ملف الترجمة<select name="subtitle_id" id="subtitleSelect"></select></label>',
 resize:'<label class="field">النسبة<select name="ratio"><option>9:16</option><option>16:9</option><option>1:1</option><option>4:5</option></select></label><label class="field">الملاءمة<select name="fit"><option value="crop">قص الحواف</option><option value="pad">حواف سوداء</option></select></label>',
 compress:'<label class="field">الجودة CRF<input name="crf" type="number" min="18" max="36" value="28"></label>',
 audio:'<p class="muted">تحويل الصوت إلى MP3.</p>',
 scenes:'<label class="field">الحساسية<select name="scene_threshold"><option value=".25">عالية</option><option value=".35" selected>متوسطة</option><option value=".5">منخفضة</option></select></label>',
 thumbnail:'<label class="field">الثانية<input name="second" type="number" min="0" value="1"></label>',
 denoise:'<p class="muted">تقليل ضوضاء الصوت.</p>'
};

function populateSubtitles(){
 const select=el("subtitleSelect");if(!select)return;
 select.replaceChildren();
 const choices=[];
 files.filter(f=>/\.(srt|ass|vtt)$/i.test(f.name)).forEach(f=>choices.push({id:f.id,name:f.name}));
 jobs.forEach(j=>(j.artifacts||[]).filter(a=>/\.(srt|ass|vtt)$/i.test(a.name)).forEach(a=>choices.push({id:a.id,name:a.name+" · "+titles[j.action]})));
 choices.forEach(f=>{const o=elem("option","",f.name);o.value=f.id;select.appendChild(o);});
}
function selectTool(tool){
 action=tool;el("currentTool").textContent=titles[tool];el("options").innerHTML=configs[tool];
 document.querySelectorAll(".tool").forEach(b=>b.classList.toggle("selected",b.dataset.tool===tool));
 if(tool==="burn")populateSubtitles();
}
function updatePreview(){
 const item=files.find(f=>f.id===el("selectedMedia").value),video=el("preview");
 if(!item||item.details.subtitle){video.hidden=true;video.removeAttribute("src");return;}
 video.hidden=false;
 if(video.dataset.id!==item.id){
  video.dataset.id=item.id;
  video.src="/api/source?id="+encodeURIComponent(item.id);
  video.load();
 }
}

function renderMedia(){
 const grid=el("fileGrid"),sel=el("selectedMedia"),previous=sel.value;
 grid.replaceChildren();sel.replaceChildren();el("empty").style.display=files.length?"none":"block";
 files.forEach(f=>{
  const o=elem("option","",f.name);o.value=f.id;sel.appendChild(o);
  const box=elem("div","file"),icon=elem("div","glyph",f.details.subtitle?"▤":"▶");
  const txt=elem("div","txt"),b=elem("b","",f.name),small=elem("small","",((f.details.bytes||0)/1048576).toFixed(1)+" MB");
  txt.append(b,small);box.append(icon,txt);grid.appendChild(box);
  box.addEventListener("click",()=>{sel.value=f.id;updatePreview();});
 });
 if([...sel.options].some(o=>o.value===previous))sel.value=previous;
 el("mediaCount").textContent=files.length;
 updatePreview();
 if(action==="burn")populateSubtitles();
}
function renderJobs(){
 const area=el("jobs");area.replaceChildren();
 let done=0,running=0;
 if(!jobs.length)area.appendChild(elem("p","muted","لسه مفيش مهام."));
 jobs.forEach(j=>{
  if(j.status==="done")done++;if(j.status==="running"||j.status==="queued")running++;
  const box=elem("div","job"),main=elem("div","job-main");
  main.append(elem("b","",titles[j.action]||j.action),elem("small","",j.status==="failed"?(j.error||"فشلت المهمة"):j.id.slice(0,10)));
  const state=elem("span","tag "+(j.status==="done"?"done":j.status==="failed"?"failed":""),j.status==="done"?"اكتملت":j.status==="failed"?"فشلت":"جاري التنفيذ");
  const links=elem("div","job-links");
  (j.artifacts||[]).forEach(a=>{const link=elem("a","",a.name);link.href="/api/file?id="+encodeURIComponent(a.id);link.download=a.name;links.appendChild(link);});
  box.append(main,state,links);area.appendChild(box);
 });
 el("doneCount").textContent=done;el("runCount").textContent=running;
 if(action==="burn")populateSubtitles();
}

async function refresh(){
 try{
  const result=await Promise.all([api("/api/media"),api("/api/jobs")]);
  files=result[0];jobs=result[1];renderMedia();renderJobs();
 }catch(err){notice(err.message,true);}
}
async function uploadMedia(event){
 const incoming=[...event.target.files];if(!incoming.length)return;
 for(const file of incoming){
  if(file.size>2147483648){notice("الملف أكبر من 2GB: "+file.name,true);continue;}
  try{
   notice("جار رفع "+file.name+" ...");
   await api("/api/upload?name="+encodeURIComponent(file.name),{method:"POST",body:file});
   notice("تمت إضافة "+file.name);
  }catch(err){notice(file.name+": "+err.message,true);}
 }
 event.target.value="";await refresh();
}
async function startJob(){
 const media_id=el("selectedMedia").value;
 if(!media_id){notice("اختار ملف الأول",true);return;}
 const options={};
 el("options").querySelectorAll("[name]").forEach(x=>{options[x.name]=x.value;});
 if(action==="burn"&&!options.subtitle_id){notice("ارفع ملف SRT أو اعمل كابشن أولاً",true);return;}
 const button=el("run");button.disabled=true;button.textContent="يتم إرسال المهمة...";
 try{
  await api("/api/jobs",{method:"POST",headers:{"Content-Type":"application/json"},
   body:JSON.stringify({action,media_id,options})});
  notice("المهمة اتضافت للطابور");await refresh();el("activity").scrollIntoView({behavior:"smooth"});
 }catch(err){notice(err.message,true);}
 finally{button.disabled=false;button.textContent="▶  شغّل المهمة";}
}
async function proposeEdit(){
 const prompt=el("aiPrompt").value.trim();
 if(!prompt){notice("اكتب المطلوب من المونتير",true);return;}
 const button=el("aiPlan");button.disabled=true;button.textContent="جاري التفكير...";
 try{
  const plan=await api("/api/plan",{method:"POST",headers:{"Content-Type":"application/json"},
   body:JSON.stringify({prompt,model:el("aiModel").value})});
  selectTool(plan.action);
  for(const [name,value] of Object.entries(plan.options)){
   const input=el("options").querySelector('[name="'+name+'"]');
   if(input)input.value=String(value);
  }
  el("aiResult").textContent=plan.explanation+" — جهزت أداة "+titles[plan.action]+". راجع الإعدادات واضغط شغّل المهمة.";
  el("workshop").scrollIntoView({behavior:"smooth"});
 }catch(err){notice("Ollama: "+err.message,true);}
 finally{button.disabled=false;button.textContent="اقترح التعديل";}
}

async function boot(){
 document.querySelectorAll(".tool").forEach(b=>b.addEventListener("click",()=>selectTool(b.dataset.tool)));
 el("upload").addEventListener("change",uploadMedia);
 el("selectedMedia").addEventListener("change",updatePreview);
 el("run").addEventListener("click",startJob);
 el("aiPlan").addEventListener("click",proposeEdit);
 el("refresh").addEventListener("click",refresh);
 selectTool("silence");
 try{
  const s=await api("/api/status");
  el("engine").textContent=s.ffmpeg&&s.ffprobe?"● FFmpeg جاهز":"● FFmpeg غير مثبت";
  if(!s.ffmpeg)notice("مطلوب تثبيت FFmpeg قبل التشغيل",true);
 }catch(err){notice(err.message,true);}
 await refresh();setInterval(refresh,4000);
}
boot();
