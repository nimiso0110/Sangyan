const {JSDOM}=require("jsdom"),fs=require("fs"),B=process.env.BASE||"http://127.0.0.1:8000/";
const ok=(c,m)=>console.log(c?"PASS":"FAIL",m);
JSDOM.fromURL(B,{runScripts:"dangerously",resources:"usable",pretendToBeVisual:true,beforeParse(w){
 w.fetch=(u,o)=>fetch(new URL(u,B),o);w.FormData=FormData;w.HTMLElement.prototype.scrollIntoView=()=>{};w.matchMedia=()=>({matches:false});
 w.URL.createObjectURL=()=>"blob:x";w.print=()=>{w.__printed=1};Object.defineProperty(w.navigator,"clipboard",{value:{writeText:async t=>{w.__copied=t}}})}}).then(async dom=>{
 const w=dom.window,d=w.document,$=s=>d.querySelector(s),all=s=>[...d.querySelectorAll(s)],errs=[],wait=ms=>new Promise(r=>setTimeout(r,ms));
 w.addEventListener("error",e=>errs.push(e.message));await wait(900);
 ok(all("#cards article").length==9,"learn gallery: 9 indicator cards");ok(all(".mode").length==4,"4 input modes");
 for(const lang of ["en","hi","ta"]){$("#lang").value=lang;$("#lang").dispatchEvent(new w.Event("change"));await wait(400);
  const t=[];for(const b of all("#smp button")){b.click();await wait(300);t.push($(".state h2").textContent.slice(0,14)+":"+all("#out .fc").length)}
  ok(!!$(".gauge")&&!!$(".radar")&&all(".radar svg.on").length>=0,`${lang}: gauge+radar | ${t.join(" ; ")}`)}
 $("#lang").value="en";
 // URL mode
 $('[data-m=url]').click();$("#url").value="https://nseindla.com/login";$("#url").dispatchEvent(new w.Event("input"));
 ok(/class="an"/.test($("#live").innerHTML),"live domain anatomy preview while typing");
 $("#go").click();await wait(400);ok($(".state").classList.contains("hi")&&all(".lk .an u").length>0,"URL lookalike => HIGH + anatomy diff");
 $("#url").value="not a link";$("#go").click();await wait(300);ok(/valid link/.test($("#err").textContent),"bad URL => friendly error");
 // Screenshot mode
 $('[data-m=image]').click();const f=new File([fs.readFileSync(__dirname+"/shot.png")],"shot.png",{type:"image/png"});
 Object.defineProperty($("#file"),"files",{value:[f],configurable:true});$("#file").dispatchEvent(new w.Event("change"));ok(!$("#pv").hidden,"screenshot preview shown");
 $("#go").click();await wait(2500);ok(/HIGH/.test($(".state h2").textContent)&&/OCR confidence/.test($("#out").textContent)&&/Text we read/.test($("#out").textContent),"screenshot => OCR => HIGH + confidence + extracted text");
 console.log("   ocr text:",JSON.stringify(all("#out .box").pop().textContent));
 $("#file").dispatchEvent(new w.Event("change"));
 const bad=new File(["x"],"a.gif",{type:"image/gif"});Object.defineProperty($("#file"),"files",{value:[bad],configurable:true});$("#file").dispatchEvent(new w.Event("change"));ok(/PNG, JPEG or WebP/.test($("#err").textContent),"wrong file type rejected in UI");
 // Voice mode
 $('[data-m=voice]').click();$("#mic").click();ok(/not supported/.test($("#err").textContent),"voice: unsupported browser => friendly message");
 class SR{constructor(){SR.last=this}start(){setTimeout(()=>this.onstart&&this.onstart(),0)}stop(){this.onend&&this.onend()}}w.webkitSpeechRecognition=SR;
 $("#mic").click();await wait(50);ok($("#mic").classList.contains("on")&&$("#mic").getAttribute("aria-pressed")=="true","voice: listening state + waveform class");
 SR.last.onresult({results:[Object.assign([{transcript:"Someone says I can double my money"}],{isFinal:false})]});ok(!$("#heard").hidden&&/double/.test($("#heard").textContent),"voice: live interim transcript");
 SR.last.onresult({results:[Object.assign([{transcript:"Someone says I can double my money in one week, send your OTP"}],{isFinal:true})]});await wait(400);
 ok(/HIGH/.test($(".state h2").textContent),"voice: final transcript => analysed => HIGH");SR.last.onend();ok(!$("#mic").classList.contains("on"),"voice: stops cleanly");
 $("#mic").click();await wait(50);SR.last.onerror({error:"not-allowed"});ok(/blocked/.test($("#err").textContent),"voice: mic permission denied => friendly message");
 // Language hint, checklist, copy, print, stats
 $('[data-m=text]').click();$("#text").value="गारंटी के साथ पैसा दोगुना करें, आज ही जुड़ें";$("#lang").value="en";$("#go").click();await wait(400);
 ok(!!$("#sw"),"Hindi text with English output => offers to switch language");$("#sw").click();await wait(500);ok($("#lang").value=="hi"&&/उच्च/.test($(".state h2").textContent),"switch => report in Hindi");
 const c=all(".ck input");c[0].checked=true;c[0].dispatchEvent(new w.Event("change"));ok($("#pgt").textContent.startsWith("1 /"),"checklist progress updates");
 $("#cp").click();await wait(50);ok(/\./.test(w.__copied||""),"copy family alert: "+(w.__copied||"").slice(0,60));$("#pr").click();ok(w.__printed==1,"save as PDF triggers print");
 await wait(300);ok(/Checks so far: \d+/.test($("#sbody").textContent)&&all(".bar").length>=3,"learning panel populated: "+$("#sbody").textContent.slice(0,60));
 ok(all(".hi-item").length>=5,"history lists saved checks: "+all(".hi-item").length);
 ok(!/double my money|OTP|गारंटी/.test(w.localStorage.getItem("scamshield.history")||""),"history stores no message content");
 all("[data-del]")[0].click();ok(all(".hi-item").length>=4,"delete one history entry");$("#hclear").click();ok(/No saved checks/.test($("#hlist").textContent),"delete all history");
 ok($("#aiwrap").hidden,"AI toggle hidden when the server has no AI configured");
 $('[data-m=text]').click();$("#text").value="Guaranteed 40% returns. Send your OTP now.";$("#go").click();await wait(500);
 $("[data-lb=scam]").click();ok(/tick the box/.test($("#cmsg").textContent),"learning: sharing needs explicit consent");
 $("#cons").checked=true;$("[data-lb=scam]").click();await wait(500);ok(/Shared \d+ fragments/.test($("#cmsg").textContent),"learning: masked fragments shared + shown to the user: "+$("#cmsg").textContent.slice(0,70));
 $("#cdel").click();await wait(400);ok(/Deleted/.test($("#cmsg").textContent),"learning: user can delete what they shared");
 console.log("js errors:",errs.length?errs:"none");process.exit(0)});
