const CACHE="quantbist-rsi-macd-st-v2";
const SHELL=["./","./index.html","./manifest.json","./icon-192.png","./icon-512.png","./signals.json"];
self.addEventListener("install",event=>{event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(SHELL)));self.skipWaiting()});
self.addEventListener("activate",event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key!==CACHE).map(key=>caches.delete(key)))).then(()=>self.clients.claim()))});
self.addEventListener("fetch",event=>{
  const request=event.request,url=new URL(request.url);
  if(request.method!=="GET"||url.origin!==self.location.origin)return;
  const signalsUrl=new URL("./signals.json",self.registration.scope);
  if(url.pathname.endsWith("signals.json")){
    event.respondWith(fetch(request).then(response=>response.ok?caches.open(CACHE).then(cache=>cache.put(signalsUrl,response.clone()).then(()=>response)):response).catch(()=>caches.match(signalsUrl)));
    return;
  }
  event.respondWith(fetch(request).then(response=>response.ok?caches.open(CACHE).then(cache=>cache.put(request,response.clone()).then(()=>response)):response).catch(()=>caches.match(request,{ignoreSearch:true})));
});
