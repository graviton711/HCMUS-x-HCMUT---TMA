"use strict";
const params=new URLSearchParams(location.search);
const design=document.getElementById("design-choice"),viewport=document.getElementById("viewport-choice");
design.value=params.get("design")==="coastal"?"coastal":"paper";
viewport.value=params.get("viewport")==="mobile"?"mobile":"desktop";
function updateViewer(){
  const path=design.value==="coastal"?"coastal.html":"paper.html";
  if(document.getElementById("prototype-frame").getAttribute("src")!==path) document.getElementById("prototype-frame").src=path;
  document.getElementById("device-frame").classList.toggle("mobile",viewport.value==="mobile");
  document.getElementById("open-direct").href=path;
  document.getElementById("prototype-frame").title="Prototype "+(design.value==="paper"?"A · Giấy & mực":"B · Hành trình xanh");
  history.replaceState(null,"","?design="+design.value+"&viewport="+viewport.value);
}
design.addEventListener("change",updateViewer);viewport.addEventListener("change",updateViewer);updateViewer();
