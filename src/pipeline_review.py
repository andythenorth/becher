"""Local review browser for procedural candidate families and 4-view branches."""
from __future__ import annotations
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import threading
from . import pipeline

HTML=r'''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Becher — architectural selection</title>
<style>
:root{font:14px system-ui,sans-serif;color-scheme:dark}*{box-sizing:border-box}
body{margin:0;padding:20px;background:#161f29;color:#e5edf5;max-width:1600px}
h1{font-size:24px;margin:0 0 4px}h2{font-size:15px;margin:0 0 7px}
p,.muted{color:#aabaca}#toolbar{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin:16px 0}
button,select,textarea{background:#273646;color:#f2f6fa;border:1px solid #516477;border-radius:6px;padding:6px 8px;font:inherit}
button{cursor:pointer}button:hover{background:#365169}button[disabled]{opacity:.35;cursor:default}
label{font-size:12px;color:#c3d1df}#grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px}
.card{background:#202d3b;border:1px solid #43576b;border-radius:10px;padding:12px}
.card.yes{border-color:#58b78d}.card.no{border-color:#bb6666}
.images{display:flex;gap:3px;overflow:auto;background:#0000fa;padding:5px;border-radius:4px;min-height:142px}
.images img{width:64px;height:128px;object-fit:contain;image-rendering:pixelated;flex:none}
.controls{display:flex;flex-wrap:wrap;align-items:center;gap:5px;margin-top:10px}
button.good{border-color:#58b78d}button.bad{border-color:#bb6666}
.lock{display:inline-flex;align-items:center;gap:4px;font-size:11px;border:1px solid #45576a;padding:5px;border-radius:4px}
.lock input{margin:0}.foot{margin:16px 0;color:#94a5b8;font-size:12px}
#notice{color:#ffcf8c;white-space:pre-wrap}textarea{width:100%;margin-top:8px;min-height:40px}
</style>
<h1>Becher — candidate selection</h1>
<p>Four projections of each architectural candidate. Accept/reject, lock individual passes, branch a reroll or return to an earlier rendered leaf. Structural fabric is never overwritten.</p>
<div id="toolbar"><label>Family <select id="family"><option value="all">All</option></select></label>
<label>Status <select id="status"><option value="all">All</option><option value="undecided">Undecided</option><option value="yes">Accepted</option><option value="no">Rejected</option></select></label>
<span id="stats"></span><button id="refresh">Refresh</button></div>
<div id="notice"></div><div id="grid">Loading candidates…</div>
<div class="foot">Rendering and rerolling run locally. The manifest records immutable scene ancestry; feedback.json records decisions and locks. Palette textures are not applied.</div>
<script>
const stages=['windows','doors','equipment','greeble'];let state;
const $=id=>document.getElementById(id);
async function req(path,body){let opts=body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{};
 let r=await fetch(path,opts);let j=await r.json();if(!r.ok)throw Error(j.error||r.statusText);return j}
function elem(tag,cls,txt){let e=document.createElement(tag);if(cls)e.className=cls;if(txt!==undefined)e.textContent=txt;return e}
function control(card,label,action,disabled=false){let b=elem('button','',label);b.disabled=disabled;b.onclick=async()=>{
 try{b.disabled=true;notice('Working: '+label+'…');await action();await load();notice('')}catch(e){notice(e.message)}finally{b.disabled=false}}
 card.append(b);return b}
function notice(t){$('notice').textContent=t}
async function load(){state=await req('/api/state');const {manifest,feedback}=state;
 const families=[...new Set(Object.values(manifest.candidates).map(c=>c.family))].sort();let old=$('family').value;
 $('family').replaceChildren(new Option('All','all'),...families.map(f=>new Option(f,f)));$('family').value=families.includes(old)?old:'all';
 const root=$('grid');root.replaceChildren();let shown=0;
 for(const [id,info] of Object.entries(manifest.candidates)){
   if(info.active===false)continue; // Archived candidates remain in the immutable history.
   let entry=feedback.candidates[id]||{vote:'undecided',locks:[],notes:''};
   if($('family').value!=='all'&&$('family').value!==info.family)continue;
   if($('status').value!=='all'&&$('status').value!==(entry.vote||'undecided'))continue;
   shown++;
   let node=manifest.nodes[info.current],box=elem('article','card '+(entry.vote||''));root.append(box);
   box.append(elem('h2','',id+' · '+info.label));
   let images=elem('div','images');box.append(images);
   for(const spr of node.sprites){let img=elem('img');img.src=spr.file+'?v='+node.id;img.alt='Orientation '+spr.rotation+'°';img.title='Rotation '+spr.rotation+'°';images.append(img)}
   box.append(elem('div','muted','Fabric '+info.root.slice(0,9)+' · branch '+node.id.slice(0,9)+' · '+info.history.length+' scene versions'));
   let votes=elem('div','controls');box.append(votes);
   control(votes,'✓ Accept',()=>req('/api/vote',{candidate:id,vote:'yes'})).classList.add('good');
   control(votes,'✕ Reject',()=>req('/api/vote',{candidate:id,vote:'no'})).classList.add('bad');
   control(votes,'Clear',()=>req('/api/vote',{candidate:id,vote:'undecided'}));
   let actions=elem('div','controls');box.append(actions);
   let stage=elem('select');for(let s of stages)stage.append(new Option(s,s));actions.append(stage);
   control(actions,'Reroll selected pass',()=>req('/api/reroll',{candidate:id,stage:stage.value}),false);
   let history=elem('select');for(const n of info.history){const r=manifest.nodes[n];if(r.sprites.length)history.append(new Option(r.stage+' · '+n.slice(0,9),n))}
   history.value=info.current;actions.append(history);
   control(actions,'Restore version',()=>req('/api/select',{candidate:id,node:history.value}));
   let locks=elem('div','controls');box.append(locks);
   for(const s of stages){let label=elem('label','lock');let cb=elem('input');cb.type='checkbox';cb.checked=(entry.locks||[]).includes(s);
     cb.onchange=async()=>{try{await req('/api/lock',{candidate:id,stage:s,locked:cb.checked});notice('')}catch(e){notice(e.message);cb.checked=!cb.checked}};
     label.append(cb,document.createTextNode(s));locks.append(label)}
   let note=elem('textarea');note.placeholder='Optional architectural review note';note.value=entry.notes||'';box.append(note);
   note.onchange=async()=>{try{await req('/api/notes',{candidate:id,notes:note.value})}catch(e){notice(e.message)}};
 }
 $('stats').textContent=shown+' buildings · '+(manifest.rotations_per_design*shown)+' projections shown';
}
$('refresh').onclick=()=>load().catch(e=>notice(e.message));$('family').onchange=()=>load().catch(e=>notice(e.message));
$('status').onchange=()=>load().catch(e=>notice(e.message));load().catch(e=>notice(e.message));
</script></html>'''


def write_review(out):
    (Path(out)/'index.html').write_text(HTML,encoding='utf-8')


def serve(out,host='127.0.0.1',port=8000):
    out=Path(out).resolve()
    if not (out/'manifest.json').exists():raise FileNotFoundError('Run `becher pipeline` first')
    lock=threading.RLock()
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(out),**kwargs)
        def respond(self,code,obj):
            b=json.dumps(obj,ensure_ascii=False).encode()
            self.send_response(code);self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Content-Length',str(len(b)))
            self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(b)
        def do_GET(self):
            if self.path=='/api/state':
                with lock:self.respond(200,{'manifest':pipeline._load_manifest(out),'feedback':pipeline.read_feedback(out)})
            else:super().do_GET()
        def do_POST(self):
            with lock:
                try:
                    if not self.path.startswith('/api/'):raise ValueError('Invalid endpoint')
                    length=int(self.headers.get('Content-Length','0'))
                    if not 0<length<16000:raise ValueError('Invalid request size')
                    req=json.loads(self.rfile.read(length));candidate=req.get('candidate')
                    if self.path=='/api/vote':
                        result=pipeline.feedback_action(out,candidate,'vote',value=req.get('vote'))
                    elif self.path=='/api/lock':
                        action='lock' if req.get('locked') else 'unlock'
                        result=pipeline.feedback_action(out,candidate,action,value=req.get('stage'))
                    elif self.path=='/api/notes':
                        result=pipeline.feedback_action(out,candidate,'notes',notes=req.get('notes'))
                    elif self.path=='/api/reroll':
                        result=pipeline.branch(out,candidate,req.get('stage'),workers=1,buffers=True)
                    elif self.path=='/api/select':
                        result=pipeline.select(out,candidate,req.get('node'))
                    else:raise ValueError('Unknown API endpoint')
                    self.respond(200,result)
                except (ValueError,KeyError,FileNotFoundError) as error:self.respond(400,{'error':str(error)})
                except Exception as error:self.respond(500,{'error':str(error)})
    server=ThreadingHTTPServer((host,port),Handler)
    print(f'Becher review: http://{host}:{server.server_port}/',flush=True)
    try:server.serve_forever()
    finally:server.server_close()
