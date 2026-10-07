"use strict";
// Demo-only state shared across pages in one tab. No tokens or tour/chat content.
window.PrototypeDemo=(()=>{
  const key="di-cung-review-20261007",anchor=Date.parse("2026-10-07T02:30:00Z");
  function seed(){
    const sessions=[
      {id:"session_demo_01",started_at:"2026-10-07T01:20:00Z",last_active_at:"2026-10-07T01:28:00Z",user_message_count:8,comparison_count:2,state:"idle",last_job_status:"succeeded"},
      {id:"session_demo_02",started_at:"2026-10-07T02:00:00Z",last_active_at:"2026-10-07T02:12:00Z",user_message_count:5,comparison_count:1,state:"open",last_job_status:"partial"},
      {id:"session_demo_03",started_at:"2026-10-06T03:10:00Z",last_active_at:"2026-10-06T03:25:00Z",user_message_count:11,comparison_count:3,state:"idle",last_job_status:"succeeded"},
      {id:"session_demo_04",started_at:"2026-10-06T08:20:00Z",last_active_at:"2026-10-06T08:35:00Z",user_message_count:4,comparison_count:1,state:"idle",last_job_status:"failed"},
      {id:"session_demo_05",started_at:"2026-10-05T02:10:00Z",last_active_at:"2026-10-05T02:15:00Z",user_message_count:3,comparison_count:1,state:"expired",last_job_status:"cancelled"}
    ];
    const events=sessions.flatMap(s=>[{id:s.id+"_message",session_id:s.id,kind:"user_message",count:s.user_message_count,at:s.last_active_at,summary:"Tin người dùng · số đếm mẫu"},...Array.from({length:s.comparison_count},(_,i)=>({id:s.id+"_run_"+i,session_id:s.id,kind:"comparison",status:s.last_job_status,at:s.last_active_at,summary:"Lượt tìm mẫu"}))]);
    return {version:1,serial:10,last_ms:anchor,sessions,events,sources:[
      {id:"source_demo_a",version:1,name:"Lữ hành Mẫu A",domain:"supplier-a.example",state:"active",access_status:"approved",health:"ok",checked_at:"2026-10-07T01:00:00Z",last_run_at:"2026-10-07T01:40:00Z",tours:48,offers:73,profile:"sample-a@1",fields:["Giá theo lịch","Ngày khởi hành","Lịch trình","Chính sách hủy"],notes:"Thiếu phụ thu phòng đơn ở một số offer."},
      {id:"source_demo_b",version:1,name:"Lữ hành Mẫu B",domain:"supplier-b.example",state:"paused",access_status:"approved",health:"partial",checked_at:"2026-10-06T03:00:00Z",last_run_at:"2026-10-06T03:20:00Z",tours:36,offers:51,profile:"sample-b@2",fields:["Giá theo lịch","Ngày khởi hành","Điểm mua sắm"],notes:"Đang rà soát các field chính sách còn thiếu."},
      {id:"source_demo_c",version:1,name:"Lữ hành Mẫu C",domain:"supplier-c.example",state:"paused",access_status:"blocked",health:"blocked",checked_at:"2026-10-07T01:10:00Z",last_run_at:null,tours:0,offers:0,profile:"sample-c@1",fields:["Lịch trình"],notes:"Tình huống access bị từ chối. Không được bật nguồn."}
    ],contacts:[
      {id:"contact_demo_01",version:1,category:"data_issue",message:"Giá công bố và phần phụ thu cần được tách rõ hơn trong bảng. (Góp ý mẫu)",reply_to:null,status:"new",created_at:"2026-10-07T01:15:00Z",session_id:"session_demo_01",notes:[]},
      {id:"contact_demo_02",version:1,category:"support",message:"Tôi muốn xem lại các yêu cầu đã xác nhận sau khi hủy chỉnh sửa. (Liên hệ mẫu)",reply_to:"reviewer@user.example",status:"in_progress",created_at:"2026-10-06T04:10:00Z",session_id:"session_demo_03",notes:[{text:"Đã ghi nhận vào review prototype.",at:"2026-10-06T05:00:00Z"}]}
    ],audit:[]};
  }
  let data;try{data=JSON.parse(sessionStorage.getItem(key));}catch{}if(!data||data.version!==1)data=seed();
  function save(){try{sessionStorage.setItem(key,JSON.stringify(data));}catch{}window.dispatchEvent(new CustomEvent("prototype:store"));}
  function stamp(){data.last_ms=Math.max(data.last_ms+1,anchor+Math.floor(performance.now()));return new Date(data.last_ms).toISOString();}
  function next(prefix){return prefix+"_"+(++data.serial);}
  function session(){let s=data.sessions.find(s=>s.id==="session_demo_live");if(!s){const at=stamp();s={id:"session_demo_live",started_at:at,last_active_at:at,user_message_count:0,comparison_count:0,state:"open",last_job_status:null};data.sessions.push(s);}return s;}
  function audit(action,id){data.audit.unshift({id:next("audit"),action,resource_id:id,at:stamp(),actor:"Admin mẫu"});}
  function event(kind,summary,extra={}){const s=session(),at=stamp();s.last_active_at=at;data.events.push({id:next("event"),session_id:s.id,kind,summary,at,...extra});save();}
  return {
    read:()=>JSON.parse(JSON.stringify(data)),
    message(){session().user_message_count++;event("user_message","Tin người dùng đã nhận · không lưu nội dung",{count:1});},
    startRun(){const s=session();s.comparison_count++;s.state="open";s.last_job_status="running";s.run_id=next("run");event("comparison","Bắt đầu lượt tìm minh họa",{run_id:s.run_id,status:"running"});},
    stage(index,summary){event("stage",summary,{stage_index:index});},
    finishRun(status){const s=session();s.last_job_status=status;const run=data.events.find(e=>e.run_id===s.run_id);if(run)run.status=status;event("terminal","Lượt tìm: "+status,{status});},
    contact(input){const s=session(),item={id:next("contact_demo"),version:1,...input,status:"new",created_at:stamp(),session_id:s.id,notes:[]};data.contacts.unshift(item);event("contact","Tạo liên hệ mẫu");return item;},
    updateContact(id,status,note){const item=data.contacts.find(c=>c.id===id);if(!item)return;item.status=status;item.version++;if(note)item.notes.push({text:note,at:stamp()});audit("Cập nhật liên hệ: "+status,id);save();},
    addSource(input){const item={id:next("source_demo"),version:1,...input,state:"draft",access_status:"unchecked",health:"unchecked",checked_at:null,last_run_at:null,tours:0,offers:0,fields:[],notes:"Nguồn mẫu mới cần kiểm tra và duyệt trước khi bật."};data.sources.push(item);audit("Thêm nguồn nháp",item.id);save();return item;},
    editSource(id,name,notes){const s=data.sources.find(s=>s.id===id);if(!s||!name)return;s.name=name;s.notes=notes;s.version++;audit("Sửa tên và ghi chú nguồn",id);save();},
    toggleSource(id){const s=data.sources.find(s=>s.id===id);if(!s||s.access_status!=="approved")return false;s.state=s.state==="active"?"paused":"active";s.version++;audit(s.state==="active"?"Bật nguồn mẫu":"Tạm dừng nguồn mẫu",id);save();return true;},
    checkSource(id){const s=data.sources.find(s=>s.id===id);if(!s)return;s.checked_at=stamp();if(s.access_status!=="blocked"){s.access_status="approved";s.health="ok";if(s.state==="draft")s.state="paused";if(!s.fields.length)s.fields=["Giá theo lịch","Ngày khởi hành","Lịch trình"];s.notes="Đã kiểm tra và duyệt trong tình huống mô phỏng; chưa gọi website thật.";}s.version++;audit("Kiểm tra/duyệt nguồn mô phỏng",id);save();},
    refreshSource(id){const s=data.sources.find(s=>s.id===id);if(!s||s.state!=="active"||s.access_status!=="approved")return false;s.last_run_at=stamp();s.health="ok";s.version++;audit("Làm mới dữ liệu mô phỏng",id);save();return true;},
    reset(){data=seed();save();},
    time:stamp
  };
})();
