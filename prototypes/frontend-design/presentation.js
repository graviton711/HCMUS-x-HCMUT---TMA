"use strict";
// Shared display preferences for the local prototype. No account or journey state.
window.PrototypePresentation = (() => {
  const key = "di-cung-presentation-v1", root = document.documentElement;
  const textSources = new WeakMap(), attributeSources = new WeakMap();
  const preserve = "[data-preserve],script,style,textarea,code,pre,svg,[contenteditable],blockquote,.chat-message.user,.account-name,.account-avatar,.account-menu>p,[data-sidebar-username],.message-preview,.admin-quote,.tour-provider,#source-title,.google-choice strong";
  const attributes = ["aria-label", "aria-valuetext", "placeholder", "title", "alt", "content"];
  let preferences = {version:1, language:"vi", theme:"light"}, observer, control, scheduled = false;
  const read = value => {
    try {
      const saved = typeof value === "string" ? JSON.parse(value) : value;
      if (saved?.version === 1) return {version:1, language:saved.language === "en" ? "en" : "vi", theme:saved.theme === "dark" ? "dark" : "light"};
    } catch {}
    return {version:1, language:"vi", theme:"light"};
  };
  try { preferences = read(localStorage.getItem(key)); } catch {}
  function applyRoot() {
    root.lang = preferences.language;
    root.dataset.theme = preferences.theme;
    root.style.colorScheme = preferences.theme;
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", preferences.theme === "dark" ? "#1b1f1c" : "#303d32");
  }
  applyRoot(); // This script runs in <head>, before CSS and the first paint.
  const translate = value => preferences.language === "en" ? window.PrototypeEnglish.translate(value) : value;
  const skipped = node => node.parentElement?.closest(preserve);
  function sourceText(node) {
    if (node.nodeType === Node.TEXT_NODE) {
      const saved = textSources.get(node);
      return saved && node.data === saved.last ? saved.source : node.data;
    }
    return [...node.childNodes].map(sourceText).join("");
  }
  function bindText(node) {
    if (skipped(node) || !node.data.trim()) return;
    const previous = textSources.get(node);
    const source = previous && node.data === previous.last ? previous.source : node.data;
    const trimmed = source.trim().replace(/\s+/g," ");
    const translated = translate(trimmed);
    const next = source.replace(source.trim(), translated);
    textSources.set(node, {source, last:next});
    if (node.data !== next) node.data = next;
  }
  function bindAttributes(element) {
    if (element.closest("script,style,svg,[data-preserve]")) return;
    let saved = attributeSources.get(element);
    if (!saved) { saved = {}; attributeSources.set(element, saved); }
    for (const name of attributes) {
      if (!element.hasAttribute(name)) continue;
      const current = element.getAttribute(name), previous = saved[name];
      const source = previous && current === previous.last ? previous.source : current;
      const next = translate(source);
      saved[name] = {source, last:next};
      if (current !== next) element.setAttribute(name,next);
    }
  }
  function refresh() {
    scheduled = false;
    if (!document.body) return;
    observer?.disconnect();
    // Text-only options otherwise derive their value from the translated label.
    document.querySelectorAll("option:not([value])").forEach(option => option.setAttribute("value", sourceText(option)));
    document.querySelectorAll("blockquote").forEach(quote => { quote.lang = "vi"; });
    const walker = document.createTreeWalker(document.documentElement, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) bindText(walker.currentNode);
    document.querySelectorAll("[aria-label],[aria-valuetext],[placeholder],[title],img[alt],meta[name=description]").forEach(bindAttributes);
    updateControl();
    observer?.observe(document.documentElement,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:attributes});
  }
  function schedule() {
    if (scheduled) return;
    scheduled = true;
    queueMicrotask(refresh);
  }
  function set(change, persist = true) {
    preferences = read({...preferences,...change});
    applyRoot();
    if (persist) { try { localStorage.setItem(key, JSON.stringify(preferences)); } catch {} }
    refresh();
    window.dispatchEvent(new CustomEvent("presentation:change",{detail:{...preferences}}));
  }
  const glyphs = {
    sun:'<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/>',
    moon:'<path d="M20.5 14.5A9 9 0 0 1 9.5 3.5a9 9 0 1 0 11 11Z"/>',
    globe:'<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c5 5 5 13 0 18-5-5-5-13 0-18Z"/>'
  };
  const glyph = name => '<svg class="display-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+glyphs[name]+'</svg>';
  function updateControl() {
    if (!control) return;
    const en = preferences.language === "en", dark = preferences.theme === "dark";
    const trigger = control.querySelector(".display-trigger");
    control.querySelector(".display-language").textContent = en ? "ENG" : "VIE";
    control.querySelector(".display-theme-icon").innerHTML = glyph(dark ? "moon" : "sun");
    trigger.setAttribute("aria-label", en ? "Display settings: English, "+(dark?"dark":"light") : "Hiển thị: Tiếng Việt, "+(dark?"tối":"sáng"));
    control.querySelector("#display-title").textContent = en ? "Display" : "Hiển thị";
    control.querySelector("[data-language-label]").textContent = en ? "Language" : "Ngôn ngữ";
    control.querySelector("[data-theme-label]").textContent = en ? "Appearance" : "Giao diện";
    control.querySelector('[data-language="vi"]').setAttribute("aria-pressed",String(!en));
    control.querySelector('[data-language="en"]').setAttribute("aria-pressed",String(en));
    ["light","dark"].forEach(theme => {
      const button = control.querySelector('[data-theme="'+theme+'"]');
      button.setAttribute("aria-pressed",String(preferences.theme === theme));
      button.querySelector("span").textContent = en ? (theme === "dark" ? "Dark" : "Light") : (theme === "dark" ? "Tối" : "Sáng");
    });
  }
  function close(returnFocus = false) {
    if (!control || control.querySelector(".display-panel").hidden) return;
    control.querySelector(".display-panel").hidden = true;
    control.querySelector(".display-trigger").setAttribute("aria-expanded","false");
    if (returnFocus) control.querySelector(".display-trigger").focus({preventScroll:true});
  }
  function mountControl() {
    const account = document.getElementById("account-control");
    let host;
    if (account) {
      host = document.createElement("div");host.className = "header-actions";
      account.before(host);host.append(account);
    } else if (document.querySelector(".review-header")) {
      host = document.createElement("div");host.className = "header-actions";
      document.querySelector(".review-header").append(host);
      host.append(document.querySelector(".review-status"));
    } else if (document.querySelector(".admin-header")) {
      host = document.createElement("div");host.className = "header-actions";
      document.querySelector(".admin-header").append(host);
      host.append(document.querySelector(".admin-role"));
    } else host = document.querySelector(".viewer-controls") || document.querySelector(".source-page .admin-preview .container");
    if (!host) return;
    control = document.createElement("div");control.className = "display-control";control.dataset.preserve = "";
    control.innerHTML = '<button class="display-trigger" type="button" aria-expanded="false" aria-controls="display-panel">'+glyph("globe")+'<span class="display-language">VIE</span><span class="display-theme-icon">'+glyph("sun")+'</span></button><section class="display-panel" id="display-panel" aria-labelledby="display-title" hidden><h2 id="display-title">Hiển thị</h2><div role="group" aria-labelledby="display-language-label"><p id="display-language-label" data-language-label>Ngôn ngữ</p><div class="display-choices"><button type="button" data-language="vi" lang="vi" aria-pressed="true">Tiếng Việt</button><button type="button" data-language="en" lang="en" aria-pressed="false">English</button></div></div><div role="group" aria-labelledby="display-theme-label"><p id="display-theme-label" data-theme-label>Giao diện</p><div class="display-choices"><button type="button" data-theme="light" aria-pressed="true">'+glyph("sun")+'<span>Sáng</span></button><button type="button" data-theme="dark" aria-pressed="false">'+glyph("moon")+'<span>Tối</span></button></div></div></section>';
    host.append(control);
    control.addEventListener("click", event => {
      const button = event.target.closest("button");if (!button) return;
      if (button.classList.contains("display-trigger")) {
        const panel = control.querySelector(".display-panel"), opening = panel.hidden;
        panel.hidden = !opening;button.setAttribute("aria-expanded",String(opening));
        if (opening) control.querySelector('[data-language="'+preferences.language+'"]').focus({preventScroll:true});
      } else if (button.dataset.language) set({language:button.dataset.language});
      else if (button.dataset.theme) set({theme:button.dataset.theme});
    });
    document.addEventListener("pointerdown",event => {if (!control.contains(event.target)) close();});
    document.addEventListener("focusin",event => {if (!control.contains(event.target)) close();});
    document.addEventListener("keydown",event => {if (event.key === "Escape" && !control.querySelector(".display-panel").hidden) {event.preventDefault();close(true);}});
  }
  document.addEventListener("DOMContentLoaded", () => {
    applyRoot();
    mountControl();
    observer = new MutationObserver(schedule);
    refresh();
  });
  window.addEventListener("storage",event => {
    if (event.key === key || event.key === null) set(read(event.newValue),false);
  });
  return Object.freeze({get preferences(){return {...preferences};}, set, sourceText, prompt:translate,
    chatInput:value => window.PrototypeEnglish.chatInput(value), refresh});
})();
