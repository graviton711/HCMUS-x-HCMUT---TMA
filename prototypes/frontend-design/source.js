"use strict";
const sourceParams=new URLSearchParams(location.search),sourceTour=tours[sourceParams.get("tour")]||tours.a;
const sourceOffer=sourceTour.id==="a"&&sourceParams.get("offer")==="1"?sourceTour.offers[1]:sourceTour.offers?.[0];
const sourceRecord={...sourceTour,...sourceOffer};
document.getElementById("source-title").textContent=sourceRecord.name;
document.getElementById("source-offer").textContent=sourceRecord.provider+" · "+sourceRecord.start+" · Ghi nhận 03/10/2026 10:42 (minh họa)";
for(const field of fields){
  const section=document.createElement("section");section.className="source-section";section.id="field-"+field.key;
  const heading=document.createElement("h2");heading.textContent=field.label;
  const quote=document.createElement("blockquote");
  const value=field.key==="price"?new Intl.NumberFormat("vi-VN").format(sourceRecord.price)+" ₫":field.key==="dates"?sourceRecord.start+" · "+sourceRecord.days:field.key==="quality"?sourceRecord.quality+" · Nhà cung cấp công bố":sourceRecord[field.key];
  quote.textContent=value==null?"Chưa ghi nhận được dữ kiện này trong nguồn minh họa.":field.label+": "+value+".";
  const note=document.createElement("p");note.textContent="Trích đoạn mô phỏng · "+field.hint+" · Chưa xác minh độc lập.";
  section.append(heading,quote,note);document.getElementById("source-sections").append(section);
}
requestAnimationFrame(()=>{if(location.hash.startsWith("#field-"))document.getElementById(location.hash.slice(1))?.scrollIntoView({block:"start"});});
