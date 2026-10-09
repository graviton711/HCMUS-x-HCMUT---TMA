"use strict";
// Local UI experiment: synthetic identities, no passwords, OAuth, tokens or API calls.
window.PrototypeWorkspace=(()=>{
  const storeKey="di-cung-workspace-20261008-v1",authKey="di-cung-demo-profile",journey=window.PrototypeJourney;
  const clone=value=>JSON.parse(JSON.stringify(value)),stamp=()=>new Date().toISOString();
  const uid=()=>"demo_"+(globalThis.crypto?.randomUUID?.()||Date.now()+"_"+Math.random().toString(36).slice(2));
  const statuses={running:"Đang tìm",paused:"Đang tạm dừng",succeeded:"Có kết quả",partial:"Một phần nguồn",failed:"Chưa thành công",cancelled:"Đã dừng"};
  let userId=null,activeId=null,restoring=false,saveTimer,storageOkay=true,authMode="login",authIntent="tours",authGeneration=0,roundsOpen=false,query="",dialogOpener=null,dialogSessionId=null;
  const searchText=value=>String(value).toLocaleLowerCase("vi-VN").normalize("NFD").replace(/[\u0300-\u036f]/g,"").replace(/đ/g,"d").trim();
  const dateFormat=new Intl.DateTimeFormat("vi-VN",{timeZone:"Asia/Ho_Chi_Minh",day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"});
  const day=value=>new Intl.DateTimeFormat("en-CA",{timeZone:"Asia/Ho_Chi_Minh",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date(value));
  Object.assign(iconPaths,{
    sidebar:'<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16m-3-11h0m0 4h0"/>',
    down:'<path d="m6 9 6 6 6-6"/>',
    history:'<path d="M3 11a9 9 0 1 1 3 7M3 4v7h7m2-4v5l3 2"/>',
    user:'<circle cx="12" cy="8" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/>',
    plus:'<path d="M12 5v14M5 12h14"/>',
    more:'<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
    pin:'<path d="m8 4 8 0-1 6 3 3v2H6v-2l3-3-1-6m4 11v6"/>',
    trash:'<path d="M4 6h16M9 3h6m-9 3 1 15h10l1-15M10 10v7m4-7v7"/>',
    eye:'<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
    logout:'<path d="M10 4H4v16h6m3-12 4 4-4 4m-5-4h13"/>',
    download:'<path d="M12 3v12m-4-4 4 4 4-4M4 16v5h16v-5"/>'
  });
  const google='<svg class="google-symbol" viewBox="0 0 24 24" aria-hidden="true"><path fill="#4285F4" d="M21.6 12.2c0-.7-.1-1.4-.2-2.1H12v4h5.4a4.6 4.6 0 0 1-2 3v2.6h3.3c1.9-1.8 2.9-4.4 2.9-7.5Z"/><path fill="#34A853" d="M12 22c2.7 0 5-.9 6.7-2.4l-3.3-2.6c-.9.6-2 .9-3.4.9a6 6 0 0 1-5.6-4.1H3v2.6A10 10 0 0 0 12 22Z"/><path fill="#FBBC05" d="M6.4 13.8a6.1 6.1 0 0 1 0-3.6V7.6H3a10 10 0 0 0 0 8.8l3.4-2.6Z"/><path fill="#EA4335" d="M12 6.1c1.5 0 2.8.5 3.8 1.5l2.9-2.9A9.6 9.6 0 0 0 12 2a10 10 0 0 0-9 5.6l3.4 2.6A6 6 0 0 1 12 6.1Z"/></svg>';
  function makeSession(owner,title,saved=journey.blank(),at=stamp()){return {id:uid(),owner,title,titleIsPlaceholder:title==="Chuyến đi mới",pinned:false,createdAt:at,updatedAt:at,journey:clone(saved),runs:[],viewedRunId:null,pendingRunId:null};}
  function seed(){
    const saved=journey.blank();saved.criteria={...sampleCriteria};saved.formDraft=null;saved.currentRevision=1;saved.resultRevision=1;saved.resultCriteria={...sampleCriteria};saved.hasResults=true;saved.tourScreen="results";
    saved.messages=[{role:"assistant",parts:[{text:"Bạn muốn cân nhắc điều gì cho chuyến đi tiếp theo?"}]},{role:"user",parts:[{text:"Tôi muốn đi Nhật Bản cùng gia đình, ưu tiên ít điểm mua sắm."}]},{role:"assistant",parts:[{text:"Đã chuẩn bị nhóm tour minh họa. Bạn có thể hỏi thêm hoặc sửa yêu cầu trước khi tìm tiếp."}]}];
    const trip=makeSession("profile_phu","Nhật Bản · cùng gia đình",saved,"2026-10-08T02:15:00Z");trip.pinned=true;
    const run={id:uid(),startedAt:trip.createdAt,finishedAt:trip.createdAt,status:"succeeded",criteria:{...sampleCriteria},revision:1,request:{nextRound:0,options:{scenario:"standard",reference:false},mode:"normal"},snapshot:clone(saved)};
    trip.runs.push(run);trip.viewedRunId=run.id;
    const draft=journey.blank();draft.formDraft={...sampleCriteria,budget:"32000000",duration:"6"};draft.notes=["Có người lớn tuổi, muốn đi thong thả."];draft.formDraft.notes=draft.notes[0];draft.noteMessages.push({role:"user",parts:[{text:draft.notes[0]}]});draft.composers.results="Khách sạn nào phù hợp cho gia đình?";
    const pending=makeSession("profile_phu","Nhật Bản · đi thong thả",draft,"2026-10-07T09:30:00Z");
    return {version:1,profiles:[{id:"profile_phu",name:"Minh Phú",username:"minhphu",hasPassword:true,google:null},{id:"profile_lan",name:"Ngọc Lan",username:"ngoclan",hasPassword:false,google:{email:"ngoclan@google.example",identity:"google_demo_lan"}}],sessions:[trip,pending],active:{profile_phu:trip.id}};
  }
  let db;try{db=JSON.parse(localStorage.getItem(storeKey));}catch{storageOkay=false;}
  if(!db||db.version!==1||!Array.isArray(db.profiles)||!Array.isArray(db.sessions)||!db.active)db=seed();
  try{const id=sessionStorage.getItem(authKey);if(db.profiles.some(profile=>profile.id===id))userId=id;}catch{storageOkay=false;}
  const user=()=>db.profiles.find(profile=>profile.id===userId);
  const sessions=()=>db.sessions.filter(session=>session.owner===userId);
  const current=()=>sessions().find(session=>session.id===activeId);
  const initials=name=>name.trim().split(/\s+/).slice(-2).map(part=>part[0]).join("").toLocaleUpperCase("vi-VN");
  function saveDb(){try{localStorage.setItem(storeKey,JSON.stringify(db));storageOkay=true;}catch{storageOkay=false;}saveState();}
  function saveState(){const status=$("session-save-state");status.dataset.failed=String(!storageOkay);status.textContent=storageOkay?"Đã lưu trên trình duyệt này":"Chưa lưu được · giữ tab này mở";}
  function saveCurrent(touch=false){
    clearTimeout(saveTimer);if(restoring||!user())return;
    let session=current();if(!session&&["form","results"].includes(activeScreen)){session=makeSession(userId,"Chuyến đi mới");db.sessions.push(session);activeId=session.id;db.active[userId]=activeId;}
    if(session){session.journey=journey.capture();if(touch)session.updatedAt=stamp();}
    saveDb();renderSidebar();renderToolbar();
  }
  function queueSave(){if(!restoring&&user()){clearTimeout(saveTimer);saveTimer=setTimeout(()=>saveCurrent(true),100);}}
  function pauseAndSave(){journey.pause();saveCurrent();}
  function closeDrawer(){if($("session-drawer").open)$("session-drawer").close();}
  function closeAccountMenu(){const menu=$("account-menu");if(menu){menu.hidden=true;$("account-trigger").setAttribute("aria-expanded","false");}}
  function closeDialog(){if($("workspace-dialog").open)$("workspace-dialog").close();}
  function showWorkspaceDialog(title,content,preserveTitle=false){dialogOpener=document.activeElement;dialogSessionId=dialogOpener?.dataset.optionsSession||dialogOpener?.dataset.renameSession||dialogOpener?.dataset.deleteSession||null;$("workspace-dialog-heading").toggleAttribute("data-preserve",preserveTitle);$("workspace-dialog-heading").textContent=title;$("workspace-dialog-content").innerHTML=content;hydrateIcons($("workspace-dialog"));$("workspace-dialog").showModal();}
  function renderAccountControl(){
    const profile=user();$("account-control").innerHTML=profile?
      '<button class="account-trigger" id="account-trigger" type="button" aria-label="Menu tài khoản '+escapeHtml(profile.name)+'" aria-expanded="false" aria-controls="account-menu"><span class="account-avatar">'+escapeHtml(initials(profile.name))+'</span><span class="account-name">'+escapeHtml(profile.name)+'</span>'+icon("down")+'</button><div class="account-menu" id="account-menu" hidden><p>'+escapeHtml(profile.name)+'<br><span>@'+escapeHtml(profile.username)+'</span></p><button type="button" data-open-account>'+icon("user")+'Tài khoản của tôi</button><button type="button" data-open-workspace>'+icon("history")+'Các phiên tìm tour</button><button type="button" data-logout>'+icon("logout")+'Đăng xuất</button></div>':
      '<button class="account-trigger visitor" type="button" data-login>'+icon("user")+'Đăng nhập</button>';
  }
  function sidebarMarkup(mobile){return '<div class="sidebar-heading"><h2>Chuyến đi của bạn</h2><button class="icon-button" type="button" '+(mobile?'data-close-drawer aria-label="Đóng lịch sử"':'data-collapse-sidebar aria-label="Thu gọn lịch sử"')+'>'+icon(mobile?"close":"sidebar")+'</button></div><button class="btn new-session-button" type="button" data-new-session>'+icon("plus")+'Tìm tour mới</button><label class="session-search">'+icon("search")+'<span class="sr-only">Tìm phiên đã lưu</span><input type="search" data-session-search placeholder="Tìm phiên đã lưu" autocomplete="off"></label><div class="session-list" data-session-list></div><div class="sidebar-foot"><p>Lịch sử riêng của @<span data-sidebar-username></span></p><p>Dữ liệu mẫu · lưu trên trình duyệt này</p><button class="text-action" type="button" data-open-account>'+icon("user")+'Tài khoản của tôi</button></div>';}
  function sessionSubtitle(session){const saved=session.journey||{},last=session.runs.at(-1),c=saved.formDraft||saved.criteria||{};return (last?statuses[last.status]:"Đang điền nhu cầu")+(c.budget?" · "+new Intl.NumberFormat("vi-VN").format(Number(c.budget)/1000000)+" triệu":"")+(saved.proposal?" · có nháp":"");}
  function renderSidebar(){
    if(!user())return;
    const list=sessions().sort((a,b)=>b.updatedAt.localeCompare(a.updatedAt));const terms=searchText(query).split(/\s+/).filter(Boolean);
    const filtered=list.filter(session=>{const text=searchText(session.title+" "+(session.journey.formDraft?.destination||session.journey.criteria?.destination||""));return terms.every(term=>text.includes(term));});
    const today=day(stamp()),yesterday=day(Date.now()-86400000),grouped={"Đã ghim":[],"Hôm nay":[],"Hôm qua":[],"Trước đó":[]};
    filtered.forEach(session=>{const group=session.pinned?"Đã ghim":day(session.updatedAt)===today?"Hôm nay":day(session.updatedAt)===yesterday?"Hôm qua":"Trước đó";grouped[group].push(session);});
    const markup=filtered.length?Object.entries(grouped).filter(([,items])=>items.length).map(([label,items])=>'<div class="session-group-label">'+label+'</div>'+items.map(session=>'<div class="session-row'+(session.id===activeId?' is-current':'')+'"><button class="session-open" type="button" data-open-session="'+escapeHtml(session.id)+'"'+(session.id===activeId?' aria-current="true"':'')+'><strong'+(session.titleIsPlaceholder?'':' data-preserve')+'>'+escapeHtml(session.title)+'</strong><small>'+escapeHtml(sessionSubtitle(session))+'</small></button><button class="session-options" type="button" data-options-session="'+escapeHtml(session.id)+'" aria-label="'+(session.titleIsPlaceholder?'Tùy chọn phiên mới':'Tùy chọn phiên '+escapeHtml(session.title))+'">'+icon("more")+'</button></div>').join("")).join(""):
      '<div class="session-list-empty"><strong>'+(query?"Không tìm thấy phiên":"Chưa có phiên đã lưu")+'</strong><p>'+(query?"Thử tên chuyến đi hoặc điểm đến khác.":"Bắt đầu tìm tour để giữ nhu cầu và cuộc trò chuyện ở đây.")+'</p></div>';
    [$("session-sidebar"),$("mobile-session-sidebar")].forEach((root,index)=>{if(!root.querySelector("[data-session-list]")){root.innerHTML=sidebarMarkup(Boolean(index));root.querySelector("[data-session-search]").value=query;}root.querySelector("[data-session-list]").innerHTML=markup;root.querySelector("[data-sidebar-username]").textContent=user().username;});
  }
  function renderToolbar(){const session=current();$("current-session-title").toggleAttribute("data-preserve",Boolean(session&&!session.titleIsPlaceholder));$("current-session-title").textContent=session?.title||"Chuyến đi mới";$("round-count").textContent="Lượt tìm"+(session?.runs.length?" · "+session.runs.length:"");$("toggle-history").setAttribute("aria-expanded",String(!document.body.classList.contains("sidebar-collapsed")&&innerWidth>1000));if(roundsOpen)renderRounds();saveState();}
  function renderRounds(){
    const session=current();$("round-history").innerHTML='<h2>Các lượt tìm trong phiên</h2><p>Xem lại kết quả cũ giữ nguyên yêu cầu và cuộc trò chuyện hiện tại.</p>'+(session?.runs.length?'<div class="round-list">'+session.runs.map((run,index)=>'<article class="round-row"><div><strong>Lượt tìm '+String(index+1).padStart(2,"0")+' · '+dateFormat.format(new Date(run.startedAt))+'</strong><small>'+escapeHtml(run.criteria.destination||"Phạm vi từ URL")+(run.criteria.budget?' · '+escapeHtml(money(Number(run.criteria.budget)))+' / người lớn':'')+'</small></div><span class="run-status" data-status="'+run.status+'">'+statuses[run.status]+'</span>'+(run.snapshot?'<button class="text-action" type="button" data-view-run="'+escapeHtml(run.id)+'"'+(running?' disabled':'')+'>'+(session.viewedRunId===run.id?'Đang xem':'Xem kết quả')+'</button>':run.status==="paused"&&session.pendingRunId===run.id?'<button class="text-action" type="button" data-resume-run>Tiếp tục</button>':'')+'</article>').reverse().join("")+'</div>':'<p>Chưa có lượt tìm. Nhu cầu và tin nhắn vẫn được lưu trong phiên này.</p>');
  }
  function selectSession(id,writeHistory=true,screen){
    const session=sessions().find(item=>item.id===id);if(!session)return;
    pauseAndSave();closeDrawer();activeId=id;db.active[userId]=id;restoring=true;
    journey.restore(session.journey,screen||session.journey.tourScreen);restoring=false;roundsOpen=false;$("round-history").hidden=true;$("toggle-rounds").setAttribute("aria-expanded","false");
    saveDb();renderSidebar();renderToolbar();if(writeHistory)history.pushState({screen:activeScreen,sessionId:id},"","#"+activeScreen);else history.replaceState({screen:activeScreen,sessionId:id},"","#"+activeScreen);
  }
  function newSession(useSample=false){
    if(!requireLogin(useSample?"sample":"new"))return;
    if(current())pauseAndSave();else{clearTimeout(saveTimer);journey.pause();}closeDrawer();query="";document.querySelectorAll("[data-session-search]").forEach(el=>el.value="");
    const saved=journey.blank();if(useSample)saved.formDraft={...sampleCriteria};const session=makeSession(userId,"Chuyến đi mới",saved);db.sessions.push(session);activeId=session.id;db.active[userId]=activeId;
    restoring=true;journey.restore(saved,"form");restoring=false;roundsOpen=false;$("round-history").hidden=true;$("toggle-rounds").setAttribute("aria-expanded","false");saveDb();renderSidebar();renderToolbar();history.pushState({screen:"form",sessionId:activeId},"","#form");
    if(useSample)toast("Nhu cầu mẫu đã sẵn sàng. Kiểm tra trước khi xác nhận.");
  }
  function openSessionActions(id){const session=sessions().find(item=>item.id===id);if(!session)return;showWorkspaceDialog(session.title,'<div class="session-action-list"><button type="button" data-rename-session="'+escapeHtml(id)+'">'+icon("edit")+'Đổi tên phiên</button><button type="button" data-pin-session="'+escapeHtml(id)+'">'+icon("pin")+(session.pinned?'Bỏ ghim':'Ghim phiên')+'</button><button class="danger-action" type="button" data-delete-session="'+escapeHtml(id)+'">'+icon("trash")+'Xóa phiên</button></div>',!session.titleIsPlaceholder);}
  function renameSession(id){const session=sessions().find(item=>item.id===id);if(!session)return;closeDialog();showWorkspaceDialog("Đổi tên phiên",'<form id="rename-session-form" data-id="'+escapeHtml(id)+'"><label class="journey-field">Tên phiên<input name="title" value="'+escapeHtml(session.title)+'" maxlength="80" required autocomplete="off"></label><div class="dialog-actions"><button class="btn" type="button" data-close-workspace>Hủy</button><button class="btn btn-primary" type="submit">Lưu tên</button></div></form>');}
  function deleteSession(id){const session=sessions().find(item=>item.id===id);if(!session)return;closeDialog();showWorkspaceDialog("Xóa phiên này?",'<p>Phiên <strong'+(session.titleIsPlaceholder?'':' data-preserve')+'>'+escapeHtml(session.title)+'</strong>, nhu cầu, tin nhắn và các lượt tìm của phiên sẽ được xóa khỏi bản mẫu trên trình duyệt này.</p><p>Các phiên khác được giữ.</p><div class="dialog-actions"><button class="btn" type="button" data-close-workspace autofocus>Giữ phiên</button><button class="btn danger-button" type="button" data-confirm-delete="'+escapeHtml(id)+'">Xóa phiên</button></div>');}
  function removeSessions(id){
    pauseAndSave();const removingActive=!id||id===activeId;db.sessions=db.sessions.filter(session=>session.owner!==userId||(id&&session.id!==id));
    closeDialog();if(removingActive){activeId=null;delete db.active[userId];restoring=true;journey.restore(journey.blank(),"form");restoring=false;const next=sessions()[0];if(next)selectSession(next.id,false);}
    saveDb();renderSidebar();renderToolbar();if(activeScreen==="account")renderAccount();toast(id?"Đã xóa phiên mẫu.":"Đã xóa lịch sử mẫu của tài khoản này.");
  }
  function viewRun(id){const session=current(),run=session?.runs.find(item=>item.id===id);if(!run?.snapshot||running)return;saveCurrent();const saved=journey.capture();Object.assign(saved,{fixture:clone(run.snapshot.fixture),resultCriteria:clone(run.criteria),resultRevision:run.revision,hasResults:true,tab:run.snapshot.tab,tourScreen:"results",runNotice:null});restoring=true;journey.restore(saved,"results");restoring=false;session.viewedRunId=run.id;saveCurrent();renderRounds();toast("Đang xem lượt tìm cũ. Yêu cầu hiện tại được giữ.");}
  function handleJourneyChange(event){
    if(restoring||!user())return;
    if(event.detail.kind==="run-start"){
      saveCurrent();const session=current(),{request,criteria:submitted,revision}=event.detail;let run=session.runs.find(item=>item.id===session.pendingRunId&&item.status==="paused"&&item.revision===revision&&JSON.stringify(item.criteria)===JSON.stringify(submitted));
      if(run){run.status="running";run.resumedAt=stamp();}else{run={id:uid(),startedAt:stamp(),status:"running",criteria:clone(submitted),revision,request:clone(request),snapshot:null};session.runs.push(run);}
      session.pendingRunId=run.id;if(session.titleIsPlaceholder===true||(session.titleIsPlaceholder===undefined&&session.title==="Chuyến đi mới")){session.title=(submitted.destination||"Chuyến đi")+" · "+(submitted.date?new Intl.DateTimeFormat("vi-VN",{month:"2-digit",year:"numeric"}).format(new Date(submitted.date+"T12:00:00+07:00")):"theo nhu cầu");session.titleIsPlaceholder=false;}saveCurrent(true);return;
    }
    if(event.detail.kind==="run-end"){
      const session=current(),run=session?.runs.find(item=>item.id===session.pendingRunId);if(run){run.status=event.detail.status;run.finishedAt=stamp();if(["succeeded","partial"].includes(run.status)){run.snapshot=journey.capture();session.viewedRunId=run.id;session.pendingRunId=null;}else if(run.status!=="paused")session.pendingRunId=null;}saveCurrent(true);return;
    }
    queueSave();
  }
  function onNavigate(event){
    const screen=event.detail.screen,work=Boolean(user()&&["form","results"].includes(screen));document.body.classList.toggle("workspace-open",work);document.body.classList.toggle("auth-open",screen==="auth");$("session-sidebar").hidden=!work;$("workspace-toolbar").hidden=!work;$("round-history").hidden=!work||!roundsOpen;
    if(screen!=="auth"){authGeneration++;$("auth-root").querySelectorAll('input[type="password"],input[data-password]').forEach(input=>input.value="");}
    if(work){renderSidebar();renderToolbar();if(!restoring)history.replaceState({screen,sessionId:activeId},"","#"+screen);}if(screen==="account"){renderAccount();$("account-heading").focus({preventScroll:true});}
  }
  function usernameError(value,excludedId){if(!/^[a-z0-9][a-z0-9._-]{2,31}$/.test(value))return "Dùng 3–32 chữ thường, số, dấu chấm, gạch ngang hoặc gạch dưới.";if(db.profiles.some(profile=>profile.id!==excludedId&&profile.username===value))return "Tên tài khoản đã có trong bản mẫu. Chọn tên khác.";return "";}
  function passwordField(id,label,confirm=false){return '<label class="journey-field" for="'+id+'">'+label+'<span class="password-input"><input id="'+id+'" name="'+(confirm?'confirm':'password')+'" type="password" data-password required minlength="8" maxlength="72" autocomplete="'+(authMode==="register"||id.startsWith("account")?'new-password':'current-password')+'" aria-describedby="'+id+'-error"><button type="button" class="password-toggle" data-toggle-password="'+id+'" aria-label="Hiện '+label.toLowerCase()+'" aria-pressed="false">'+icon("eye")+'</button></span><span class="auth-error" id="'+id+'-error" hidden></span></label>';}
  function renderAuth(){
    authGeneration++;const register=authMode==="register";
    $("auth-root").innerHTML='<button class="text-action auth-back" type="button" data-nav="home">'+icon("left")+'Về giới thiệu</button><div class="auth-layout"><aside class="auth-story"><span class="eyebrow">MỘT CHUYẾN ĐI. NHIỀU GÓC NHÌN.</span><h2>Mỗi chuyến đi,<br><em>đều có thể tiếp nối.</em></h2><p>Lưu những điều bạn đã hỏi, những tour đã tìm. Khi trở lại, bạn bắt đầu từ nơi mình dừng.</p><figure><img src="assets/kyoto.jpg" width="1000" height="667" alt="Những cổng torii nối tiếp nhau ở Kyoto, ảnh điểm đến minh họa"><figcaption><span>Kyoto, Nhật Bản</span><span>Ảnh minh họa</span></figcaption></figure></aside><div class="auth-form-panel"><div class="auth-tabs" aria-label="Chọn đăng nhập hoặc đăng ký"><button type="button" data-auth-mode="login" aria-pressed="'+!register+'">Đăng nhập</button><button type="button" data-auth-mode="register" aria-pressed="'+register+'">Tạo tài khoản</button></div><h1 id="auth-heading" tabindex="-1">'+(register?'Chuyến đi của riêng bạn.':'Chào bạn trở lại.')+'</h1><p class="auth-intro">'+(register?'Chỉ cần một vài thông tin để giữ lại những cuộc trò chuyện và lượt tìm tour.':'Đăng nhập để tiếp tục những điều bạn đang cân nhắc cho chuyến đi.')+'</p><button class="google-button" type="button" data-google-login>'+google+'Tiếp tục bằng Google</button><div class="auth-divider">hoặc '+(register?'tạo tài khoản':'đăng nhập bằng tài khoản')+'</div><form id="auth-form" class="auth-form" novalidate>'+(register?'<label class="journey-field" for="auth-name">Họ và tên<input id="auth-name" name="name" autocomplete="name" maxlength="80" placeholder="Ví dụ: Minh Phú" required aria-describedby="auth-name-error"><span class="auth-error" id="auth-name-error" hidden></span></label>':'')+'<label class="journey-field" for="auth-username">Tên tài khoản<input id="auth-username" name="username" autocomplete="username" autocapitalize="none" spellcheck="false" minlength="3" maxlength="32" placeholder="Ví dụ: minhphu" required aria-describedby="auth-username-error"><span class="auth-error" id="auth-username-error" hidden></span></label>'+passwordField("auth-password","Mật khẩu")+(register?passwordField("auth-confirm","Xác nhận mật khẩu",true):'')+'<button class="btn btn-primary auth-submit" type="submit">'+(register?'Tạo tài khoản':'Đăng nhập')+icon("arrow")+'</button><p id="auth-submit-status" class="auth-error" role="status" hidden></p></form><div class="auth-footnote"><strong>Bản mẫu tương tác · Chưa xác thực thật.</strong><br>'+ (register?'Mật khẩu chỉ dùng để thử form, không được lưu. Email có thể liên kết sau trong Tài khoản.':'Tài khoản mẫu: <strong>minhphu</strong>. Dùng mật khẩu thử bất kỳ từ 8 ký tự; không lưu hoặc kiểm tra mật khẩu thật.')+'<button class="text-action demo-login" type="button" data-demo-login>Vào bằng tài khoản mẫu '+icon("arrow")+'</button></div></div></div>';
    hydrateIcons($("auth-root"));
  }
  function authErrors(form,errors){form.querySelectorAll(".auth-error").forEach(el=>{el.hidden=true;el.textContent="";});form.querySelectorAll("input").forEach(el=>el.removeAttribute("aria-invalid"));for(const [name,message] of Object.entries(errors)){const input=form.elements.namedItem(name),error=$(input.id+"-error");input.setAttribute("aria-invalid","true");error.textContent=message;error.hidden=false;}if(Object.keys(errors).length)form.elements.namedItem(Object.keys(errors)[0]).focus();}
  function submitAuth(form){
    if(form.getAttribute("aria-busy")==="true")return;
    const username=form.elements.username.value.trim().toLowerCase(),password=form.elements.password.value,register=authMode==="register",errors={};
    const name=register?form.elements.name.value.trim():"";
    if(register&&name.length<2)errors.name="Nhập họ tên từ 2 ký tự.";
    if(register){const message=usernameError(username);if(message)errors.username=message;}else if(!username)errors.username="Nhập tên tài khoản.";
    const profile=db.profiles.find(item=>item.username===username);if(!register&&username&&!profile)errors.username="Chưa có tài khoản này trong bản mẫu. Bạn có thể tạo tài khoản.";
    if(!register&&profile&&!profile.hasPassword)errors.username="Tài khoản này dùng Google. Chọn Tiếp tục bằng Google.";
    if(password.length<8)errors.password="Dùng mật khẩu thử từ 8 ký tự.";
    if(register&&form.elements.confirm.value!==password)errors.confirm="Mật khẩu xác nhận chưa khớp.";
    authErrors(form,errors);if(Object.keys(errors).length)return;
    const generation=++authGeneration,submit=form.querySelector('[type="submit"]');submit.disabled=true;submit.textContent=register?"Đang tạo tài khoản mẫu…":"Đang đăng nhập mẫu…";form.setAttribute("aria-busy","true");$("auth-root").querySelectorAll("[data-google-login],[data-auth-mode],[data-demo-login]").forEach(el=>el.disabled=true);
    setTimeout(()=>{if(generation!==authGeneration||activeScreen!=="auth")return;let next=profile;if(register){next={id:uid(),name,username,hasPassword:true,google:null};db.profiles.push(next);}form.elements.password.value="";if(register)form.elements.confirm.value="";completeLogin(next.id);},350);
  }
  function requireLogin(intent="tours"){if(user())return true;authIntent=intent;authMode="login";renderAuth();navigate("auth");return false;}
  function allowNavigation(screen){if(["form","results","tours","account"].includes(screen)&&!user())return requireLogin(screen);return true;}
  function completeLogin(id){
    userId=id;activeId=db.active[id]||null;try{sessionStorage.setItem(authKey,id);}catch{storageOkay=false;}saveDb();renderAccountControl();closeDialog();
    const intent=authIntent,session=current();restoring=true;if(session)journey.restore(session.journey,session.journey.tourScreen);else journey.restore(journey.blank(),"form");restoring=false;
    if(intent==="account")navigate("account");else if(["new","form","sample"].includes(intent)||!session)newSession(intent==="sample");else navigate(intent==="results"?"results":tourScreen);
    toast("Đã đăng nhập mẫu. Lịch sử riêng của bạn đã sẵn sàng.");
  }
  function googleChooser(link=false){
    const profile=user(),email=link?profile.username+".review@gmail.example":"ngoclan@google.example";
    showWorkspaceDialog(link?"Liên kết Google mẫu":"Chọn tài khoản Google mẫu",'<p>'+(link?'Chọn email minh họa để thử luồng liên kết với tài khoản đang đăng nhập.':'Chọn tài khoản để thử luồng tiếp tục bằng Google.')+'</p><button class="google-choice" type="button" '+(link?'data-confirm-link':'data-google-profile="profile_lan"')+'><span class="account-avatar">'+escapeHtml(initials(link?profile.name:"Ngọc Lan"))+'</span><span><strong>'+escapeHtml(link?profile.name:"Ngọc Lan")+'</strong><small>'+escapeHtml(email)+'</small></span>'+icon("arrow")+'</button><p class="google-dialog-note">Tài khoản Google/Gmail minh họa, không kết nối Google và không đọc thư. Không nhập thông tin thật.</p><div class="dialog-actions"><button class="btn" type="button" data-close-workspace>Hủy</button></div>');
  }
  function renderAccount(){
    const profile=user();if(!profile)return;
    const count=sessions().length,runCount=sessions().reduce((total,session)=>total+session.runs.length,0);
    $("account-root").innerHTML='<header class="account-heading"><span class="account-avatar">'+escapeHtml(initials(profile.name))+'</span><div><span class="eyebrow">KHÔNG GIAN CỦA BẠN</span><h1 id="account-heading" tabindex="-1">Tài khoản của tôi.</h1><p>Hồ sơ, cách đăng nhập và những chuyến đi đã lưu.</p></div></header><div class="account-layout"><nav class="account-subnav" aria-label="Cài đặt tài khoản"><a href="#account-profile" data-account-anchor="account-profile">'+icon("user")+'Hồ sơ</a><a href="#account-google" data-account-anchor="account-google">'+icon("mail")+'Đăng nhập & liên kết</a><a href="#account-data" data-account-anchor="account-data">'+icon("history")+'Dữ liệu của bạn</a><button class="text-action" type="button" data-open-workspace>'+icon("left")+'Về phiên tìm tour</button></nav><div class="account-content"><section class="account-section" id="account-profile" tabindex="-1"><h2>Thông tin cá nhân</h2><p>Tên hiển thị giúp cuộc trò chuyện gần gũi hơn. Tên tài khoản dùng để đăng nhập.</p><form id="profile-form" class="profile-form" novalidate><div class="profile-fields"><label class="journey-field" for="profile-name">Họ và tên<input id="profile-name" name="name" value="'+escapeHtml(profile.name)+'" maxlength="80" required autocomplete="name" aria-describedby="profile-name-error"><span id="profile-name-error" class="auth-error" hidden></span></label><label class="journey-field" for="profile-username">Tên tài khoản<input id="profile-username" name="username" value="'+escapeHtml(profile.username)+'" minlength="3" maxlength="32" required autocapitalize="none" autocomplete="username" aria-describedby="profile-username-error"><span id="profile-username-error" class="auth-error" hidden></span></label></div><button class="btn btn-primary" type="submit">Lưu thay đổi '+icon("check")+'</button><p id="profile-save-status" class="account-inline-status" role="status" hidden></p></form></section><section class="account-section" id="account-google" tabindex="-1"><h2>Đăng nhập & liên kết</h2><p>Liên kết Google để đăng nhập thuận tiện hơn. Tài khoản tạo bằng tên đăng nhập có thể bổ sung Gmail tại đây.</p><div class="connection-row">'+google+'<div><strong>Google / Gmail</strong><small>'+(profile.google?escapeHtml(profile.google.email):"Chưa liên kết · Tùy chọn")+'</small>'+(profile.google?'<span class="connection-badge">Đã liên kết trong bản mẫu</span>':'')+'</div>'+(profile.google?'<button class="text-action" type="button" data-unlink-google'+(!profile.hasPassword?' disabled':'')+'>Ngắt liên kết</button>':'<button class="btn" type="button" data-link-google>Liên kết Google</button>')+'</div><p class="account-connection-note">Chỉ dùng danh tính và email để đăng nhập, không yêu cầu quyền đọc Gmail. Mọi thao tác liên kết ở bản mẫu đều mô phỏng.</p>'+(!profile.hasPassword?'<form id="add-password-form" class="add-password-form" novalidate><h3>Thêm cách đăng nhập bằng mật khẩu</h3><p>Cần một cách đăng nhập khác trước khi ngắt liên kết Google. Mật khẩu thử không được lưu.</p>'+passwordField("account-password","Mật khẩu mới")+passwordField("account-confirm","Xác nhận mật khẩu",true)+'<button class="btn" type="submit">Thêm mật khẩu mẫu</button></form>':'')+'</section><section class="account-section" id="account-data" tabindex="-1"><h2>Dữ liệu của bạn</h2><p>'+count+' phiên và '+runCount+' lượt tìm trên trình duyệt này. Mỗi tài khoản có lịch sử riêng; bản mẫu chưa đồng bộ sang thiết bị khác.</p><div class="data-action-row"><div><h3>Xuất lịch sử</h3><p>Tải nhu cầu, cuộc trò chuyện và các lượt tìm dưới dạng JSON.</p></div><button class="btn" type="button" data-export-history>'+icon("download")+'Xuất dữ liệu</button></div><div class="data-action-row"><div><h3>Xóa lịch sử tìm tour</h3><p>Xóa tất cả phiên mẫu thuộc tài khoản này.</p></div><button class="text-action danger-action" type="button" data-clear-history'+(!count?' disabled':'')+'>Xóa lịch sử</button></div></section><aside class="account-upcoming"><h2>Có thể bổ sung tiếp</h2><ul><li>Quản lý thiết bị đăng nhập và đăng xuất từ xa.</li><li>Nơi khởi hành, thành viên và ưu tiên mặc định cho chuyến mới.</li><li>Thông báo khi lượt tìm hoàn thành hoặc có dữ kiện mới.</li></ul></aside></div></div>';
    hydrateIcons($("account-root"));
  }
  function logout(){pauseAndSave();try{sessionStorage.removeItem(authKey);}catch{}userId=null;activeId=null;restoring=true;journey.restore(journey.blank(),"home");restoring=false;renderAccountControl();authIntent="tours";authMode="login";renderAuth();navigate("auth");toast("Đã đăng xuất mẫu. Lịch sử được giữ cho lần đăng nhập sau.");}
  function openWorkspace(){closeDrawer();if(!requireLogin("tours"))return;if(current())navigate(tourScreen);else newSession();}
  function exportHistory(){saveCurrent();const payload={prototype:true,exportedAt:stamp(),profile:{name:user().name,username:user().username},sessions:clone(sessions())},url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:"application/json"})),link=document.createElement("a");link.href=url;link.download="di-cung-"+user().username+"-lich-su.json";document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),15000);toast("Đã chuẩn bị tệp lịch sử mẫu để tải xuống.");}
  document.addEventListener("journey:change",handleJourneyChange);document.addEventListener("journey:navigate",onNavigate);document.addEventListener("prototype:render",queueSave);
  document.addEventListener("input",event=>{if(event.target.matches("[data-session-search]")){query=event.target.value;document.querySelectorAll("[data-session-search]").forEach(el=>{if(el!==event.target)el.value=query;});renderSidebar();}else if(event.target.closest("#results-chat-form,#notes-form,#bulk-editor"))queueSave();});
  document.addEventListener("submit",event=>{
    const form=event.target;
    if(form.id==="auth-form"){event.preventDefault();submitAuth(form);return;}
    if(form.id==="rename-session-form"){event.preventDefault();const session=sessions().find(item=>item.id===form.dataset.id),name=form.elements.title.value.trim();if(!session||!name){form.elements.title.focus();return;}session.title=name;session.titleIsPlaceholder=false;session.updatedAt=stamp();closeDialog();saveDb();renderSidebar();renderToolbar();toast("Đã đổi tên phiên.");return;}
    if(form.id==="profile-form"){event.preventDefault();const name=form.elements.name.value.trim(),username=form.elements.username.value.trim().toLowerCase(),errors={};if(name.length<2)errors.name="Nhập họ tên từ 2 ký tự.";const message=usernameError(username,userId);if(message)errors.username=message;authErrors(form,errors);if(Object.keys(errors).length)return;user().name=name;user().username=username;saveDb();renderAccountControl();renderSidebar();$("account-root").querySelector(".account-heading .account-avatar").textContent=initials(name);$("profile-save-status").hidden=false;$("profile-save-status").textContent=storageOkay?"Đã lưu hồ sơ mẫu.":"Chưa lưu được. Giữ tab mở và thử lại.";return;}
    if(form.id==="add-password-form"){event.preventDefault();const errors={};if(form.elements.password.value.length<8)errors.password="Dùng mật khẩu thử từ 8 ký tự.";if(form.elements.confirm.value!==form.elements.password.value)errors.confirm="Mật khẩu xác nhận chưa khớp.";authErrors(form,errors);if(Object.keys(errors).length)return;form.reset();user().hasPassword=true;saveDb();renderAccount();toast("Đã thêm cách đăng nhập mẫu; không lưu mật khẩu.");return;}
    if(form.closest("#main"))queueSave();
  });
  document.addEventListener("click",event=>{
    const target=event.target.closest("button,a");if(!target)return;
    if(target.hasAttribute("data-login")){requireLogin("tours");return;}
    if(target.id==="account-trigger"){const menu=$("account-menu"),open=menu.hidden;menu.hidden=!open;target.setAttribute("aria-expanded",String(open));if(open)menu.querySelector("button").focus();return;}
    if(!target.closest(".account-control")){const menu=$("account-menu");if(menu){menu.hidden=true;$("account-trigger").setAttribute("aria-expanded","false");}}
    if(target.hasAttribute("data-logout")){logout();return;}
    if(target.hasAttribute("data-open-account")){closeAccountMenu();closeDrawer();if(requireLogin("account")){saveCurrent();navigate("account");}return;}
    if(target.hasAttribute("data-open-workspace")){closeAccountMenu();openWorkspace();return;}
    if(target.hasAttribute("data-auth-mode")){authMode=target.dataset.authMode;renderAuth();$("auth-heading").focus({preventScroll:true});return;}
    if(target.hasAttribute("data-demo-login")){completeLogin("profile_phu");return;}
    if(target.hasAttribute("data-toggle-password")){const input=$(target.dataset.togglePassword),show=input.type==="password";input.type=show?"text":"password";target.setAttribute("aria-pressed",String(show));target.setAttribute("aria-label",(show?"Ẩn ":"Hiện ")+input.closest("label").childNodes[0].textContent.toLowerCase());return;}
    if(target.hasAttribute("data-google-login")){googleChooser();return;}
    if(target.hasAttribute("data-google-profile")){completeLogin(target.dataset.googleProfile);return;}
    if(target.hasAttribute("data-link-google")){googleChooser(true);return;}
    if(target.hasAttribute("data-confirm-link")){user().google={email:user().username+".review@gmail.example",identity:"google_demo_"+userId};closeDialog();saveDb();renderAccount();toast("Đã liên kết Google/Gmail mẫu.");return;}
    if(target.hasAttribute("data-unlink-google")){if(!user().hasPassword)return;showWorkspaceDialog("Ngắt liên kết Google?",'<p>Bạn vẫn đăng nhập bằng tên tài khoản và mật khẩu mẫu. Lịch sử tìm tour được giữ.</p><div class="dialog-actions"><button class="btn" type="button" data-close-workspace autofocus>Giữ liên kết</button><button class="btn" type="button" data-confirm-unlink>Ngắt liên kết</button></div>');return;}
    if(target.hasAttribute("data-confirm-unlink")){if(!user().hasPassword)return;user().google=null;closeDialog();saveDb();renderAccount();toast("Đã ngắt liên kết Google mẫu.");return;}
    if(target.hasAttribute("data-account-anchor")){event.preventDefault();$(target.dataset.accountAnchor).scrollIntoView({block:"start",behavior:matchMedia("(prefers-reduced-motion: reduce)").matches?"instant":"smooth"});$(target.dataset.accountAnchor).focus({preventScroll:true});return;}
    if(target.hasAttribute("data-export-history")){exportHistory();return;}
    if(target.hasAttribute("data-clear-history")){showWorkspaceDialog("Xóa toàn bộ lịch sử?",'<p>Tất cả phiên, nhu cầu, tin nhắn và lượt tìm của @'+escapeHtml(user().username)+' sẽ bị xóa khỏi bản mẫu này. Hồ sơ và liên kết Google được giữ.</p><div class="dialog-actions"><button class="btn" type="button" data-close-workspace autofocus>Giữ lịch sử</button><button class="btn danger-button" type="button" data-confirm-clear>Xóa tất cả phiên</button></div>');return;}
    if(target.hasAttribute("data-confirm-clear")){removeSessions();return;}
    if(target.hasAttribute("data-new-session")){newSession();return;}
    if(target.hasAttribute("data-open-session")){selectSession(target.dataset.openSession);return;}
    if(target.hasAttribute("data-options-session")){openSessionActions(target.dataset.optionsSession);return;}
    if(target.hasAttribute("data-rename-session")){renameSession(target.dataset.renameSession);return;}
    if(target.hasAttribute("data-pin-session")){const session=sessions().find(item=>item.id===target.dataset.pinSession);if(session){session.pinned=!session.pinned;closeDialog();saveDb();renderSidebar();toast(session.pinned?"Đã ghim phiên.":"Đã bỏ ghim phiên.");}return;}
    if(target.hasAttribute("data-delete-session")){deleteSession(target.dataset.deleteSession);return;}
    if(target.hasAttribute("data-confirm-delete")){removeSessions(target.dataset.confirmDelete);return;}
    if(target.hasAttribute("data-collapse-sidebar")||target.id==="toggle-history"){if(innerWidth<=1000){renderSidebar();$("session-drawer").showModal();}else document.body.classList.toggle("sidebar-collapsed");renderToolbar();return;}
    if(target.hasAttribute("data-close-drawer")){closeDrawer();return;}
    if(target.hasAttribute("data-close-workspace")){closeDialog();return;}
    if(target.id==="toggle-rounds"){roundsOpen=!roundsOpen;$("round-history").hidden=!roundsOpen;target.setAttribute("aria-expanded",String(roundsOpen));renderRounds();return;}
    if(target.hasAttribute("data-view-run")){viewRun(target.dataset.viewRun);return;}
    if(target.hasAttribute("data-resume-run")){if(proposal){toast("Xác nhận hoặc hủy thay đổi trước khi tiếp tục tìm.");focusConfirmation();return;}$("response-mode").value="normal";startRun(lastRunRequest?.nextRound??state.round,lastRunRequest?.options||{});}
  });
  document.addEventListener("keydown",event=>{if(event.key==="Escape"&&$("account-menu")&&!$("account-menu").hidden){$("account-menu").hidden=true;$("account-trigger").setAttribute("aria-expanded","false");$("account-trigger").focus();}if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==="k"&&document.body.classList.contains("workspace-open")){event.preventDefault();if(innerWidth<=1000){renderSidebar();$("session-drawer").showModal();$("mobile-session-sidebar").querySelector("[data-session-search]").focus();}else{document.body.classList.remove("sidebar-collapsed");$("session-sidebar").querySelector("[data-session-search]").focus();renderToolbar();}}});
  $("workspace-dialog").addEventListener("close",()=>{if($("workspace-dialog").open)return;if(dialogOpener?.isConnected){dialogOpener.focus({preventScroll:true});return;}const root=$("session-drawer").open?$("mobile-session-sidebar"):$("session-sidebar"),sessionAction=dialogSessionId?root.querySelector('[data-options-session="'+dialogSessionId+'"]'):null;if(sessionAction&&sessionAction.getClientRects().length)sessionAction.focus({preventScroll:true});else $(activeScreen+"-heading")?.focus({preventScroll:true});});
  [$("workspace-dialog"),$("session-drawer")].forEach(dialog=>dialog.addEventListener("click",event=>{const rect=dialog.getBoundingClientRect();if(event.target===dialog&&(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom))dialog.close();}));
  window.addEventListener("pagehide",()=>saveCurrent());document.addEventListener("visibilitychange",()=>{if(document.visibilityState==="hidden")saveCurrent();});
  const resize=new ResizeObserver(()=>{document.documentElement.style.setProperty("--header-height",document.querySelector(".site-header").offsetHeight+"px");if(innerWidth>1000)closeDrawer();renderToolbar();});resize.observe(document.querySelector(".site-header"));
  const initialRoute=location.hash.slice(1)||activeScreen||"home";activeId=user()?db.active[userId]||null:null;renderAccountControl();
  if(user()){restoring=true;journey.restore(current()?.journey||journey.blank(),["form","results","tours"].includes(initialRoute)?current()?.journey.tourScreen||"form":"home");restoring=false;navigate(initialRoute==="auth"?tourScreen:initialRoute,false);}
  else if(["form","results","tours","account","auth"].includes(initialRoute)){authIntent=initialRoute==="auth"?"tours":initialRoute;authMode=new URLSearchParams(location.search).get("auth")==="register"?"register":"login";renderAuth();navigate("auth",false);}
  hydrateIcons();saveDb();
  return {requireLogin,allowNavigation,restoreHistory(saved){if(saved?.sessionId&&sessions().some(session=>session.id===saved.sessionId)){selectSession(saved.sessionId,false,saved.screen);return true;}return false;},state:()=>({profile:user()?clone(user()):null,activeId,sessions:clone(sessions()),storageOkay}),storeKey,authKey};
})();
