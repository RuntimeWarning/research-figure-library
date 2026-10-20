// Render NN-SVG (MIT, github.com/alexlenail/NN-SVG) architecture schematics headlessly.
//
//   node nnsvg.mjs <NN-SVG checkout> <output dir> [chrome executable]
//
// Needs `puppeteer-core` and network access for the CDN scripts the NN-SVG pages load.  Math.random is
// seeded so that the randomly placed convolution windows are the same on every run.
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import puppeteer from 'puppeteer-core';

const [root, out, chrome = 'C:/Program Files/Google/Chrome/Application/chrome.exe'] = process.argv.slice(2);
mkdirSync(out, { recursive: true });

const lenet = (layers, fc = [120, 84, 10]) => ({
  architecture_: layers.map(([n, h, w, f], i) => ({ numberOfSquares: n, squareHeight: h, squareWidth: w,
    filterHeight: f, filterWidth: f, op: i === layers.length - 1 ? 'Dense' : 'Convolution', layer: i })),
  architecture2_: fc,
});
const LENET = [[1, 64, 64, 5], [4, 52, 52, 5], [4, 32, 32, 5], [6, 22, 22, 3], [6, 12, 12, 3]];
const LENET_DEEP = [[3, 64, 64, 5], [5, 56, 56, 3], [5, 36, 36, 3], [7, 28, 28, 3], [7, 18, 18, 3], [9, 10, 10, 3]];
const alex = (layers, fc = [2048, 2048]) => ({
  architecture_: layers.map(([h, w, d, f], i) => ({ height: h, width: w, depth: d, filterHeight: f, filterWidth: f,
    rel_x: [0.25, -0.2, 0.15, -0.25, 0.2, -0.1][i % 6], rel_y: [-0.2, 0.25, -0.15, 0.2, -0.25, 0.1][i % 6] })),
  architecture2_: fc,
});
const ALEXNET = [[224, 224, 3, 11], [55, 55, 96, 5], [27, 27, 256, 3], [13, 13, 384, 3], [13, 13, 256, 3]];
const VGG = [[224, 224, 3, 3], [224, 224, 64, 3], [112, 112, 128, 3], [56, 56, 256, 3], [28, 28, 512, 3], [14, 14, 512, 3]];
const ENCODER = [[128, 128, 16, 3], [64, 64, 32, 3], [32, 32, 64, 3], [16, 16, 128, 3], [8, 8, 256, 3]];

const JOBS = [
  ['fcnn-small', 'index.html', 'fcnn', { arch: [3, 4, 4, 2] }],
  ['fcnn-classic', 'index.html', 'fcnn', { arch: [4, 6, 6, 3] }],
  ['fcnn-wide', 'index.html', 'fcnn', { arch: [8, 12, 12, 8, 4] }],
  ['fcnn-deep', 'index.html', 'fcnn', { arch: [5, 7, 7, 7, 7, 3] }],
  ['fcnn-blue', 'index.html', 'fcnn', { arch: [4, 6, 6, 3], style: { nodeColor_: '#a5c8ff', nodeBorderColor_: '#2f5fb3', defaultEdgeColor_: '#7b93bd' } }],
  ['fcnn-weights', 'index.html', 'fcnn', { arch: [6, 8, 8, 4], style: { edgeWidthProportional_: true, edgeWidth_: 1.6, edgeColorProportional_: true, negativeEdgeColor_: '#2f6fde', positiveEdgeColor_: '#e8590c' } }],
  ['fcnn-vertical', 'index.html', 'fcnn', { arch: [3, 5, 5, 2], layout: { nnDirection_: 'up' } }],
  ['lenet-gray', 'LeNet.html', 'lenet', { ...lenet(LENET) }],
  ['lenet-blue', 'LeNet.html', 'lenet', { ...lenet(LENET), style: { color1_: '#dbe7ff', color2_: '#8db3f0' } }],
  ['lenet-orange', 'LeNet.html', 'lenet', { ...lenet(LENET), style: { color1_: '#ffe8cc', color2_: '#f5a35c' } }],
  ['lenet-deep', 'LeNet.html', 'lenet', { ...lenet(LENET_DEEP, [512, 128, 10]), style: { color1_: '#e6fcf5', color2_: '#63c9a8' } }],
  ['alexnet', 'AlexNet.html', 'alexnet', { ...alex(ALEXNET) }],
  ['alexnet-blue', 'AlexNet.html', 'alexnet', { ...alex(ALEXNET), style: { color1_: '#dbe7ff', color2_: '#4c7bd9', color3_: '#ffc078' } }],
  ['vgg-3d', 'AlexNet.html', 'alexnet', { ...alex(VGG, [4096, 4096, 1000]), style: { color1_: '#e5dbff', color2_: '#9775fa', color3_: '#ffa8a8' } }],
  ['encoder-3d', 'AlexNet.html', 'alexnet', { ...alex(ENCODER, [1024]), style: { color1_: '#d3f9d8', color2_: '#40c057', color3_: '#ffd43b' } }],
];

const SEED = `(() => { let s = 20241020; Math.random = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296); })();`;
const browser = await puppeteer.launch({ executablePath: chrome, headless: 'new', args: ['--allow-file-access-from-files'] });
for (const [name, file, kind, job] of JOBS) {
  const page = await browser.newPage();
  await page.setViewport({ width: 1600, height: 1000 });
  await page.evaluateOnNewDocument(SEED);
  await page.goto(pathToFileURL(join(root, file)).href, { waitUntil: 'networkidle0', timeout: 120000 });
  const svg = await page.evaluate(async (kind, job) => {
    const wait = ms => new Promise(r => setTimeout(r, ms));
    if (kind === 'fcnn') {
      fcnn.redraw({ architecture_: job.arch, showLabels_: false });
      fcnn.redistribute({ betweenNodesInLayer_: job.arch.map(() => 12), betweenLayers_: 120, ...(job.layout || {}) });
      fcnn.style({ ...(job.style || {}) });
    } else if (kind === 'lenet') {
      lenet.redraw({ architecture_: job.architecture_, architecture2_: job.architecture2_, sqrtLength_: true, lengthScale_: 70 });
      lenet.redistribute({ betweenLayers_: job.architecture_.map(() => 26), betweenSquares_: 7 });
      lenet.style({ showLabels_: false, ...(job.style || {}) });
    } else {
      alexnet.restartRenderer({ rendererType_: 'svg' });
      alexnet.redraw({ architecture_: job.architecture_, architecture2_: job.architecture2_, showDims_: false });
      alexnet.style({ ...(job.style || {}) });
      await wait(800);
    }
    await wait(300);
    const svg = document.querySelector('#graph-container svg');
    svg.querySelectorAll('text').forEach(t => { if (!t.textContent.trim()) t.remove(); });
    const box = svg.getBBox();
    const pad = 12;
    const clone = svg.cloneNode(true);
    clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    clone.setAttribute('viewBox', `${box.x - pad} ${box.y - pad} ${box.width + 2 * pad} ${box.height + 2 * pad}`);
    clone.setAttribute('width', Math.round(box.width + 2 * pad));
    clone.setAttribute('height', Math.round(box.height + 2 * pad));
    clone.removeAttribute('style');
    return clone.outerHTML;
  }, kind, job);
  writeFileSync(join(out, `${name}.svg`), svg);
  console.log(name, svg.length);
  await page.close();
}
await browser.close();
