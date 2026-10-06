// Pack the caption slides into a broadly playable Motion JPEG AVI.
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const root = __dirname;
execFileSync('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', path.join(root, 'make_frames.ps1')], {stdio: 'inherit'});
const frames = fs.readdirSync(path.join(root, 'video_frames')).filter(x => x.endsWith('.jpg')).sort().map(x => fs.readFileSync(path.join(root, 'video_frames', x)));
const durationPerSlide = 9;
const repeats = frames.flatMap(frame => Array(durationPerSlide).fill(frame));
const width = 960, height = 540, fps = 1;
const fourcc = s => Buffer.from(s, 'ascii');
const u32 = n => { const b = Buffer.alloc(4); b.writeUInt32LE(n >>> 0); return b; };
const i32 = n => { const b = Buffer.alloc(4); b.writeInt32LE(n); return b; };
const u16 = n => { const b = Buffer.alloc(2); b.writeUInt16LE(n); return b; };
const chunk = (id, data) => Buffer.concat([fourcc(id), u32(data.length), data, data.length % 2 ? Buffer.alloc(1) : Buffer.alloc(0)]);
const list = (type, data) => chunk('LIST', Buffer.concat([fourcc(type), data]));
const maxSize = Math.max(...frames.map(f => f.length));

const avih = Buffer.concat([
  u32(1000000 / fps), u32(maxSize * fps), u32(0), u32(0x10), u32(repeats.length),
  u32(0), u32(1), u32(maxSize), u32(width), u32(height), Buffer.alloc(16)
]);
const strh = Buffer.concat([
  fourcc('vids'), fourcc('MJPG'), u32(0), u16(0), u16(0), u32(0),
  u32(1), u32(fps), u32(0), u32(repeats.length), u32(maxSize), i32(-1),
  u32(0), u16(0), u16(0), u16(width), u16(height)
]);
const strf = Buffer.concat([
  u32(40), i32(width), i32(height), u16(1), u16(24), fourcc('MJPG'),
  u32(width * height * 3), i32(0), i32(0), u32(0), u32(0)
]);
const hdrl = list('hdrl', Buffer.concat([chunk('avih', avih), list('strl', Buffer.concat([chunk('strh', strh), chunk('strf', strf)]))]));
const moviParts = [];
const indices = [];
let offset = 4;
for (const frame of repeats) {
  const part = chunk('00dc', frame);
  moviParts.push(part);
  indices.push(Buffer.concat([fourcc('00dc'), u32(0x10), u32(offset), u32(frame.length)]));
  offset += part.length;
}
const body = Buffer.concat([hdrl, list('movi', Buffer.concat(moviParts)), chunk('idx1', Buffer.concat(indices))]);
const avi = Buffer.concat([fourcc('RIFF'), u32(body.length + 4), fourcc('AVI '), body]);
const out = path.join(root, 'demo_walkthrough.avi');
fs.writeFileSync(out, avi);
console.log(`Wrote ${out}: ${repeats.length} seconds, ${(avi.length / 1048576).toFixed(2)} MiB`);
