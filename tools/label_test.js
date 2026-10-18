// Runs the REAL drawOverlay out of index.html against stubbed canvas + real scan
// results, and reports whether any label fell off-screen or onto another.
import * as std from "qjs:std";
const html = std.loadFile("/data/data/com.termux/files/home/src/dalton/index.html");

const A = html.indexOf("function fitMap(){");
const B = html.indexOf("function footText(){");
const C = html.indexOf("}", html.indexOf("return p.length ? 'ignored: '"));
const src = html.slice(A, B) + html.slice(B, C+1);

const boxes = [];
const ctx = {
  setTransform(){}, clearRect(){}, fillRect(){}, drawImage(){},
  beginPath(){}, moveTo(){}, lineTo(){}, arcTo(){}, arc(){}, closePath(){},
  fill(){}, stroke(){},
  measureText(t){ return {width: t.length * (this.font.indexOf('17px')>=0 ? 9.3
                                           : this.font.indexOf('18px')>=0 ? 9.8 : 6.4)}; },
  fillText(t,x,y){ boxes.push({t,x,y}); },
  font:'', fillStyle:'', strokeStyle:'', lineWidth:0, textAlign:'', textBaseline:''
};

globalThis.window = {devicePixelRatio:2};
const run = new Function("cam","ov","octx","shotc","shot","sens","TIER","MAX_LEDS","boxes",
  src + "\n drawOverlay(); return null;");

function trial(name, cw, ch, W, H, leds){
  boxes.length = 0;
  const shot = {W, H, leds, drop:{small:0,big:0,over:0}, frac:0.68, T:173, peak:255};
  const placed = [];
  const ctx2 = Object.create(ctx);
  // capture the boxes drawn, by recomputing from fillText anchors
  run({clientWidth:cw, clientHeight:ch}, {style:{}}, ctx, {}, shot, 'high',
      {low:[55,0.90],med:[35,0.82],high:[25,0.68]}, 24, boxes);
  const labs = boxes.filter(b=>b.t!=='NO LIGHT FOUND' && b.t.indexOf('ignored:')!==0);
  const rects = labs.map(b=>({t:b.t, x:b.x-8, y:b.y-14.5, w:b.t.length*9.3+16, h:28}));
  let off=0, ov=0;
  for(let i=0;i<rects.length;i++){
    const r=rects[i];
    if(r.x<0 || r.y<0 || r.x+r.w>cw+0.5 || r.y+r.h>ch+0.5) off++;
    for(let j=i+1;j<rects.length;j++){
      const q=rects[j];
      if(!(r.x+r.w<=q.x || q.x+q.w<=r.x || r.y+r.h<=q.y || q.y+q.h<=r.y)) ov++;
    }
  }
  print(`  ${name.padEnd(34)} ${String(rects.length).padStart(2)} labels   off-screen ${off}   overlapping ${ov}`);
  return off+ov;
}

function led(cx,cy,area,label,sure){
  return {cx, cy, area, rad:Math.sqrt(area/Math.PI), pad:6,
          res:{label, hue:sure?null:123.4, sure}};
}
let bad = 0;
print("portrait phone 400x640, landscape frame 1280x720");
bad += trial("router: 7 stacked, centre", 400,640,1280,720,
  Array.from({length:7},(_,i)=>led(640,240+55*i,900,['WHITE','GREEN','GREEN','YELLOW','RED','GREEN','OTHER'][i],true)));
bad += trial("7 stacked, all hedged names", 400,640,1280,720,
  Array.from({length:7},(_,i)=>led(640,230+52*i,900,'YELLOW OR GREEN',false)));
bad += trial("LEDs at the far left and right", 400,640,1280,720,
  [led(40,360,400,'RED',true),led(1240,360,400,'GREEN',true),led(640,80,400,'YELLOW',true),led(640,660,400,'GREEN',true)]);
bad += trial("4 corners", 400,640,1280,720,
  [led(60,60,300,'RED',true),led(1220,60,300,'GREEN',true),led(60,660,300,'YELLOW',true),led(1220,660,300,'WHITE',true)]);
bad += trial("6 clustered in one corner", 400,640,1280,720,
  [led(120,100,200,'RED',true),led(170,130,200,'GREEN',true),led(220,100,200,'YELLOW',true),
   led(140,170,200,'GREEN',true),led(200,180,200,'RED',true),led(260,140,200,'WHITE',true)]);
bad += trial("the 24-LED cap, 4x6 grid", 400,640,1280,720,
  Array.from({length:24},(_,i)=>led(300+ (i%4)*220, 120+((i/4)|0)*95, 250,
    ['RED','GREEN','YELLOW','WHITE'][i%4], true)));
print("\nlandscape 640x400, same frame");
bad += trial("router: 7 stacked", 640,400,1280,720,
  Array.from({length:7},(_,i)=>led(640,240+55*i,900,'GREEN',true)));
print(bad===0 ? "\nALL CLEAN" : `\n${bad} PROBLEMS`);
