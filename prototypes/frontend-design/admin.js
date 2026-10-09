"use strict";
// UI review only. Data comes from tab-local demo-store, never production APIs.
const admin$=id=>document.getElementById(id);
const safe=value=>String(value??"").replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const statusNames={active:"Đang bật",paused:"Tạm dừng",draft:"Bản nháp",approved:"Đã duyệt mẫu",blocked:"Bị chặn",unchecked:"Chưa kiểm tra",ok:"Ổn định",partial:"Một phần",new:"Chưa xử lý",in_progress:"Đang xử lý",resolved:"Đã xử lý",open:"Đang mở",idle:"Không hoạt động",expired:"Hết hạn",succeeded:"Hoàn tất",failed:"Lỗi",cancelled:"Đã hủy",running:"Đang chạy"};
const categoryNames={feedback:"Góp ý trải nghiệm",data_issue:"Thông tin tour / nguồn",support:"Cần hỗ trợ"};
const dateText=value=>value?new Intl.DateTimeFormat("vi-VN",{timeZone:"Asia/Ho_Chi_Minh",day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"}).format(new Date(value)):"Chưa có";
const badge=value=>value?'<span class="status-badge" data-state="'+safe(value)+'">'+safe(statusNames[value]||value)+'</span>':"Chưa có";
let adminSection="overview",dialogOpener=null,dialogResource=null,adminToastTimer;
function bounds(){const to=Date.parse("2026-10-07T17:00:00Z"),period=admin$("admin-period").value;return {from:period==="all"?0:to-(period==="today"?1:7)*86400000,to};}
function inRange(value){const t=Date.parse(value),{from,to}=bounds();return t>=from&&t<to;}
function notifyAdmin(copy){clearTimeout(adminToastTimer);admin$("admin-toast").textContent=copy;admin$("admin-toast").hidden=false;adminToastTimer=setTimeout(()=>admin$("admin-toast").hidden=true,3500);}
function setSection(name,push=true){
  adminSection=["overview","sources","contacts","sessions"].includes(name)?name:"overview";
  document.querySelectorAll(".admin-section").forEach(el=>el.hidden=el.id!=="section-"+adminSection);
  document.querySelectorAll(".admin-tabs [data-section]").forEach(el=>{if(el.dataset.section===adminSection)el.setAttribute("aria-current","page");else el.removeAttribute("aria-current");});
  if(push&&location.hash!=="#"+adminSection)history.pushState(null,"","#"+adminSection);renderAdmin();
}
function renderAdmin(){
  const d=window.PrototypeDemo.read(),events=d.events.filter(e=>inRange(e.at)),runs=events.filter(e=>e.kind==="comparison");
  const activeIds=new Set(events.filter(e=>["user_message","comparison","contact"].includes(e.kind)).map(e=>e.session_id));
  const contacts=d.contacts.filter(c=>inRange(c.created_at)),backlog=contacts.filter(c=>c.status!=="resolved").length;
  const messages=events.filter(e=>e.kind==="user_message").reduce((sum,e)=>sum+(e.count||1),0);
  admin$("period-description").textContent=admin$("admin-period").value==="today"?"00:00–24:00 · giờ Việt Nam":admin$("admin-period").value==="all"?"Tất cả bản ghi mô phỏng":"01–07/10/2026 · giờ Việt Nam";
  admin$("source-count").textContent=d.sources.length;admin$("contact-count").textContent=d.contacts.filter(c=>c.status!=="resolved").length;
  admin$("overview-metrics").innerHTML=[
    ["Phiên có hoạt động",activeIds.size,"Đếm phiên riêng biệt trong kỳ"],
    ["Tin người dùng",messages,"Không gồm phản hồi AI và log"],
    ["Lượt tìm",runs.length,"Gồm hoàn tất, đang chạy, lỗi, hủy"],
    ["Liên hệ cần xử lý",backlog,"Liên hệ trong kỳ, chưa đóng"]
  ].map(([label,value,hint])=>'<article class="admin-metric"><span>'+label+'</span><strong>'+value+'</strong><small>'+hint+'</small></article>').join("");
  admin$("run-breakdown").innerHTML=["succeeded","partial","failed","cancelled","running"].map(status=>{const count=runs.filter(r=>r.status===status).length;return '<div class="run-bar" data-state="'+status+'"><span>'+statusNames[status]+'</span><div class="run-bar-track" aria-hidden="true"><span style="--fill:'+((count/Math.max(1,runs.length))*100)+'%"></span></div><strong>'+count+'</strong></div>';}).join("");
  const needs=d.sources.filter(s=>s.access_status!=="approved"||s.state!=="active"),waiting=d.contacts.filter(c=>c.status!=="resolved").length;
  admin$("attention-list").innerHTML='<div class="attention-row"><div><strong>'+waiting+' liên hệ đang chờ</strong><small>Góp ý và yêu cầu hỗ trợ của người dùng</small></div><button class="text-action" data-section="contacts" type="button">Xử lý →</button></div><div class="attention-row"><div><strong>'+needs.length+' nguồn cần kiểm tra</strong><small>Tạm dừng, chưa duyệt hoặc bị chặn</small></div><button class="text-action" data-section="sources" type="button">Xem nguồn →</button></div><div class="attention-row"><div><strong>'+d.sources.reduce((n,s)=>n+s.tours,0)+' tour / '+d.sources.reduce((n,s)=>n+s.offers,0)+' offer mẫu</strong><small>Snapshot hiện tại · chưa là dữ liệu crawl thật</small></div></div>';
  admin$("recent-activity").innerHTML=events.slice().sort((a,b)=>b.at.localeCompare(a.at)).slice(0,6).map(e=>'<div class="activity-row"><time>'+dateText(e.at)+'</time><span>'+safe(e.summary)+'</span><small>'+safe(e.session_id)+'</small></div>').join("")||'<p class="admin-empty">Chưa có hoạt động trong khoảng thời gian này.</p>';
  const sourceFilter=admin$("source-filter").value,query=admin$("source-search").value.trim().toLocaleLowerCase("vi-VN");
  const sources=d.sources.filter(s=>(sourceFilter==="all"||s.state===sourceFilter)&&(!query||(s.name+" "+s.domain).toLocaleLowerCase("vi-VN").includes(query)));
  admin$("source-table").innerHTML=sources.map(s=>'<tr><td><strong data-preserve>'+safe(s.name)+'</strong><small>'+safe(s.domain)+'</small></td><td>'+badge(s.state)+'</td><td>'+badge(s.access_status)+'</td><td>'+s.tours+' tour<br><small>'+s.offers+' offer</small></td><td>'+dateText(s.last_run_at)+'</td><td><button class="text-action" data-source-detail="'+s.id+'" type="button">Quản lý →</button></td></tr>').join("")||'<tr><td colspan="6" class="admin-empty">Không có nguồn theo bộ lọc này.</td></tr>';
  const contactFilter=admin$("contact-filter").value,category=admin$("contact-category-filter").value;
  admin$("contact-table").innerHTML=contacts.filter(c=>(contactFilter==="all"||c.status===contactFilter)&&(category==="all"||c.category===category)).map(c=>'<tr><td><strong>'+safe(categoryNames[c.category])+'</strong><small>'+c.id+'</small></td><td class="message-preview">'+safe(c.message.slice(0,140))+(c.message.length>140?"…":"")+'</td><td>'+badge(c.status)+'</td><td>'+dateText(c.created_at)+'</td><td><button class="text-action" data-contact-detail="'+c.id+'" type="button">Mở liên hệ →</button></td></tr>').join("")||'<tr><td colspan="5" class="admin-empty">Không có liên hệ theo bộ lọc và khoảng thời gian này.</td></tr>';
  const sessionFilter=admin$("session-filter").value;
  admin$("session-table").innerHTML=d.sessions.filter(s=>activeIds.has(s.id)&&(sessionFilter==="all"||s.state===sessionFilter)).map(s=>{const own=events.filter(e=>e.session_id===s.id);return '<tr><td><strong>'+s.id+'</strong><small>'+dateText(s.started_at)+'</small></td><td>'+own.filter(e=>e.kind==="user_message").reduce((n,e)=>n+(e.count||1),0)+'</td><td>'+own.filter(e=>e.kind==="comparison").length+'</td><td>'+badge(s.state)+'</td><td>'+badge(s.last_job_status)+'</td><td><button class="text-action" data-session-detail="'+s.id+'" type="button">Xem tiến độ →</button></td></tr>';}).join("")||'<tr><td colspan="6" class="admin-empty">Không có phiên có hoạt động theo bộ lọc này.</td></tr>';
}
function openAdminDialog(title,content,resource){
  if(!admin$("admin-dialog").open)dialogOpener=document.activeElement;
  dialogResource=resource;admin$("admin-dialog-title").toggleAttribute("data-preserve",resource.type==="source");admin$("admin-dialog-title").textContent=title;admin$("admin-dialog-body").innerHTML=content;
  if(!admin$("admin-dialog").open)admin$("admin-dialog").showModal();admin$("close-admin-dialog").focus();
}
function sourceDetail(id){
  const d=window.PrototypeDemo.read(),s=d.sources.find(s=>s.id===id);if(!s)return;
  const rows=[["Domain",s.domain],["Thu thập",statusNames[s.state]],["Quyền truy cập",statusNames[s.access_status]],["Kiểm tra lúc",dateText(s.checked_at)],["Profile",s.profile],["Field có dữ liệu",s.fields.join(" · ")||"Chưa xác định"],["Snapshot",s.tours+" tour / "+s.offers+" offer mẫu"],["Chất lượng",statusNames[s.health]]];
  openAdminDialog(s.name,'<dl class="admin-detail-list">'+rows.map(([key,value])=>'<div><dt>'+key+'</dt><dd>'+safe(value)+'</dd></div>').join("")+'</dl><p class="admin-quote">'+safe(s.notes)+'</p><div class="admin-actions"><button class="btn" type="button" data-toggle-source="'+id+'"'+(s.access_status!=="approved"?' disabled':'')+'>'+(s.state==="active"?"Tạm dừng nguồn":"Bật nguồn mẫu")+'</button><button class="btn" type="button" data-check-source="'+id+'">Kiểm tra & duyệt mẫu</button><button class="text-action" type="button" data-refresh-source="'+id+'"'+(s.state!=="active"||s.access_status!=="approved"?' disabled':'')+'>Làm mới dữ liệu mẫu</button></div><p class="admin-helper">Check và refresh chỉ đổi trạng thái mô phỏng. Nguồn bị chặn giữ bị chặn; chưa có request tới website.</p><form id="admin-source-edit" class="admin-contact-form" data-source-id="'+id+'"><label>Tên nguồn<input name="name" maxlength="100" required value="'+safe(s.name)+'"></label><label>Ghi chú nguồn<textarea name="notes" rows="2" maxlength="1000">'+safe(s.notes)+'</textarea></label><button class="btn" type="submit">Lưu thông tin nguồn mẫu</button></form><h3>Lịch sử quản lý</h3><ul class="admin-timeline">'+(d.audit.filter(a=>a.resource_id===id).slice(0,5).map(a=>'<li><time>'+dateText(a.at)+'</time>'+safe(a.action)+'</li>').join("")||'<li>Chưa có thay đổi trong tab này.</li>')+'</ul>',{type:"source",id});
}
function contactDetail(id){
  const c=window.PrototypeDemo.read().contacts.find(c=>c.id===id);if(!c)return;
  openAdminDialog(categoryNames[c.category],'<p class="admin-quote">'+safe(c.message)+'</p><dl class="admin-detail-list"><div><dt>Mã liên hệ</dt><dd>'+c.id+'</dd></div><div><dt>Gửi lúc</dt><dd>'+dateText(c.created_at)+'</dd></div><div><dt>Cách liên hệ</dt><dd>'+safe(c.reply_to||"Người dùng chưa để lại")+'</dd></div><div><dt>Phiên</dt><dd>'+safe(c.session_id)+'</dd></div></dl><form id="admin-contact-form" class="admin-contact-form" data-ticket="'+id+'"><label>Trạng thái<select name="status">'+["new","in_progress","resolved"].map(status=>'<option value="'+status+'"'+(c.status===status?' selected':'')+'>'+statusNames[status]+'</option>').join("")+'</select></label><label>Ghi chú nội bộ<textarea name="note" rows="3" maxlength="1000" placeholder="Nhóm đã kiểm tra điều gì, cần theo dõi gì thêm…"></textarea></label><button class="btn btn-primary" type="submit">Lưu xử lý mẫu</button></form><p class="admin-helper">Chưa gửi email hoặc phản hồi ra ngoài.</p><ul class="admin-timeline">'+c.notes.map(note=>'<li><time>'+dateText(note.at)+'</time><span data-preserve>'+safe(note.text)+'</span></li>').join("")+'</ul>',{type:"contact",id});
}
function sessionDetail(id){
  const d=window.PrototypeDemo.read(),s=d.sessions.find(s=>s.id===id);if(!s)return;
  openAdminDialog("Tiến độ phiên",'<dl class="admin-detail-list"><div><dt>Phiên</dt><dd>'+id+'</dd></div><div><dt>Tin người dùng</dt><dd>'+s.user_message_count+' · toàn phiên</dd></div><div><dt>Lượt tìm</dt><dd>'+s.comparison_count+' · toàn phiên</dd></div><div><dt>Hoạt động cuối</dt><dd>'+dateText(s.last_active_at)+'</dd></div></dl><ol class="admin-timeline">'+d.events.filter(e=>e.session_id===id).slice(-15).map(e=>'<li><time>'+dateText(e.at)+'</time>'+safe(e.summary)+'</li>').join("")+'</ol><p class="admin-helper">Tiến độ mô phỏng. Không hiển thị nội dung chat hoặc thông tin nhu cầu cá nhân.</p>',{type:"session",id});
}
document.addEventListener("click",event=>{
  const section=event.target.closest("[data-section]");if(section){event.preventDefault();setSection(section.dataset.section);return;}
  const source=event.target.closest("[data-source-detail]");if(source){sourceDetail(source.dataset.sourceDetail);return;}
  const contact=event.target.closest("[data-contact-detail]");if(contact){contactDetail(contact.dataset.contactDetail);return;}
  const session=event.target.closest("[data-session-detail]");if(session){sessionDetail(session.dataset.sessionDetail);return;}
  for(const [attribute,method,copy] of [["toggleSource","toggleSource","Đã cập nhật trạng thái nguồn mẫu."],["checkSource","checkSource","Đã mô phỏng kiểm tra nguồn. Nguồn bị chặn không được bật."],["refreshSource","refreshSource","Đã cập nhật thời điểm làm mới mẫu; chưa crawl thật."]]){
    const button=event.target.closest('[data-'+attribute.replace(/[A-Z]/g,c=>"-"+c.toLowerCase())+']');
    if(button){const id=button.dataset[attribute];window.PrototypeDemo[method](id);sourceDetail(id);notifyAdmin(copy);return;}
  }
});
document.addEventListener("submit",event=>{if(event.target.id==="admin-source-edit"){event.preventDefault();const v=new FormData(event.target),name=String(v.get("name")).trim();if(!name){notifyAdmin("Tên nguồn cần có nội dung.");return;}const id=event.target.dataset.sourceId;window.PrototypeDemo.editSource(id,name,String(v.get("notes")).trim());sourceDetail(id);notifyAdmin("Đã cập nhật tên và ghi chú nguồn mẫu.");return;}if(event.target.id!=="admin-contact-form")return;event.preventDefault();const values=new FormData(event.target);window.PrototypeDemo.updateContact(event.target.dataset.ticket,values.get("status"),String(values.get("note")).trim());admin$("admin-dialog").close();notifyAdmin("Đã lưu trạng thái và ghi chú nội bộ trong mẫu.");});
admin$("add-source").addEventListener("click",()=>{admin$("source-form").hidden=false;admin$("source-form").querySelector("input").focus();});
admin$("close-source-form").addEventListener("click",()=>{admin$("source-form").hidden=true;admin$("add-source").focus();});
admin$("source-form").addEventListener("submit",event=>{event.preventDefault();const values=Object.fromEntries(new FormData(event.target));Object.keys(values).forEach(key=>values[key]=values[key].trim());if(Object.values(values).some(value=>!value)){notifyAdmin("Điền đủ tên, domain mẫu và profile.");return;}window.PrototypeDemo.addSource(values);event.target.reset();event.target.hidden=true;admin$("source-filter").value="all";admin$("source-search").value="";renderAdmin();notifyAdmin("Đã thêm nguồn nháp. Kiểm tra mẫu trước khi bật.");});
admin$("close-admin-dialog").addEventListener("click",()=>admin$("admin-dialog").close());
admin$("admin-dialog").addEventListener("close",()=>{if(dialogOpener?.isConnected)dialogOpener.focus();else if(dialogResource){const selector='[data-'+dialogResource.type+'-detail="'+dialogResource.id+'"]';document.querySelector(selector)?.focus();}});
admin$("reset-admin").addEventListener("click",()=>{window.PrototypeDemo.reset();notifyAdmin("Đã khôi phục nguồn, liên hệ và số đếm demo.");});
["admin-period","source-filter","contact-filter","contact-category-filter","session-filter"].forEach(id=>admin$(id).addEventListener("change",renderAdmin));
admin$("source-search").addEventListener("input",renderAdmin);window.addEventListener("prototype:store",renderAdmin);window.addEventListener("popstate",()=>setSection(location.hash.slice(1),false));
setSection(location.hash.slice(1)||"overview",false);
