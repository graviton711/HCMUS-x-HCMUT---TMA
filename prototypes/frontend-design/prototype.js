"use strict";
// Fixed visual-review fixtures, not API DTOs, retrieval or frontend ranking.
const iconPaths = {
  arrow:'<path d="M4 12h15m-6-6 6 6-6 6"/>',
  left:'<path d="M20 12H5m6-6-6 6 6 6"/>',
  refresh:'<path d="M20 10a8 8 0 1 0-.7 6M20 4v6h-6"/>',
  info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v.2"/>',
  check:'<path d="m5 12 4 4L19 6"/>',
  warning:'<path d="m12 3 10 18H2L12 3Z" stroke-linejoin="round"/><path d="M12 9v5m0 3v.1"/>',
  calendar:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4m10-4v4M3 10h18m-12 4h3m3 0h3"/>',
  edit:'<path d="m15 4 5 5M5 20l5-1L21 8a2 2 0 0 0-5-5L5 14v6Zm-1 2h18"/>',
  sliders:'<path d="M4 6h8m4 0h4M4 12h3m4 0h9M4 18h10m4 0h2"/><circle cx="14" cy="6" r="2"/><circle cx="9" cy="12" r="2"/><circle cx="16" cy="18" r="2"/>',
  close:'<path d="m6 6 12 12M18 6 6 18"/>',
  horizontal:'<path d="M3 12h18m-4-4 4 4-4 4M7 8l-4 4 4 4"/>',
  source:'<path d="M14 4h6v6m0-6-9 9M10 4H5a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-5"/>',
  balance:'<path d="M12 3v18M6 21h12M4 7h16M6 7l-4 8h8L6 7Zm12 0-4 8h8l-4-8Z"/>',
  leaf:'<path d="M20 3c0 11-4 16-10 16-4 0-6-3-6-6C4 7 10 5 20 3ZM4 21l10-10"/>',
  route:'<circle cx="5" cy="5" r="2"/><circle cx="19" cy="19" r="2"/><path d="M7 5h10a4 4 0 0 1 0 8H7a3 3 0 0 0 0 6h10"/>'
};
const icon = name => '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+(iconPaths[name]||iconPaths.info)+'</svg>';
const escapeHtml = value => String(value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const money = value => new Intl.NumberFormat("vi-VN").format(value)+" ₫";
const tours = {
  a:{id:"a",name:"Tokyo · Fuji · Hakone",provider:"Lữ hành Mẫu A",photo:"fuji.jpg",alt:"Núi Phú Sĩ và chùa Chureito, ảnh minh họa điểm đến",start:"10/11/2026",days:"5 ngày 4 đêm",price:32800000,tag:"Cân bằng các ưu tiên",reason:"5 ngày, không có điểm mua sắm trong lịch trình mẫu.",caution:"Phụ thu phòng đơn chưa được công bố.",route:"Tokyo · Fuji · Hakone",included:"Vé bay khứ hồi, 4 đêm khách sạn, bữa ăn theo lịch trình",shopping:"Không có trong lịch trình công bố",extras:"Phòng đơn chưa công bố",cancel:"Trước 30 ngày: phí 20% giá tour",quality:"Một phần",offers:[{start:"10/11/2026",price:32800000},{start:"17/11/2026",price:34800000}]},
  b:{id:"b",name:"Osaka · Kyoto · Nara",provider:"Lữ hành Mẫu B",photo:"kyoto.jpg",alt:"Cổng torii đỏ tại Kyoto, ảnh minh họa điểm đến",start:"11/11/2026",days:"6 ngày 5 đêm",price:29900000,tag:"Ưu tiên giá công bố",reason:"Giá công bố thấp hơn trong nhóm, nhiều điểm tham quan.",caution:"6 ngày và 2 điểm mua sắm theo lịch trình.",route:"Osaka · Kyoto · Nara",included:"Vé bay khứ hồi, 5 đêm khách sạn, bữa ăn theo lịch trình",shopping:"2 điểm theo lịch trình",extras:"Phòng đơn: 4.200.000 ₫",cancel:"Trước 30 ngày: phí 30% giá tour",quality:"Một phần"},
  c:{id:"c",name:"Tokyo · Fuji · Yokohama",provider:"Lữ hành Mẫu C",photo:"tokyo.jpg",alt:"Phố gần đền Sensō-ji ở Tokyo, ảnh minh họa điểm đến",start:"12/11/2026",days:"5 ngày 4 đêm",price:31200000,tag:"Ưu tiên thời lượng",reason:"5 ngày, giá công bố nằm trong khoảng ưu tiên.",caution:"Chính sách hủy và phụ thu còn thiếu dữ kiện.",route:"Tokyo · Fuji · Yokohama",included:"Vé bay, khách sạn; bữa ăn chưa rõ",shopping:"1 điểm theo lịch trình",extras:null,cancel:null,quality:"Một phần"},
  d:{id:"d",name:"Tokyo · Kamakura · Fuji",provider:"Lữ hành Mẫu D",photo:"tokyo.jpg",alt:"Phố gần đền Sensō-ji ở Tokyo, ảnh minh họa điểm đến",start:"13/11/2026",days:"5 ngày 4 đêm",price:33400000,tag:"Cân bằng các ưu tiên",reason:"5 ngày, không có điểm mua sắm trong lịch trình mẫu.",caution:"Cần xác nhận mức phụ thu phòng đơn.",route:"Tokyo · Kamakura · Fuji",included:"Vé bay khứ hồi, 4 đêm khách sạn, bữa ăn theo lịch trình",shopping:"Không có trong lịch trình công bố",extras:null,cancel:"Trước 30 ngày: phí 20% giá tour",quality:"Một phần"},
  e:{id:"e",name:"Osaka · Kyoto · Kobe",provider:"Lữ hành Mẫu E",photo:"kyoto.jpg",alt:"Cổng torii đỏ tại Kyoto, ảnh minh họa điểm đến",start:"14/11/2026",days:"6 ngày 5 đêm",price:30500000,tag:"Ưu tiên giá công bố",reason:"Giá công bố thấp hơn trong nhóm minh họa mới.",caution:"6 ngày và 1 điểm mua sắm theo lịch trình.",route:"Osaka · Kyoto · Kobe",included:"Vé bay khứ hồi, 5 đêm khách sạn, bữa ăn theo lịch trình",shopping:"1 điểm theo lịch trình",extras:"Phòng đơn: 4.000.000 ₫",cancel:"Trước 30 ngày: phí 25% giá tour",quality:"Một phần"},
  f:{id:"f",name:"Tokyo · Hakone · Nikko",provider:"Lữ hành Mẫu F",photo:"tokyo.jpg",alt:"Phố gần đền Sensō-ji ở Tokyo, ảnh minh họa điểm đến",start:"15/11/2026",days:"5 ngày 4 đêm",price:31900000,tag:"Ưu tiên thời lượng",reason:"5 ngày, giá công bố nằm trong khoảng ưu tiên.",caution:"Chính sách hủy chưa được công bố.",route:"Tokyo · Hakone · Nikko",included:"Vé bay khứ hồi, 4 đêm khách sạn, bữa ăn theo lịch trình",shopping:"1 điểm theo lịch trình",extras:"Phòng đơn: 3.800.000 ₫",cancel:null,quality:"Một phần"},
  ref:{id:"ref",name:"Tokyo · Fuji · Osaka",provider:"Lữ hành Tham chiếu",photo:"fuji.jpg",alt:"Núi Phú Sĩ và chùa Chureito, ảnh minh họa điểm đến",start:"10/11/2026",days:"5 ngày 4 đêm",price:35900000,tag:"Bạn cung cấp",reason:"Tour bạn gửi được giữ để đối chiếu.",caution:"Giá công bố cao hơn khoảng ưu tiên.",route:"Tokyo · Fuji · Osaka",included:"Vé bay, 4 đêm khách sạn; bữa ăn chưa rõ",shopping:null,extras:"Phòng đơn chưa công bố",cancel:"Trước 30 ngày: phí 30% giá tour",quality:"Một phần"}
};
const groups = [["a","b","c"],["d","e","f"]];
const fields = [
  {key:"provider",label:"Nhà cung cấp",hint:"Nhận diện theo nguồn"},
  {key:"price",label:"Giá công bố",hint:"VND / người lớn"},
  {key:"dates",label:"Lịch & thời lượng",hint:"Chưa xác nhận còn chỗ"},
  {key:"route",label:"Lịch trình",hint:"Các điểm đến công bố"},
  {key:"included",label:"Bao gồm",hint:"Theo lịch đang xem"},
  {key:"shopping",label:"Điểm mua sắm",hint:"Ưu tiên của bạn"},
  {key:"extras",label:"Phụ thu",hint:"Ngoài giá công bố"},
  {key:"cancel",label:"Hủy / đổi",hint:"Cần đọc điều kiện"},
  {key:"quality",label:"Dữ liệu & nguồn",hint:"Theo từng dữ kiện"}
];
const state={round:0,scenario:"standard",reference:false,exhausted:false,offerIndex:0};
const $=id=>document.getElementById(id);
const baseContext=document.querySelector(".context-panel").innerHTML;
const defaultNeeds="Tôi muốn đi Nhật Bản từ TP.HCM vào tháng 11/2026, khoảng 5 ngày. Ưu tiên giá công bố khoảng 35 triệu/người lớn trở xuống và ít điểm mua sắm.";
let draftNeeds=defaultNeeds,dialogOpener=null,toastTimer;
const getTour=id=>id==="a" ? {...tours.a,...tours.a.offers[state.offerIndex]} : tours[id];
function fieldValue(tour,key){
  if(tour.id==="ref"&&state.scenario==="source-error") return null;
  if(key==="price") return money(tour.price);
  if(key==="dates") return tour.start+" · "+tour.days;
  if(key==="quality") return tour.quality+" · Nhà cung cấp công bố";
  return tour[key]??null;
}
function hydrateIcons(root=document){root.querySelectorAll("[data-icon]").forEach(el=>{el.innerHTML=icon(el.dataset.icon);});}
function toast(message){
  clearTimeout(toastTimer);$("toast").textContent=message;$("toast").hidden=false;
  toastTimer=setTimeout(()=>{$("toast").hidden=true;},4200);
}
function showDialog(title,content,eyebrow="DỮ KIỆN & NGUỒN"){
  if(!$("detail-dialog").open) dialogOpener=document.activeElement;
  $("dialog-title").textContent=title;$("dialog-eyebrow").textContent=eyebrow;$("dialog-body").innerHTML=content;
  hydrateIcons($("detail-dialog"));
  if(!$("detail-dialog").open) $("detail-dialog").showModal();
  $("close-dialog").focus();
}
function evidence(id,key){
  const tour=getTour(id),field=fields.find(f=>f.key===key),value=fieldValue(tour,key),failed=id==="ref"&&state.scenario==="source-error";
  const quote=value===null ? "Chưa ghi nhận được dữ kiện này trong nguồn minh họa." : key==="quality" ? "Bản mẫu có dữ liệu một phần; nguồn do nhà cung cấp tự công bố." : field.label+": "+value+".";
  const missingNote=failed ? "Nguồn tham chiếu đang được mô phỏng là không đọc được. Bạn vẫn có thể xem các gợi ý tìm thêm." : value===null ? "Không có dữ kiện để kết luận. Thông tin còn thiếu không được coi là đã đáp ứng yêu cầu." : key==="price" ? "Đây là giá công bố cho một người lớn ở lịch đang xem. Chưa có đủ mọi phụ thu để tính tổng cuối cho nhóm." : key==="dates" ? "Có lịch khởi hành công bố chưa có nghĩa tour còn chỗ. Cần xác nhận với nhà cung cấp." : "Dữ kiện do nhà cung cấp công bố. Bản mẫu không có nguồn độc lập để xác nhận lại.";
  showDialog(field.label,
    '<p class="dialog-context">'+escapeHtml(tour.name)+' · '+escapeHtml(tour.provider)+'</p>'+
    '<div class="evidence-value"><small>Giá trị ghi nhận · minh họa</small><strong>'+escapeHtml(value??(failed?"Chưa đọc được nguồn":"Chưa có dữ kiện"))+'</strong></div>'+
    '<dl class="evidence-details"><div><dt>Dữ kiện</dt><dd>'+escapeHtml(value===null?"Chưa có": "Có trong nguồn mẫu")+'</dd></div><div><dt>Độ đầy đủ tour</dt><dd>'+tour.quality+'</dd></div><div><dt>Trạng thái nguồn</dt><dd>'+escapeHtml(value===null?"Chưa có chứng cứ cho dữ kiện này":"Nhà cung cấp công bố")+'</dd></div><div><dt>Xác minh độc lập</dt><dd>Chưa có</dd></div><div><dt>Ghi nhận lúc</dt><dd>'+escapeHtml(value===null?"Chưa có thời điểm":"03/10/2026 · 10:42 (minh họa)")+'</dd></div><div><dt>Lịch đang xem</dt><dd>'+escapeHtml(tour.start)+' · phòng 2 người</dd></div></dl>'+
    '<div class="source-block"><span>Trích đoạn minh họa, không phải nội dung crawl thật</span><blockquote>'+escapeHtml(quote)+'</blockquote><code>https://tour-minh-hoa.example/'+tour.id+'#'+key+'</code><button type="button" class="btn" disabled title="Địa chỉ .example chỉ minh họa, chưa có nguồn thật">Nguồn minh họa '+icon("source")+'</button></div>'+
    '<h3>Giới hạn cần biết</h3><p class="dialog-note">'+escapeHtml(missingNote)+'</p><p class="dialog-note">Thời điểm ghi nhận không tự chứng minh dữ liệu còn mới. Cả hai hướng dùng cùng fixture để review cách trình bày.</p>'+
    (id==="a"&&key==="dates"?'<h3>Thử đổi lịch minh họa</h3><label class="form-field">Lịch / giá đi kèm<select id="offer-picker"><option value="0"'+(state.offerIndex===0?' selected':'')+'>10/11/2026 · 32.800.000 ₫</option><option value="1"'+(state.offerIndex===1?' selected':'')+'>17/11/2026 · 34.800.000 ₫</option></select></label><p class="dialog-note">Control này kiểm tra giá, ngày và nguồn cùng đổi. Đây chưa phải kết quả đánh giá/ranking lại của backend.</p>':"")
  );
}
function rationale(id){
  const tour=getTour(id);
  showDialog(state.scenario==="url-only"?"Vì sao gợi ý tương tự?":"Vì sao có gợi ý này?",
    '<p class="dialog-context">'+escapeHtml(tour.name)+'</p><div class="evidence-value"><small>Cơ sở trong bộ dữ liệu minh họa</small><strong>'+escapeHtml(state.scenario==="url-only"?"Cùng phạm vi Nhật Bản":tour.tag)+'</strong></div>'+
    '<h3>'+(state.scenario==="url-only"?"Dựa trên tour bạn gửi":"Những điểm hợp với ưu tiên")+'</h3><p class="dialog-note">'+escapeHtml(state.scenario==="url-only"?"Tour nằm trong phạm vi Nhật Bản được lấy từ URL tham chiếu. Chưa có nhu cầu cá nhân để kết luận tối ưu cho bạn.":tour.reason)+'</p>'+
    '<h3>Điều cần cân nhắc</h3><p class="dialog-note">'+escapeHtml(tour.caution)+'</p>'+
    '<h3>Kiểm tra dữ kiện</h3><div class="rationale-links">'+["price","dates","shopping","cancel"].map(key=>'<button type="button" class="btn" data-source="'+id+'.'+key+'">'+fields.find(f=>f.key===key).label+' '+icon("source")+'</button>').join("")+'</div>'+
    '<p class="dialog-note">Thứ tự và lý do này là ví dụ thiết kế. Bản mẫu không tính điểm, không tự rank và không xác nhận tour phù hợp khi ràng buộc bắt buộc chưa biết.</p>',"LÝ DO & ĐÁNH ĐỔI");
}
function card(tour,index){
  return '<article class="tour-card" data-tour-id="'+tour.id+'"><div class="tour-photo"><img src="assets/'+tour.photo+'" alt="'+escapeHtml(tour.alt)+'" width="1000" height="667"><span class="photo-caption">Ảnh minh họa</span></div><div class="tour-body">'+
  '<div class="rank-label'+(index===0?' featured':'')+'"><span class="rank-number">0'+(index+1)+'</span><span>'+escapeHtml(state.scenario==="url-only"?"Gợi ý tương tự":tour.tag)+'</span></div>'+
  '<h3>'+escapeHtml(tour.name)+'</h3><p class="tour-provider">'+escapeHtml(tour.provider)+'</p><p class="price">'+money(tour.price)+'</p><p class="price-unit">/ người lớn · chưa đủ mọi phụ thu</p>'+
  '<div class="tour-meta">'+icon("calendar")+'<span>'+tour.start+'</span><span>·</span><span>'+tour.days+'</span></div>'+
  '<ul class="tour-reasons"><li>'+icon("check")+'<span>'+escapeHtml(state.scenario==="url-only"?"Cùng phạm vi Nhật Bản từ tour bạn gửi.":tour.reason)+'</span></li><li class="caution">'+icon("warning")+'<span>'+escapeHtml(tour.caution)+'</span></li></ul>'+
  '<div class="tour-bottom"><button type="button" class="text-action" data-reason="'+tour.id+'">'+(state.scenario==="url-only"?"Cơ sở gợi ý tương tự":"Vì sao có gợi ý này?")+' '+icon("arrow")+'</button></div></div></article>';
}
function comparison(allTours){
  const table=$("compare-table");table.classList.toggle("with-reference",state.reference);
  table.style.minWidth=allTours.length===1?"400px":"";
  table.innerHTML='<caption class="sr-only">So sánh tour theo nhu cầu đã xác nhận, mọi thông tin là minh họa</caption><thead><tr><th scope="col">Tiêu chí<span>'+allTours.length+' tour đối chiếu</span></th>'+
    allTours.map(tour=>'<th scope="col" class="'+(tour.id==="ref"?"table-reference":"")+'"><span class="table-tour-origin">'+(tour.id==="ref"?"Bạn cung cấp":"Gợi ý minh họa")+'</span><span class="table-tour-name">'+escapeHtml(tour.name)+'</span><p class="table-tour-date">'+tour.start+'</p></th>').join("")+'</tr></thead><tbody>'+
    fields.map(field=>'<tr><th scope="row">'+field.label+'<span>'+field.hint+'</span></th>'+
      allTours.map(tour=>{
        const value=fieldValue(tour,field.key);
        return '<td'+(tour.id==="ref"?' class="table-reference"':"")+'><button type="button" class="cell-source" data-source="'+tour.id+'.'+field.key+'" aria-label="Xem nguồn '+escapeHtml(field.label)+' của '+escapeHtml(tour.name)+'"><span class="cell-value">'+
          (value===null?'<span class="missing">'+icon("warning")+(tour.id==="ref"&&state.scenario==="source-error"?"Nguồn đọc lỗi":"Chưa có dữ kiện")+'</span>':
            field.key==="price"?'<strong>'+escapeHtml(value)+'</strong><small>Phòng 2 người · lịch '+tour.start+'</small>':escapeHtml(value))+
          '</span>'+icon("source")+'</button></td>';
      }).join("")+'</tr>').join("")+'</tbody>';
}

function render(){
  const ids=state.scenario==="empty"?[]:groups[state.round].slice(0,state.scenario==="limited"?2:3);
  const selected=ids.map(getTour),allTours=state.reference?[getTour("ref"),...selected]:selected;
  document.querySelector(".page-intro h1").innerHTML=state.scenario==="url-only"?"Những tour tương tự,<br>đặt cạnh tour bạn gửi.":"Chuyến đi hợp với bạn,<br>nhìn rõ từng lựa chọn.";
  document.querySelector(".intro-copy").textContent=state.scenario==="url-only"?"Tìm thêm theo phạm vi tour bạn gửi. Chưa suy ra nhu cầu hoặc sở thích cá nhân.":"Gợi ý theo nhu cầu đã xác nhận. Đối chiếu điểm hợp, điều cần cân nhắc và nguồn phía sau mỗi dữ kiện.";
  $("suggestions-title").textContent=state.scenario==="url-only" ? selected.length+" gợi ý tương tự tour bạn gửi" : selected.length+" tour gợi ý cho bạn";
  $("round-label").textContent="Nhóm 0"+(state.round+1)+" · "+(state.scenario==="url-only"?"Theo phạm vi tour tham chiếu":"Cùng nhu cầu và phạm vi tìm");
  document.querySelector(".context-panel").innerHTML=state.scenario==="url-only"?
    '<h2 class="context-title">'+icon("sliders")+'Phạm vi tìm</h2><div class="requirement-group"><div class="group-label">Từ tour bạn gửi</div><dl><div><dt>Điểm đến tham chiếu</dt><dd>Nhật Bản</dd></div></dl></div><p class="context-note">Chưa có nhu cầu cá nhân. Giá, lịch và đặc điểm tour gửi chưa được coi là ngân sách hoặc sở thích của bạn.</p>':baseContext;
  $("tour-grid").innerHTML=selected.length?selected.map(card).join(""):
    '<div class="empty-state">'+icon("route")+'<h2>Chưa có gợi ý để đối chiếu.</h2><p>Trong tình huống minh họa này, chưa tìm được tour đáp ứng phạm vi đã xác nhận.'+(state.reference?' Tour bạn gửi vẫn được giữ bên dưới.':"")+'</p><button type="button" class="btn" data-edit-needs>Sửa yêu cầu '+icon("edit")+'</button></div>';
  $("tour-grid").classList.toggle("no-tours",!selected.length);
  $("reference-strip").hidden=!state.reference;
  $("reference-strip").innerHTML=!state.reference?"" : state.scenario==="source-error"?
    icon("warning")+'<div class="reference-copy"><p class="reference-label">Bạn cung cấp · URL minh họa</p><p class="reference-title">Tour tham chiếu chưa đọc được</p><p class="reference-hint">Giữ URL và các gợi ý tìm thêm. Chưa đủ dữ kiện để kết luận tour tham chiếu.</p></div><button type="button" class="text-action" data-retry-source>Thử lại nguồn '+icon("refresh")+'</button>':
    '<img src="assets/fuji.jpg" alt="Ảnh minh họa điểm đến của tour tham chiếu" width="51" height="51"><div class="reference-copy"><p class="reference-label">Bạn cung cấp · Tham chiếu để đối chiếu</p><p class="reference-title">'+tours.ref.name+'</p><p class="reference-hint">'+(state.scenario==="url-only"?"Phạm vi Nhật Bản được lấy từ tour này; chưa suy ra ưu tiên cá nhân.":"Giá công bố cao hơn khoảng ưu tiên. Tour vẫn được giữ để bạn xem.")+'</p></div><div class="reference-price">'+money(tours.ref.price)+'<small>/ người lớn · minh họa</small></div>';
  const notice=$("result-notice");
  const noticeCopy=state.exhausted?'<strong>Chưa còn nhóm gợi ý mới trong bộ mẫu.</strong>Nhóm hiện tại được giữ lại. Bạn có thể sửa yêu cầu; bản thật sẽ báo giới hạn nguồn và phạm vi tìm.':
    state.scenario==="limited"?'<strong>Hiện có 2 gợi ý để đối chiếu.</strong>Không thêm tour chưa đủ điều kiện chỉ để lấp đủ ba lựa chọn.':
    state.scenario==="url-only"?'<strong>Đây là gợi ý tương tự, chưa phải tối ưu cá nhân.</strong>Cơ sở là phạm vi Nhật Bản từ tour bạn gửi; bổ sung nhu cầu nếu muốn so theo ưu tiên riêng.':
    state.scenario==="source-error"?'<strong>Một nguồn tham chiếu chưa đọc được.</strong>Các gợi ý tìm thêm vẫn được giữ. Bạn có thể thử lại nguồn tham chiếu.':
    state.offerIndex===1?'<strong>Bạn đang xem lịch khác của gợi ý 01.</strong>Giá, ngày và nguồn trong fixture đã đổi cùng nhau. Thứ tự gợi ý chưa được backend đánh giá lại.':"";
  notice.hidden=!noticeCopy;notice.innerHTML=noticeCopy;
  document.querySelector(".comparison-section").hidden=!allTours.length;
  if(allTours.length) comparison(allTours);
  $("comparison-title").textContent=allTours.length===1?"Thông tin tour bạn gửi.":"Đặt cạnh nhau để thấy rõ.";
  $("column-count").textContent=allTours.length+" tour";
  $("tradeoffs").innerHTML=selected.length>1?
    '<div class="tradeoff-item">'+icon("balance")+'<div><h3>Giá thấp hơn, thời lượng dài hơn</h3><p>'+escapeHtml(selected[1].name)+' có giá công bố thấp hơn gợi ý đầu, đổi lại lịch 6 ngày và có điểm mua sắm.</p><button type="button" class="text-action" data-reason="'+selected[1].id+'">Xem căn cứ '+icon("source")+'</button></div></div>'+
    '<div class="tradeoff-item">'+icon("info")+'<div><h3>'+ (selected.length>2?"Phần chưa biết cũng cần cân nhắc":"Giá chưa phải tổng cuối cho nhóm")+'</h3><p>'+(selected.length>2?escapeHtml(selected[2].name)+" còn thiếu chính sách hủy. Hãy xác nhận trước khi quyết định.":"Các giá thuộc lịch công bố; phụ thu và điều kiện phòng có thể làm thay đổi tổng chi phí.")+'</p><button type="button" class="text-action" data-source="'+(selected[2]?.id||selected[0].id)+'.'+(selected.length>2?"cancel":"price")+'">Xem dữ kiện '+icon("source")+'</button></div></div>':"";
  $("compare-wrap").scrollLeft=0;$("compare-wrap").scrollTop=0;
  $("include-reference").checked=state.reference;$("scenario").value=state.scenario;
  $("coverage-copy").innerHTML=(selected.length?"Đề xuất trong phạm vi nguồn được hỗ trợ.<br>Không khẳng định tốt nhất toàn thị trường.":"Chưa đủ nhiều tour để so sánh đánh đổi.");
  hydrateIcons();
}
function editNeeds(){
  const personalNeedsMissing=state.scenario==="url-only";
  showDialog("Sửa nhu cầu của bạn",
    '<p class="dialog-context">'+(personalNeedsMissing?'Nhật Bản · chỉ có URL tham chiếu':'Nhật Bản · TP.HCM · bản nháp riêng với kết quả hiện tại')+'</p>'+
    '<label class="form-field">Bạn muốn thay đổi điều gì?<textarea id="draft-needs" maxlength="1200" aria-describedby="draft-hint">'+escapeHtml(personalNeedsMissing&&draftNeeds===defaultNeeds?'':draftNeeds)+'</textarea><span class="form-hint" id="draft-hint">Ví dụ: đổi tháng đi, thời lượng hoặc ưu tiên về điểm mua sắm.</span></label>'+
    '<p id="draft-error" class="notice" role="alert" hidden>Nhập nhu cầu để lưu bản nháp.</p>'+
    '<h3>'+(personalNeedsMissing?'Phạm vi dùng cho nhóm hiện tại':'Yêu cầu đã dùng cho nhóm hiện tại')+'</h3><p class="dialog-note">'+escapeHtml(personalNeedsMissing?'Nhật Bản từ tour bạn gửi. Chưa có nhu cầu cá nhân.':defaultNeeds)+'</p>'+
    '<p class="dialog-note">Bản mẫu chỉ thử thao tác sửa và giữ bản nháp. Việc hiểu nhu cầu, review và tìm lại thuộc flow sẽ thiết kế chi tiết sau khi chọn hướng visual.</p>'+
    '<button type="button" class="btn btn-primary" id="save-draft">Lưu bản nháp '+icon("check")+'</button>',"NHU CẦU & PHẠM VI");
}
function showBasis(){
  showDialog(state.scenario==="url-only"?"Cơ sở gợi ý tương tự":"Căn cứ đề xuất",
    '<div class="evidence-value"><small>Cơ sở đang xem</small><strong>'+(state.scenario==="url-only"?"Phạm vi từ URL tham chiếu":"Nhu cầu đã xác nhận")+'</strong></div>'+
    '<h3>'+(state.scenario==="url-only"?"Chưa suy ra sở thích riêng":"Ràng buộc bắt buộc")+'</h3><p class="dialog-note">'+(state.scenario==="url-only"?"Tour bạn gửi gợi ý phạm vi Nhật Bản. Chưa dùng giá hoặc lịch của tour làm điều kiện cá nhân.":"Nhật Bản, xuất phát từ TP.HCM. Thông tin chưa biết không được mặc định là đạt.")+'</p>'+
    '<h3>Ưu tiên và giới hạn</h3><p class="dialog-note">'+(state.scenario==="url-only"?"Các gợi ý ở đây là tương tự trong phạm vi, không có điểm phù hợp cá nhân.":"Khoảng 5 ngày, giá công bố khoảng 35 triệu trở xuống, ít điểm mua sắm. Ưu tiên được dùng để giải thích đánh đổi, không che thông tin thiếu.")+'</p>'+
    '<p class="dialog-note">Nhóm và thứ tự trên prototype là dữ liệu minh họa cố định. Backend sẽ cung cấp ranking, lý do, phạm vi nguồn và policy; bản mẫu không tính điểm hoặc chọn ba phần tử đầu từ API.</p>'+
    '<h3>Tour bạn gửi</h3><p class="dialog-note">Giữ làm tham chiếu khi có URL. Cách đếm ba gợi ý mới cộng tour tham chiếu đang cần review, chưa phải contract đã duyệt.</p>',"LÝ DO & PHẠM VI");
}
function showReadingHelp(){
  showDialog("Đọc kết quả có căn cứ",
    '<h3>01 · Gợi ý, không quyết định thay bạn</h3><p class="dialog-note">Nhìn lý do và đánh đổi của từng tour trước khi quyết định. Có thể yêu cầu nhóm khác hoặc sửa nhu cầu.</p>'+
    '<h3>02 · Giá gắn với một lịch cụ thể</h3><p class="dialog-note">Giá công bố/người lớn, phụ thu, phòng và số người là các dữ kiện khác nhau. Chưa đủ dữ kiện thì chưa kết luận tổng cuối.</p>'+
    '<h3>03 · Mở nguồn ở từng ô</h3><p class="dialog-note">Bấm vào giá, lịch, chính sách hoặc phần còn thiếu để xem trạng thái dữ kiện, nguồn, trích đoạn và giới hạn.</p>'+
    '<h3>04 · Phân biệt các trạng thái</h3><p class="dialog-note">Dữ kiện có hay thiếu khác độ đầy đủ của tour. Nhà cung cấp công bố khác xác minh độc lập. Thời điểm ghi nhận không tự chứng minh dữ liệu còn mới.</p>',"CÁCH ĐỌC KẾT QUẢ");
}
document.addEventListener("click",event=>{
  const source=event.target.closest("[data-source]");
  if(source){const [id,key]=source.dataset.source.split(".");evidence(id,key);return;}
  const reason=event.target.closest("[data-reason]");
  if(reason){rationale(reason.dataset.reason);return;}
  if(event.target.closest("[data-edit-needs]")) editNeeds();
  if(event.target.closest("[data-retry-source]")){
    state.scenario="standard";render();toast("Nguồn đã trở lại trong tình huống minh họa. Không có truy xuất thật.");
  }
  if(event.target.closest("#save-draft")){
    const value=$("draft-needs").value.trim();
    if(!value){$("draft-error").hidden=false;$("draft-needs").setAttribute("aria-invalid","true");$("draft-needs").focus();return;}
    draftNeeds=value;$("draft-notice").hidden=value===defaultNeeds;$("detail-dialog").close();toast("Đã giữ bản nháp. Kết quả hiện tại chưa thay đổi.");
  }
});
$("find-alternatives").addEventListener("click",()=>{
  if(state.round===1||state.scenario==="empty"){state.exhausted=true;render();return;}
  state.round=1;state.offerIndex=0;state.exhausted=false;render();
  toast("Đang xem nhóm 02 minh họa, gồm các tour khác nhóm 01.");
});
$("edit-needs").addEventListener("click",editNeeds);
$("review-draft").addEventListener("click",editNeeds);
$("ranking-reasons").addEventListener("click",showBasis);
$("about-results").addEventListener("click",showReadingHelp);
$("include-reference").addEventListener("change",event=>{state.reference=event.target.checked;if(!state.reference&&["url-only","source-error"].includes(state.scenario)) state.scenario="standard";render();});
$("scenario").addEventListener("change",event=>{state.scenario=event.target.value;state.exhausted=false;if(["url-only","source-error"].includes(state.scenario)) state.reference=true;render();});
$("reset-demo").addEventListener("click",()=>{Object.assign(state,{round:0,scenario:"standard",reference:false,exhausted:false,offerIndex:0});draftNeeds=defaultNeeds;$("draft-notice").hidden=true;render();toast("Đã đặt lại bản mẫu.");});
document.addEventListener("change",event=>{
  if(event.target.id==="offer-picker"){
    state.offerIndex=Number(event.target.value)===1?1:0;render();evidence("a","dates");$("offer-picker").focus();
  }
});
$("close-dialog").addEventListener("click",()=>{$("detail-dialog").close();});
$("detail-dialog").addEventListener("close",()=>{
  let target=dialogOpener;
  if(target&&!target.isConnected){
    target=target.dataset.source?document.querySelector('[data-source="'+target.dataset.source+'"]'):
      target.dataset.reason?document.querySelector('[data-reason="'+target.dataset.reason+'"]'):null;
  }
  (target||$("ranking-reasons")).focus();
});
$("detail-dialog").addEventListener("click",event=>{
  const rect=$("detail-dialog").getBoundingClientRect();
  if(event.target===$("detail-dialog")&&(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom)) $("detail-dialog").close();
});
function scrollTable(direction){
  const column=$("compare-table").querySelector("thead th:nth-child(2)");
  const amount=column?.getBoundingClientRect().width||210;
  $("compare-wrap").scrollBy({left:direction*amount,behavior:matchMedia("(prefers-reduced-motion: reduce)").matches?"instant":"smooth"});
}
$("scroll-left").addEventListener("click",()=>scrollTable(-1));
$("scroll-right").addEventListener("click",()=>scrollTable(1));
render();
