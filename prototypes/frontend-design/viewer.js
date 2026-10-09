"use strict";
const params=new URLSearchParams(location.search);
const viewport=document.getElementById("viewport-choice");
viewport.value=params.get("viewport")==="mobile"?"mobile":"desktop";
function updateViewer(){
  const path="paper.html";
  if(document.getElementById("prototype-frame").getAttribute("src")!==path) document.getElementById("prototype-frame").src=path;
  document.getElementById("device-frame").classList.toggle("mobile",viewport.value==="mobile");
  document.getElementById("open-direct").href=path;
  document.getElementById("prototype-frame").title="Prototype hiện hành · Giấy & Mực";
  history.replaceState(null,"","?viewport="+viewport.value);
}
viewport.addEventListener("change",updateViewer);updateViewer();
