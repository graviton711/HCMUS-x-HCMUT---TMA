"use strict";
// Local planning experiment: fixed fixtures, deterministic chat and mock jobs.
$("landing-root").innerHTML=window.landingMarkup||"<h1 id='home-heading'>Đi cùng</h1>";
Object.assign(iconPaths,{search:'<circle cx="10" cy="10" r="6"/><path d="m15 15 5 5"/>',mail:'<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 6 9 7 9-7"/>'});
const preferenceNames={pref_cost:"Tiết kiệm chi phí",pref_comfort:"Khách sạn tiện nghi",pref_pace:"Nhịp đi thư thả",pref_culture:"Trải nghiệm văn hóa"};
const preferenceLevels=["Không ưu tiên","Ưu tiên nhẹ","Vừa phải","Quan trọng","Rất quan trọng","Ưu tiên cao nhất"];
const sampleCriteria={destination:"Nhật Bản",origin:"TP.HCM",date:"2026-11-10",adults:"2",budget:"35000000",duration:"5",children:"0",ages:"",hotel:"",shopping:"few",url:"",notes:"",pref_cost:"3",pref_comfort:"3",pref_pace:"3",pref_culture:"3"};
let criteria={...sampleCriteria},resultCriteria=null,currentRevision=0,resultRevision=0,hasResults=false;
let proposal=null,activeRun=0,runTimers=[],running=false,chatBusy=false,chatGeneration=0,notes=[],lastRunRequest=null;
let activeScreen="home",tourScreen="form";
const labels={destination:"Điểm đến",origin:"Khởi hành",date:"Ngày dự kiến",adults:"Người lớn",budget:"Ngân sách",duration:"Thời lượng",children:"Trẻ em",ages:"Tuổi trẻ em",hotel:"Khách sạn",shopping:"Mua sắm",url:"URL tham chiếu",notes:"Lưu ý thêm",...preferenceNames};
const requiredKeys=["destination","origin","date","adults","budget"];
const choices={destination:[["Nhật Bản","Nhật Bản"]],origin:[["TP.HCM","TP.HCM"]],duration:[["5","Khoảng 5 ngày"],["6","Khoảng 6 ngày"],["","Chưa chỉ định"]],hotel:[["","Chưa chỉ định"],["3","Từ 3 sao"],["4","Từ 4 sao"],["5","Từ 5 sao"]],shopping:[["","Chưa chỉ định"],["few","Ưu tiên ít điểm"],["none","Bắt buộc không có"]]};
function displayValue(key,value){
  if(value===""||value==null)return "Chưa chỉ định";
  if(preferenceNames[key])return preferenceLevels[Number(value)]+" · "+value+"/5";
  if(choices[key])return choices[key].find(entry=>entry[0]===value)?.[1]||value;
  if(key==="budget")return money(Number(value))+" / người lớn";
  if(key==="date")return value.split("-").reverse().join("/");
  if(key==="adults"||key==="children")return value+" người";
  return value;
}
function sliderMarkup(prefix,data){return Object.entries(preferenceNames).map(([key,label])=>{
  const id=prefix+key,value=data[key]??"3",level=Number(value),pending=proposal?.changes[key]!==undefined;
  return '<div class="preference-slider'+(pending?' preference-pending':'')+'"><div class="preference-title"><label for="'+id+'">'+label+'</label><output for="'+id+'" id="'+id+'-output">'+preferenceLevels[level]+'</output></div><div class="preference-control" style="--range-progress:'+(level/5)+'"><span class="range-track" aria-hidden="true"><span></span></span><input type="range" id="'+id+'" min="0" max="5" step="1" value="'+value+'" aria-valuetext="'+preferenceLevels[level]+'" data-preference="'+key+'" data-scope="'+(prefix==="need-"?'form':'results')+'"'+(prefix!=="need-"&&(running||chatBusy)?' disabled':'')+'></div><div class="preference-endpoints" aria-hidden="true"><span>Không ưu tiên</span><span>Rất quan tâm</span></div></div>';
}).join("");}
function updateSlider(input){const level=Number(input.value);input.closest(".preference-control").style.setProperty("--range-progress",String(level/5));$(input.id+"-output").textContent=preferenceLevels[level];input.setAttribute("aria-valuetext",preferenceLevels[level]);}
function syncForm(source=criteria){Object.keys(sampleCriteria).forEach(key=>{const el=$("need-"+key);if(el){el.value=source[key];if(el.type==="range")updateSlider(el);}});$("child-age-field").hidden=Number(source.children)===0;}
function fillSample(){syncForm({...sampleCriteria,notes:notes.join(" · ")});toast("Đã điền nhu cầu mẫu Nhật Bản vào form để review. Chưa đổi yêu cầu đã xác nhận.");navigate("form");}
function readForm(){const next={};Object.keys(sampleCriteria).forEach(key=>{next[key]=$("need-"+key)?.value.trim()||"";});next.notes=notes.join(" · ");return next;}
function validUrl(value){try{const u=new URL(value);return ["http:","https:"].includes(u.protocol)&&!u.username&&!u.password&&(!u.port||["80","443"].includes(u.port));}catch{return false;}}
function validation(next){
  const errors={};requiredKeys.forEach(key=>{if(!next[key])errors[key]="Điền "+labels[key].toLowerCase()+" trước khi tìm.";});
  if(next.adults&&(!Number.isInteger(Number(next.adults))||Number(next.adults)<1||Number(next.adults)>100))errors.adults="Nhập từ 1 đến 100 người lớn.";
  if(next.budget&&(!Number.isInteger(Number(next.budget))||Number(next.budget)<=0||Number(next.budget)>1000000000))errors.budget="Nhập ngân sách hợp lệ bằng VND, lớn hơn 0.";
  if(next.date&&(!/^\d{4}-\d{2}-\d{2}$/.test(next.date)||next.date<"2026-10-07"))errors.date="Chọn ngày từ 07/10/2026.";
  if(!Number.isInteger(Number(next.children))||Number(next.children)<0||Number(next.children)>20)errors.children="Nhập từ 0 đến 20 trẻ em.";
  if(Number(next.children)>0){const ages=next.ages.split(",").map(s=>s.trim());if(ages.length!==Number(next.children)||ages.some(a=>!/^\d+$/.test(a)||Number(a)>17))errors.ages="Điền đủ tuổi từng trẻ (0–17), cách nhau bằng dấu phẩy.";}
  if(next.url&&!validUrl(next.url))errors.url="Nhập URL HTTP(S) hợp lệ, không có tài khoản hoặc mật khẩu.";
  Object.keys(preferenceNames).forEach(key=>{if(!Number.isInteger(Number(next[key]))||Number(next[key])<0||Number(next[key])>5)errors[key]="Chọn mức sở thích từ 0 đến 5.";});
  return errors;
}
function showFormErrors(errors){
  document.querySelectorAll(".field-error").forEach(el=>el.remove());
  Object.keys(sampleCriteria).forEach(key=>{const field=$("need-"+key);field?.removeAttribute("aria-invalid");if(field?.getAttribute("aria-describedby")?.startsWith("error-"))field.removeAttribute("aria-describedby");});
  $("form-error").hidden=!Object.keys(errors).length;
  if(!Object.keys(errors).length)return;
  $("form-error").textContent="Còn "+Object.keys(errors).length+" thông tin cần kiểm tra. Các giá trị đã nhập được giữ lại.";
  Object.entries(errors).forEach(([key,msg])=>{const field=$("need-"+key);field.setAttribute("aria-invalid","true");const hint=document.createElement("span");hint.className="field-error";hint.id="error-"+key;hint.textContent=msg;field.setAttribute("aria-describedby",hint.id);field.closest(".journey-field,.preference-slider").append(hint);});
  $("need-"+Object.keys(errors)[0]).focus();
}
function navigate(screen,writeHistory=true){
  if(screen==="tours")screen=tourScreen;
  if(!["home","form","results","contact","support"].includes(screen))screen="home";
  if(screen==="results"&&!hasResults&&!running)screen="form";
  if(screen==="form"&&running)stopRun(false);
  if(screen!=="results"){chatGeneration++;lockChat(false);}
  if(screen==="form")syncForm({...criteria,...proposal?.changes});
  activeScreen=screen;if(["form","results"].includes(screen))tourScreen=screen;
  ["home","form","results","contact","support"].forEach(name=>$("screen-"+name).hidden=name!==screen);
  const navSection=["form","results"].includes(screen)?"tours":screen;
  document.querySelectorAll(".app-nav [data-nav]").forEach(el=>{if(el.dataset.nav===navSection)el.setAttribute("aria-current","page");else el.removeAttribute("aria-current");});
  document.querySelector(".site-header").dataset.section=navSection;
  if(writeHistory&&location.hash!=="#"+screen)history.pushState({screen},"","#"+screen);
  window.scrollTo({top:0,behavior:"instant"});
  const heading=$(screen+"-heading");heading?.focus({preventScroll:true});
  if(heading){heading.classList.remove("heading-enter");void heading.offsetWidth;heading.classList.add("heading-enter");}
  renderCriteria();
}
function renderCriteria(){
  const urlOnly=state.scenario==="url-only"&&resultRevision===currentRevision;
  const preview={...criteria,...proposal?.changes};
  $("criteria-revision").textContent=proposal?Object.keys(proposal.changes).length+" chờ xác nhận":hasResults&&resultRevision!==currentRevision?"Đã sửa":"Đã xác nhận";
  const core=["destination","origin","date","adults","budget"],extras=["duration","children","ages","hotel","shopping","url","notes"];
  function rows(keys){return keys.map(key=>{
    const pending=proposal?.changes[key]!==undefined;
    const value=urlOnly&&!pending?(key==="destination"?"Nhật Bản · từ URL" :key==="url"?"tour-minh-hoa.example/ref":"Chưa chỉ định"):displayValue(key,preview[key]);
    return '<div class="criteria-row'+(pending?' criteria-pending':'')+'"><span>'+escapeHtml(labels[key])+'</span><button class="criteria-value" type="button" data-inline="'+key+'" aria-label="Sửa '+escapeHtml(labels[key])+'"'+(running||chatBusy?' disabled':'')+'><span>'+escapeHtml(value)+(pending?'<small class="draft-label">Chưa xác nhận</small>':'')+'</span>'+icon("edit")+'</button></div>';
  }).join("");}
  $("criteria-fields").innerHTML='<p class="criteria-group-label">'+(urlOnly?"Phạm vi từ tour tham chiếu":"Thông tin cần thiết")+'</p>'+rows(core)+'<p class="criteria-group-label">Thông tin bổ sung</p><div class="criteria-extras">'+rows(extras)+'</div><div class="criteria-row readonly"><span>Phạm vi giá</span><p>Giá tour / người lớn · ưu tiên</p></div><section class="preferences-block" aria-labelledby="preferences-heading"><h3 id="preferences-heading">Mức độ sở thích</h3><p>Kéo để sửa ưu tiên · Mức mẫu</p>'+sliderMarkup("result-",{...criteria,...proposal?.changes})+'</section>';
  const stale=hasResults&&resultRevision!==currentRevision;
  $("criteria-warning").hidden=!stale;
  $("criteria-warning").textContent=running?"Đang tìm theo yêu cầu mới. Kết quả trước vẫn được giữ để bạn tham khảo.":"Yêu cầu đã thay đổi. Bấm Tìm kiếm để cập nhật kết quả.";
  $("result-revision").textContent=running?"Đang tìm kiếm…":stale?"Kết quả theo yêu cầu trước":hasResults?"Kết quả theo yêu cầu đã xác nhận":"Sẵn sàng tìm kiếm";
  $("search-tours").disabled=running||chatBusy||Boolean(proposal);
  $("edit-many").disabled=running||chatBusy;
  $("search-button-label").textContent=running?"Đang tìm…":"Tìm kiếm";
  renderSyncStatus();hydrateIcons($("criteria-fields"));
}
function renderSyncStatus(){
  const stale=hasResults&&resultRevision!==currentRevision,pending=Boolean(proposal),banner=$("result-sync");
  const changed=hasResults?Object.keys(labels).filter(key=>resultCriteria?.[key]!==criteria[key]):[];
  banner.dataset.sync=stale?"stale":pending?"pending":running?"running":hasResults?"matched":"empty";
  const title=stale?(running?"Đang tìm theo yêu cầu mới":"Kết quả chưa theo yêu cầu mới"):pending?"Có thay đổi chưa xác nhận":running?"Đang tìm kiếm":hasResults?"Kết quả dùng đúng bản yêu cầu":"Sẵn sàng tìm kiếm";
  const copy=stale?"Bảng và phân tích bên dưới vẫn dùng bản yêu cầu trước. "+(pending?"Bạn còn thay đổi chưa xác nhận. ":"")+(running?"Kết quả mới sẽ thay thế khi xử lý xong.":"Bấm Tìm kiếm để cập nhật."):pending?"Các ô đang sửa chưa áp dụng. Bạn có thể sửa thêm, xác nhận cả nhóm hoặc hủy về bản đã xác nhận.":running?"Bảng cũ được giữ trong lúc xử lý. Hủy tìm kiếm vẫn giữ yêu cầu đã xác nhận.":hasResults?"Bảng và phân tích dùng cùng bản yêu cầu đã xác nhận. Tour minh họa chưa được kiểm tra đủ để kết luận đáp ứng mọi điều kiện.":"Xác nhận yêu cầu rồi bắt đầu tìm tour.";
  banner.innerHTML=icon(stale?"warning":pending?"edit":running?"route":hasResults?"check":"info")+'<div><strong>'+title+'</strong><p>'+copy+'</p>'+(changed.length?'<details class="sync-differences"><summary>'+changed.length+' tiêu chí khác với lượt kết quả đang xem</summary><ul>'+changed.map(key=>'<li><span>'+escapeHtml(labels[key])+'</span><span>'+escapeHtml(displayValue(key,resultCriteria?.[key]))+' → <b>'+escapeHtml(displayValue(key,criteria[key]))+'</b></span></li>').join("")+'</ul></details>':"")+(hasResults?'<button class="text-action" type="button" id="sync-basis">Xem yêu cầu của bảng này '+icon("source")+'</button>':"")+'</div>';
}
function selectedTours(){return state.scenario==="empty"?[]:groups[state.round].slice(0,state.scenario==="limited"?2:3).map(getTour);}
function renderAnalysis(){
  const selected=selectedTours(),panel=$("analysis-panel");
  if(!selected.length){panel.innerHTML='<div class="analysis-content empty-state"><h2>Chưa có đủ dữ kiện để phân tích.</h2><p>Điều chỉnh yêu cầu qua chat hoặc kiểm tra nguồn; không tạo nhận định khi chưa có tour.</p></div>';return;}
  const first=selected[0],second=selected[1],budget=Number(resultCriteria?.budget)||0,adults=Number(resultCriteria?.adults)||0;
  const urlOnly=state.scenario==="url-only",difference=second?first.price-second.price:0;
  const budgetStatus=urlOnly?"Chưa có ngân sách cá nhân để đánh giá.":first.price<=budget?"Giá công bố của gợi ý đầu nằm trong ngân sách ưu tiên.":"Giá công bố của gợi ý đầu vượt ngân sách ưu tiên "+money(first.price-budget)+".";
  panel.innerHTML='<div class="analysis-content"><span class="analysis-kicker">PHÂN TÍCH MINH HỌA · THEO LƯỢT KẾT QUẢ ĐANG XEM</span>'+
    '<div class="analysis-intro">'+icon("balance")+'<div><h2>'+(second?"Giá thấp hơn có một đánh đổi.":"Một tour, chưa đủ để so đánh đổi.")+'</h2><p>'+escapeHtml(second?second.name+" có giá công bố thấp hơn "+first.name+", nhưng kéo dài 6 ngày và có điểm mua sắm. Lựa chọn phụ thuộc ưu tiên của bạn.":first.name+" có thể kiểm tra dữ kiện, nhưng chưa có tour thứ hai để đối chiếu.")+'</p></div></div>'+
    '<div class="analysis-metrics"><article class="analysis-metric"><span>Chênh lệch giá công bố / người lớn</span><strong>'+(second?money(difference):"Chưa đủ tour")+'</strong><small>'+escapeHtml(second?first.name+" − "+second.name:"Cần ít nhất hai tour")+'</small><button class="text-action" type="button" data-source="'+first.id+'.price">Giá gợi ý 01 '+icon("source")+'</button>'+(second?'<button class="text-action" type="button" data-source="'+second.id+'.price">Giá gợi ý 02 '+icon("source")+'</button>':"")+'</article><article class="analysis-metric"><span>Giá tour mẫu cho '+(urlOnly?"nhóm chưa rõ":adults+" người lớn")+'</span><strong>'+(urlOnly?"Chưa thể tính":money(first.price*adults))+'</strong><small>'+escapeHtml(urlOnly?"Chưa có số người":money(first.price)+" × "+adults+" người lớn")+'</small><p>Chưa gồm phụ thu'+(Number(resultCriteria?.children)>0?" và giá trẻ em":"")+'. Chưa phải tổng cuối của chuyến đi.</p><button class="text-action" type="button" data-source="'+first.id+'.price">Kiểm tra giá mẫu '+icon("source")+'</button></article></div>'+
    '<div class="analysis-rows"><article class="analysis-row"><span>01</span><div><h3>Đối chiếu với yêu cầu đã dùng</h3><p>'+escapeHtml(budgetStatus)+' '+(urlOnly?"Phạm vi Nhật Bản lấy từ tour tham chiếu, chưa suy ra sở thích riêng.":"Thời lượng ưu tiên: "+displayValue("duration",resultCriteria?.duration)+". Gợi ý đầu có "+first.days+".")+'</p><button class="text-action" type="button" data-source="'+first.id+'.dates">Xem lịch & thời lượng '+icon("source")+'</button></div></article>'+
    (second?'<article class="analysis-row"><span>02</span><div><h3>Tiết kiệm giá, đổi lại thêm thời gian</h3><p>'+escapeHtml(second.name)+" có "+escapeHtml(second.shopping)+'. So với gợi ý đầu, giá công bố thấp hơn '+money(difference)+' / người lớn; chưa đủ dữ kiện để so tổng chi phí mỗi ngày.</p><button class="text-action" type="button" data-source="'+second.id+'.shopping">Xem lịch trình mua sắm '+icon("source")+'</button></div></article>':"")+
    '<article class="analysis-row"><span>03</span><div><h3>Điều chưa biết ảnh hưởng quyết định</h3><p>Phụ thu, chính sách hủy hoặc dịch vụ còn thiếu ở một số tour. Các giá gắn với lịch riêng; chưa xác minh còn chỗ hoặc nguồn độc lập.</p><button class="text-action" type="button" data-source="'+(selected[2]?.id||first.id)+'.'+(selected[2]?"cancel":"extras")+'">Mở dữ kiện còn thiếu '+icon("source")+'</button></div></article></div>'+
    '<div class="analysis-preferences"><h3>Mức sở thích của lượt này</h3><p>'+Object.keys(preferenceNames).map(key=>escapeHtml(preferenceNames[key])+": "+escapeHtml(displayValue(key,resultCriteria?.[key]))).join(" · ")+'</p><small>Thể hiện mức bạn chọn trong mẫu; chưa dùng để tính điểm hoặc xếp hạng thật.</small></div><details class="calculation-details"><summary>Xem phép tính và điều kiện áp dụng</summary><p><code>'+escapeHtml(second?money(first.price)+" − "+money(second.price)+" = "+money(difference):"Chưa có hai tour để tính chênh lệch")+'</code></p><p>Cùng đơn vị VND / người lớn và phạm vi giá tour. Giá thuộc ngày công bố ở từng cột; khác lịch khởi hành và chưa đủ phụ thu nên chưa chứng minh tour nào rẻ hơn về tổng cuối.</p><p>Phép tính từ fixture, không điểm AI hay tổng nhóm do backend xác nhận. Đổi offer cập nhật giá, ngày, bằng chứng và các phép tính cùng lúc.</p></details>'+
    '<p class="analysis-limit">Mẫu giải thích từ dữ liệu cố định, chưa có AI hoặc xếp hạng theo yêu cầu mới. Nhận định có điều kiện, không kết luận tour tốt nhất hay thay bạn quyết định.</p></div>';
}
function refreshExtras(){
  renderCriteria();renderAnalysis();
  $("round-label").textContent="Nhóm 0"+(state.round+1)+" · Fixture minh họa";
  $("suggestions-title").textContent=selectedTours().length+" gợi ý mô phỏng";
  document.querySelector(".intro-copy").textContent="Dữ kiện và phân tích từ cùng lượt kết quả. Trao đổi ở cột yêu cầu để điều chỉnh.";
  $("fixture-summary").textContent="Bộ tour Nhật Bản / TP.HCM tháng 11 cố định. Chưa truy xuất, kiểm tra đủ ràng buộc hoặc xếp hạng theo nhu cầu.";
  if(state.reference&&state.scenario!=="source-error"){const label=$("reference-strip").querySelector(".reference-label");if(label)label.textContent="Tham chiếu minh họa · Chưa đọc URL đã nhập";}
}
document.addEventListener("prototype:render",refreshExtras);
function addMessage(role,message,html=false){
  const div=document.createElement("div");div.className="chat-message "+role;
  if(html)div.innerHTML=message;else div.textContent=message;
  $("results-chat-log").append(div);$("results-chat-log").scrollTop=$("results-chat-log").scrollHeight;return div;
}
function clearProposal(){proposal=null;$("pending-change").hidden=true;$("pending-change").innerHTML="";}
function focusConfirmation(){requestAnimationFrame(()=>{if($("pending-change").hidden)return;const action=$("confirm-change");action.scrollIntoView({block:"center",behavior:matchMedia("(prefers-reduced-motion: reduce)").matches?"instant":"smooth"});action.focus({preventScroll:true});});}
function propose(changes,searchAfterConfirm=false){
  const merged={...proposal?.changes,...changes};
  Object.keys(merged).forEach(key=>{if(merged[key]===criteria[key])delete merged[key];});
  const requestedSearch=searchAfterConfirm||Boolean(proposal?.searchAfterConfirm);
  proposal=Object.keys(merged).length?{changes:merged,revision:currentRevision,searchAfterConfirm:requestedSearch}:null;
  renderCriteria();renderProposal();if(proposal)focusConfirmation();
}
function renderProposal(){
  if(!proposal){$("pending-change").hidden=true;$("pending-change").innerHTML="";return;}
  const entries=Object.entries(proposal.changes);
  $("pending-change").innerHTML='<h4>'+entries.length+' thay đổi chờ xác nhận</h4><p>So với bản đã xác nhận gần nhất. Bạn có thể tiếp tục sửa nhiều mục.</p>'+entries.map(([key,value])=>'<div class="batch-change"><div class="batch-change-title"><strong>'+escapeHtml(labels[key])+'</strong><button type="button" class="text-action" data-discard-change="'+key+'" aria-label="Bỏ thay đổi '+escapeHtml(labels[key])+'">Bỏ</button></div><div class="change-diff"><div><span>Đã xác nhận</span><strong>'+escapeHtml(displayValue(key,criteria[key]))+'</strong></div>'+icon("arrow")+'<div><span>Đang sửa</span><strong>'+escapeHtml(displayValue(key,value))+'</strong></div></div></div>').join("")+'<p>'+(proposal.searchAfterConfirm?"Bạn đã yêu cầu tìm kiếm; xác nhận cả nhóm xong sẽ bắt đầu tìm.":"Xác nhận cả nhóm để cập nhật. Tìm kiếm khi bạn sẵn sàng.")+'</p><div class="actions"><button class="btn btn-primary" type="button" id="confirm-change">Xác nhận tất cả '+entries.length+' thay đổi</button><button class="text-action" type="button" id="continue-edit">Tiếp tục sửa</button><button class="text-action" type="button" id="reject-change">Hủy tất cả</button></div>';
  $("pending-change").hidden=false;
}
function rejectProposal(){
  clearProposal();$("bulk-editor").hidden=true;renderCriteria();syncForm();addMessage("assistant","Đã hủy mọi thay đổi chưa xác nhận và khôi phục bản đã xác nhận gần nhất.");$("results-chat-message").focus();
}
function openBulk(){
  const preview={...criteria,...proposal?.changes},keys=Object.keys(labels).filter(key=>!preferenceNames[key]);
  $("bulk-editor").innerHTML='<h3>Sửa nhiều thông tin</h3><p>Chỉnh các mục cần đổi rồi thêm vào cùng nhóm xác nhận.</p><div class="bulk-fields">'+keys.map(key=>{
    const type=key==="date"?"date":["adults","budget","children"].includes(key)?"number":"text";
    const control=choices[key]?'<select name="'+key+'">'+choices[key].map(([value,label])=>'<option value="'+escapeHtml(value)+'"'+(preview[key]===value?' selected':'')+'>'+escapeHtml(label)+'</option>').join("")+'</select>':'<input name="'+key+'" type="'+type+'" value="'+escapeHtml(preview[key])+'"'+(key==="url"?' maxlength="2048"':' maxlength="500"')+'>';
    return '<label>'+escapeHtml(labels[key])+control+'</label>';
  }).join("")+'</div><p id="bulk-errors" role="alert" hidden></p><div class="actions"><button class="btn" type="submit">Thêm vào nhóm xác nhận</button><button class="text-action" type="button" id="close-bulk">Đóng trình sửa</button></div>';
  $("bulk-editor").hidden=false;const first=$("bulk-editor").querySelector("input,select");first.scrollIntoView({block:"center",behavior:matchMedia("(prefers-reduced-motion: reduce)").matches?"instant":"smooth"});first.focus({preventScroll:true});
}
function openInline(key){
  if(running||chatBusy){toast("Đợi phản hồi hiện tại hoặc dừng chờ trước khi sửa.");return;}
  const preview={...criteria,...proposal?.changes};
  if(key==="ages"&&Number(preview.children)===0){toast("Thêm số trẻ em và tuổi cùng lúc ở ô Trẻ em.");return;}
  const button=document.querySelector('[data-inline="'+key+'"]'),row=button.closest(".criteria-row");
  document.querySelectorAll(".inline-editor").forEach(el=>el.remove());
  const editor=document.createElement("form");editor.className="inline-editor";
  const type=key==="date"?"date":["adults","budget","children"].includes(key)?"number":"text";
  editor.innerHTML=choices[key]?'<select aria-label="'+escapeHtml(labels[key])+'">'+choices[key].map(([value,label])=>'<option value="'+escapeHtml(value)+'"'+(preview[key]===value?' selected':'')+'>'+escapeHtml(label)+'</option>').join("")+'</select>':'<input aria-label="'+escapeHtml(labels[key])+'" type="'+type+'" value="'+escapeHtml(preview[key])+'">';
  editor.innerHTML+='<button class="btn" type="submit">Sửa</button><button class="text-action" data-inline-cancel type="button">Hủy</button>';
  if(key==="children"){const ages=document.createElement("input");ages.setAttribute("aria-label","Tuổi từng trẻ, cách nhau bằng dấu phẩy");ages.placeholder="Tuổi: 6, 10";ages.value=preview.ages;ages.dataset.childAges="true";editor.prepend(ages);editor.classList.add("children-editor");}
  row.append(editor);editor.querySelector("input,select").focus();
  editor.addEventListener("submit",event=>{event.preventDefault();const field=editor.querySelector("input:not([data-child-ages]),select"),value=field.value.trim();const changes={[key]:value};if(key==="children")changes.ages=Number(value)>0?editor.querySelector("[data-child-ages]").value.trim():"";const errors=validation({...preview,...changes});const relatedError=errors[key]||(key==="children"?errors.ages:null);if(relatedError){toast(relatedError);return;}if(Object.entries(changes).every(([name,next])=>preview[name]===next)){editor.remove();button.focus();return;}editor.remove();propose(changes);});
  editor.querySelector("[data-inline-cancel]").addEventListener("click",()=>{editor.remove();button.focus();});
}
function lockChat(locked){chatBusy=locked;$("results-chat-form").querySelector("button").disabled=locked;document.querySelectorAll("[data-chat]").forEach(el=>el.disabled=locked);renderCriteria();}
function searchCurrent(){
  if(running||chatBusy)return;
  if(proposal){addMessage("assistant","Xác nhận sửa hoặc chọn Giữ nguyên trước khi tìm kiếm nhé.");focusConfirmation();return;}
  const changed=resultRevision!==currentRevision;startRun(0,{scenario:changed?"standard":state.scenario,reference:Boolean(criteria.url)||(!changed&&state.reference)});
}
function replyToChat(raw){
  if(chatBusy||running){toast("Đợi phản hồi hiện tại hoặc dừng chờ để tiếp tục.");return;}
  const text=raw.trim();if(!text)return;
  window.PrototypeDemo?.message();
  addMessage("user",text);$("results-chat-message").value="";
  const placeholder=addMessage("assistant","Đang chuẩn bị phản hồi mẫu…"),generation=++chatGeneration;lockChat(true);
  setTimeout(()=>{
    placeholder.remove();if(generation!==chatGeneration)return;lockChat(false);
    const lower=text.toLocaleLowerCase("vi-VN");
    const requestsSearch=/(tìm kiếm|tìm tour|tìm lại|chạy tìm|bắt đầu tìm)/.test(lower)&&!/(cách|thế nào|làm sao)/.test(lower);
    const changes={};
    if(/(đổi|sửa|tăng|giảm|chỉnh).*(ngân sách|giá)|ngân sách.*\d/.test(lower)){
      if(/(thêm|bớt|tăng thêm|giảm đi)/.test(lower)||(/(tăng|giảm)/.test(lower)&&!/(thành|lên|xuống còn)/.test(lower))){addMessage("assistant","Bạn muốn ngân sách cuối là bao nhiêu triệu VND / người lớn? Prototype cần số tuyệt đối, ví dụ “đổi ngân sách thành 37 triệu”.");return;}
      const found=lower.match(/(\d+(?:[.,]\d+)?)\s*(triệu|tr\b)/);
      if(!found){addMessage("assistant","Bạn muốn ngân sách bao nhiêu triệu VND / người lớn? Ví dụ: “đổi ngân sách thành 32 triệu”.");return;}
      const value=String(Math.round(Number(found[1].replace(",","."))*1000000));
      changes.budget=value;
    }
    if(/(đổi|sửa|chỉnh).*(ngày|thời lượng)/.test(lower)){
      const found=lower.match(/\b([56])\s*ngày/);if(found)changes.duration=found[1];
      else if(!/\d{1,2}\/\d{1,2}\/\d{4}/.test(lower)){addMessage("assistant","Trong mẫu, bạn có thể đổi thành 5 hoặc 6 ngày; chọn trực tiếp ngày khởi hành ở bảng yêu cầu.");return;}
    }
    if(/(không|bỏ).*(mua sắm|shopping)/.test(lower))changes.shopping="none";
    if(/ít.*(mua sắm|shopping)/.test(lower))changes.shopping="few";
    const hotel=lower.match(/khách sạn[^\d]*([345])\s*sao/);if(hotel)changes.hotel=hotel[1];
    const adults=lower.match(/\b(\d+)\s*người lớn/);if(adults&&/(đổi|sửa|chỉnh|thành|cho|đoàn)/.test(lower))changes.adults=adults[1];
    const date=lower.match(/(?:khởi hành|ngày đi|ngày dự kiến)[^\d]*(\d{1,2})\/(\d{1,2})\/(\d{4})/);if(date)changes.date=date[3]+"-"+date[2].padStart(2,"0")+"-"+date[1].padStart(2,"0");
    if(Object.keys(changes).length){
      const errors=validation({...criteria,...proposal?.changes,...changes});if(Object.keys(errors).length){addMessage("assistant",Object.values(errors).join(" ")+" Chưa áp dụng thay đổi nào.");return;}
      addMessage("assistant","Tôi đã gom các thay đổi vào cùng bản nháp. Sửa thêm hoặc xác nhận cả nhóm bên dưới; yêu cầu đã xác nhận vẫn được giữ.");propose(changes,requestsSearch);return;
    }
    if(/^(hủy|bỏ).*(thay đổi|bản nháp)|^giữ nguyên/.test(lower)){rejectProposal();return;}
    if(/(nhóm khác|phương án khác|tour khác)/.test(lower)){
      if(proposal){addMessage("assistant","Xác nhận sửa hoặc Giữ nguyên trước khi lấy nhóm khác nhé.");focusConfirmation();return;}
      if(state.round===1||state.scenario==="empty"){addMessage("assistant","Bộ mẫu chưa còn nhóm mới. Nhóm hiện tại được giữ lại; bạn có thể điều chỉnh yêu cầu.");return;}
      addMessage("assistant","Tôi đang lấy nhóm minh họa thứ hai, giữ nguyên yêu cầu và loại các tour đã xem.");startRun(1);return;
    }
    if(requestsSearch){addMessage("assistant","Tôi bắt đầu tìm theo yêu cầu bạn đã xác nhận.");searchCurrent();return;}
    if(/(giá|rẻ|chi phí|so sánh)/.test(lower)){
      const selected=selectedTours();if(!hasResults||selected.length<2){addMessage("assistant","Chưa có ít nhất hai tour để so chênh lệch. Có thể kiểm tra nguồn của tour đang có.");return;}
      const [a,b]=selected;addMessage("assistant",'<p>'+escapeHtml(b.name)+' có giá công bố thấp hơn '+money(a.price-b.price)+' / người lớn so với '+escapeHtml(a.name)+'. Đổi lại là 6 ngày và điểm mua sắm.</p><button type="button" class="text-action" data-source="'+b.id+'.price">Xem giá & nguồn '+icon("source")+'</button><p>Phản hồi theo lượt kết quả đang xem; chưa phải tổng nhóm đủ phụ thu.</p>',true);return;
    }
    if(/(hủy|chính sách|phụ thu|nguồn)/.test(lower)){const tour=selectedTours()[2]||selectedTours()[0];if(!tour){addMessage("assistant","Chưa có tour để kiểm tra chính sách.");return;}addMessage("assistant",'<p>Một số tour thiếu chính sách hủy hoặc phụ thu. Chưa đủ căn cứ để kết luận chi phí cuối.</p><button class="text-action" type="button" data-source="'+tour.id+'.cancel">Kiểm tra chính sách '+icon("source")+'</button>',true);return;}
    addMessage("assistant","Bạn có thể nhắn “đổi ngân sách thành 32 triệu và thời lượng thành 6 ngày”, sửa khách sạn/mua sắm, hỏi về giá hoặc yêu cầu nhóm khác. Lưu ý riêng có thể sửa trực tiếp. Chat hiện nhận câu mẫu.");
  },700);
}
function cancelTimers(){runTimers.forEach(clearTimeout);runTimers=[];activeRun++;}
function stopRun(showNotice=true){
  if(running)window.PrototypeDemo?.finishRun("cancelled");
  cancelTimers();running=false;$("screen-results").dataset.busy="false";$("processing-panel").hidden=true;lockChat(false);$("simulate-run").disabled=false;
  if(showNotice){$("run-error").innerHTML='Đã dừng chờ mô phỏng. '+(hasResults?'Kết quả trước được giữ lại. ':'Chưa có kết quả mới. ')+'<button class="text-action" type="button" data-run-retry>Tiếp tục xử lý '+icon("refresh")+'</button>';$("run-error").hidden=false;}
  renderCriteria();
}
function startRun(nextRound=state.round,options={}){
  if(proposal){focusConfirmation();toast("Xác nhận sửa hoặc Giữ nguyên trước khi tìm kiếm.");return;}
  cancelTimers();const runId=activeRun,revision=currentRevision,submitted={...criteria},scenario=options.scenario||state.scenario,reference=options.reference??state.reference;
  lastRunRequest={nextRound,options:{scenario,reference}};
  running=true;clearProposal();chatGeneration++;lockChat(true);$("simulate-run").disabled=true;
  window.PrototypeDemo?.startRun();
  $("screen-results").dataset.busy="true";$("processing-panel").hidden=false;$("run-error").hidden=true;$("long-wait").hidden=true;$("results-snapshot").hidden=!hasResults;
  $("activity-log").innerHTML="";renderCriteria();navigate("results");$("processing-title").focus({preventScroll:true});
  const mode=$("response-mode").value,slow=mode==="slow",stepMs=slow?2100:900;
  const steps=["Hiểu yêu cầu và kiểm tra dữ kiện đầu vào","Đọc URL tham chiếu và tìm tour từ nguồn mẫu","Chuẩn hóa giá / offer rồi đối chiếu điều kiện","Sắp nhóm, dựng bảng và phân tích có dẫn chứng"];
  steps.forEach((copy,index)=>runTimers.push(setTimeout(()=>{
    if(runId!==activeRun)return;
    window.PrototypeDemo?.stage(index,copy);
    $("activity-log").querySelectorAll("li.active").forEach(el=>{el.classList.remove("active");el.querySelector(".icon").outerHTML=icon("check");});
    const li=document.createElement("li");li.className="active";li.innerHTML=icon("route")+'<span>'+escapeHtml(copy)+'</span><time>+'+(index*stepMs/1000).toFixed(1)+'s</time>';$("activity-log").append(li);
  },index*stepMs)));
  if(slow)runTimers.push(setTimeout(()=>{if(runId===activeRun)$("long-wait").hidden=false;},4200));
  runTimers.push(setTimeout(()=>{
    if(runId!==activeRun||revision!==currentRevision)return;
    running=false;$("screen-results").dataset.busy="false";$("processing-panel").hidden=true;lockChat(false);$("simulate-run").disabled=false;
    if(mode==="error"){
      window.PrototypeDemo?.finishRun("failed");
      $("run-error").innerHTML='<strong>Chưa nhận được kết quả mới.</strong>Mất kết nối trong tình huống mô phỏng. Yêu cầu đã xác nhận vẫn được giữ; '+(hasResults?'bảng bên dưới là lượt kết quả trước. ':'chưa có kết quả để so sánh. ')+'<button class="text-action" type="button" data-run-retry>Thử lại '+icon("refresh")+'</button>';
      $("run-error").hidden=false;renderCriteria();return;
    }
    state.round=nextRound;state.scenario=scenario;state.reference=reference||["url-only","source-error"].includes(scenario);state.offerIndex=0;state.exhausted=false;
    window.PrototypeDemo?.finishRun(scenario==="source-error"?"partial":"succeeded");
    resultCriteria=submitted;resultRevision=revision;hasResults=true;$("results-snapshot").hidden=false;render();
    addMessage("assistant","Đã chuẩn bị kết quả minh họa. Bạn có thể xem nguồn, phân tích hoặc trao đổi thêm.");
    if(activeScreen==="results")$("results-heading").focus({preventScroll:true});
  },stepMs*4));
}
function selectTab(which,focus=false){["facts","analysis"].forEach(name=>{const active=name===which;$(name+"-tab").setAttribute("aria-selected",String(active));$(name+"-tab").tabIndex=active?0:-1;$(name+"-panel").hidden=!active;});if(focus)$(which+"-tab").focus();}
$("needs-form").addEventListener("submit",event=>{
  event.preventDefault();const next=readForm(),errors=validation(next);showFormErrors(errors);if(Object.keys(errors).length)return;
  criteria=next;currentRevision++;clearProposal();startRun(0,{scenario:"standard",reference:Boolean(next.url)});
});
$("need-children").addEventListener("input",event=>{$("child-age-field").hidden=Number(event.target.value)<=0;});
$("notes-form").addEventListener("submit",event=>{event.preventDefault();const message=$("notes-message").value.trim();if(!message)return;window.PrototypeDemo?.message();notes.push(message);const div=document.createElement("div");div.className="chat-message user";div.textContent=message;$("notes-log").append(div);const reply=document.createElement("div");reply.className="chat-message assistant";reply.textContent="Đã thêm vào lưu ý. Bản mẫu chưa tự chuyển ghi chú thành điều kiện.";$("notes-log").append(reply);$("notes-message").value="";$("notes-log").scrollTop=$("notes-log").scrollHeight;});
$("results-chat-form").addEventListener("submit",event=>{event.preventDefault();replyToChat($("results-chat-message").value);});
$("cancel-run").addEventListener("click",()=>stopRun());
$("simulate-run").addEventListener("click",()=>startRun(state.round,{scenario:$("scenario").value,reference:$("include-reference").checked}));
$("search-tours").addEventListener("click",searchCurrent);
$("edit-many").addEventListener("click",openBulk);
$("bulk-editor").addEventListener("submit",event=>{
  event.preventDefault();const changes={},preview={...criteria,...proposal?.changes};
  new FormData(event.target).forEach((value,key)=>{const next=String(value).trim();if(next!==preview[key])changes[key]=next;});
  const errors=validation({...preview,...changes});
  if(Object.keys(errors).length){$("bulk-errors").textContent=Object.values(errors).join(" ");$("bulk-errors").hidden=false;const first=event.target.elements.namedItem(Object.keys(errors)[0]);first?.focus();return;}
  $("bulk-editor").hidden=true;if(Object.keys(changes).length)propose(changes);else toast("Chưa có thay đổi mới. Nhóm đang sửa được giữ lại.");
});
$("facts-tab").addEventListener("click",()=>selectTab("facts"));$("analysis-tab").addEventListener("click",()=>selectTab("analysis"));
document.querySelector(".analysis-tabs").addEventListener("keydown",event=>{if(!["ArrowLeft","ArrowRight","Home","End"].includes(event.key))return;event.preventDefault();selectTab(event.key==="Home"?"facts":event.key==="End"?"analysis":$("facts-tab").getAttribute("aria-selected")==="true"?"analysis":"facts",true);});
document.addEventListener("click",event=>{
  const nav=event.target.closest("[data-nav]");if(nav){event.preventDefault();navigate(nav.dataset.nav);return;}
  if(event.target.closest("[data-demo-fill]")){fillSample();return;}
  const chat=event.target.closest("[data-chat]");if(chat){replyToChat(chat.dataset.chat);return;}
  const inline=event.target.closest("[data-inline]");if(inline){openInline(inline.dataset.inline);return;}
  if(event.target.closest("#reject-change")){rejectProposal();return;}
  if(event.target.closest("#sync-basis")){window.journeyBasis();return;}
  if(event.target.closest("#continue-edit")){openBulk();return;}
  if(event.target.closest("#close-bulk")){$("bulk-editor").hidden=true;$("edit-many").focus();return;}
  const discard=event.target.closest("[data-discard-change]");if(discard&&proposal){const key=discard.dataset.discardChange;propose({[key]:criteria[key]});if(!proposal)$("edit-many").focus();return;}
  if(event.target.closest("#confirm-change")){
    if(!proposal||proposal.revision!==currentRevision){toast("Yêu cầu đã đổi ở nơi khác. Bản nháp được giữ để review; chưa xác nhận.");return;}
    const next={...criteria,...proposal.changes},errors=validation(next);if(Object.keys(errors).length){addMessage("assistant",Object.values(errors).join(" "));return;}
    const shouldSearch=proposal.searchAfterConfirm;
    criteria=next;notes=criteria.notes?[criteria.notes]:[];currentRevision++;clearProposal();$("bulk-editor").hidden=true;chatGeneration++;lockChat(false);syncForm();renderCriteria();addMessage("assistant",shouldSearch?"Đã xác nhận toàn bộ thay đổi. Tôi bắt đầu tìm kiếm theo lời nhắn của bạn.":"Đã xác nhận toàn bộ thay đổi. Bấm Tìm kiếm hoặc nhắn “tìm kiếm đi” để cập nhật kết quả.");
    if(shouldSearch)searchCurrent();else{$("search-tours").scrollIntoView({block:"center",behavior:matchMedia("(prefers-reduced-motion: reduce)").matches?"instant":"smooth"});$("search-tours").focus({preventScroll:true});}return;
  }
  if(event.target.closest("[data-run-retry]")){$("response-mode").value="normal";startRun(lastRunRequest?.nextRound??state.round,lastRunRequest?.options||{});return;}
  const locate=event.target.closest("[data-location]");if(locate){
    locate.disabled=true;$("location-copy").textContent="Đang mô phỏng xác định vị trí…";$("weather-copy").textContent="Đang tải thời tiết mẫu…";
    setTimeout(()=>{$("location-copy").textContent="TP.HCM · Vị trí minh họa";$("weather-copy").textContent="29°C · Có mây · Thời tiết minh họa";locate.disabled=false;toast("Widget mô phỏng; nơi khởi hành chưa tự thay đổi.");},1100);return;
  }
  if(event.target.closest("[data-location-denied]")){$("location-copy").textContent="Không cấp quyền vị trí (mô phỏng). Bạn vẫn có thể chọn nơi đi trong form.";return;}
  const walkthrough=event.target.closest("[data-walkthrough]");if(walkthrough){
    walkthrough.disabled=true;const scenes=["Điền điểm đến, ngày và ngân sách của bạn.","Hệ thống đối chiếu tour, giá và dữ kiện còn thiếu.","Xem bảng, mở nguồn và trao đổi qua chat để điều chỉnh."];
    scenes.forEach((copy,index)=>setTimeout(()=>{$("walkthrough-scene").textContent=(index+1)+" / 3 · "+copy;},index*1600));setTimeout(()=>walkthrough.disabled=false,4800);
  }
});
window.addEventListener("popstate",()=>navigate(location.hash.slice(1)||"home",false));
window.addEventListener("pagehide",()=>{if(running)stopRun(false);});
window.journeyBasis=()=>showDialog("Căn cứ của lượt đang xem",'<p class="dialog-context">Theo yêu cầu đã dùng cho lượt kết quả này · Fixture minh họa</p><dl class="evidence-details">'+Object.keys(labels).map(key=>'<div><dt>'+escapeHtml(labels[key])+'</dt><dd>'+escapeHtml(state.scenario==="url-only"?(key==="destination"?"Nhật Bản từ URL":"Chưa chỉ định"):displayValue(key,resultCriteria?.[key]))+'</dd></div>').join("")+'</dl><p class="dialog-note">Tour và thứ tự cố định để review bố cục. Bộ mẫu chưa lọc hoặc xếp hạng theo thay đổi nhu cầu; không kết luận đã đáp ứng mọi ràng buộc.</p>',"YÊU CẦU ĐÃ DÙNG");
document.addEventListener("input",event=>{if(event.target.matches("[data-preference]"))updateSlider(event.target);});
document.addEventListener("change",event=>{const input=event.target;if(!input.matches('[data-preference][data-scope="results"]'))return;const key=input.dataset.preference;if(input.value!==(proposal?.changes[key]??criteria[key]))propose({[key]:input.value});});
$("contact-form").addEventListener("submit",event=>{
  event.preventDefault();const value=$("contact-message").value.trim();if(!value){$("contact-message").focus();return;}
  const ticket=window.PrototypeDemo?.contact({category:$("contact-category").value,message:value,reply_to:$("contact-email").value.trim()||null});
  $("contact-response").textContent="Đã tạo liên hệ mẫu "+(ticket?.id||"")+". Mở trang quản trị cùng tab để xem và xử lý; chưa gửi ra ngoài.";$("contact-response").hidden=false;event.target.reset();
});
$("form-preferences").innerHTML=sliderMarkup("need-",sampleCriteria);
refreshExtras();hydrateIcons();
if(new URLSearchParams(location.search).get("demo")==="results"){
  syncForm();currentRevision=1;resultRevision=1;resultCriteria={...criteria};hasResults=true;$("results-snapshot").hidden=false;render();navigate("results",false);
}else navigate(location.hash.slice(1)||"home",false);
