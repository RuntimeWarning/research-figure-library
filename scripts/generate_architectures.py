#!/usr/bin/env python3
"""Generate independently designed, editable MIT architecture schematics.

SVG generation uses only Python's standard library and works from any clone path:
    python scripts/generate_architectures.py

Optional rendered contact sheet (not needed to generate SVG):
    pip install resvg-py Pillow
    python scripts/generate_architectures.py --qa

The diagrams express architecture facts, not the compositions of published figures.
They are intentionally abstract and omit implementation details unless labeled.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'dist/assets/architectures'
BACKUP = ROOT / '.local-backup/new-assets'
COPYRIGHT = 'Copyright (c) 2026 Research Figure Library contributors'
LICENSE_TEXT = (ROOT / 'LICENSE').read_text(encoding='utf-8').strip()
PALETTE = {
    'blue': ('#e3edfc', '#a9c2e8'),
    'teal': ('#ddf1e9', '#9bc9b7'),
    'purple': ('#ece5f8', '#bda9dc'),
    'orange': ('#fcebd9', '#e4bc91'),
    'rose': ('#f7e3ea', '#dba6bc'),
    'gray': ('#f1f4f8', '#bdc8d5'),
}
INK = '#2e3e52'
MUTED = '#7d8b9e'
ARROW = '#91a0b3'
LICENSE_NOTE = '本项目独立绘制的概念示意（MIT），原论文仅作事实来源；非原论文插图。'
SCHEMATIC_NOTE = '结构为概念抽象，省略部分层级、参数和训练细节；采用本项目独立布局，未复刻原论文图。所有节点、文字和箭头均为可编辑原生 SVG。'


class Diagram:
    def __init__(self, title, subtitle, width=1120, height=450):
        self.title, self.subtitle = title, subtitle
        self.w, self.h = width, height
        self.parts = []
        self.index = 0
        self.text(36, 44, title, 27, weight=650, anchor='start')
        self.text(37, 72, subtitle, 14, color=MUTED, anchor='start')

    def text(self, x, y, text, size=16, color=INK, anchor='middle', weight=400):
        self.parts.append(f'<text x="{x:g}" y="{y:g}" font-size="{size:g}" fill="{color}" text-anchor="{anchor}" dominant-baseline="middle" font-weight="{weight}">{html.escape(str(text))}</text>')

    def block(self, x, y, w, h, title, sub='', color='blue', size=18):
        fill, stroke = PALETTE[color]
        self.index += 1
        self.parts.append(f'<g id="module-{self.index}"><rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" rx="11" fill="{fill}" stroke="{stroke}" stroke-width="1.3"/>')
        labels = [(line, size, 600) for line in str(title).split('\n')]
        labels += [(line, 14, 400) for line in str(sub).split('\n') if line]
        line_height = 24 if len(labels) < 4 else 21
        for i, (label, fontsize, weight) in enumerate(labels):
            fitted = min(fontsize, max(11, (w-18)/(max(1,len(label))*.54)))
            self.text(x+w/2, y+h/2+(i-(len(labels)-1)/2)*line_height, label, fitted, weight=weight)
        self.parts.append('</g>')
        return (x, y, w, h)

    def line(self, points, arrow=True, dashed=False, color=ARROW, start_arrow=False, width=1.8):
        d = ' '.join(('M' if i == 0 else 'L')+f'{x:g},{y:g}' for i,(x,y) in enumerate(points))
        dash = ' stroke-dasharray="5 5"' if dashed else ''
        marker = ' marker-end="url(#arrow)"' if arrow else ''
        marker += ' marker-start="url(#arrow)"' if start_arrow else ''
        self.parts.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width:g}" stroke-linejoin="round" stroke-linecap="round"{dash}{marker}/>')

    def connect(self, a, b, direction='right', dashed=False):
        ax,ay,aw,ah=a;bx,by,bw,bh=b
        if direction=='right':self.line([(ax+aw,ay+ah/2),(bx,by+bh/2)],dashed=dashed)
        elif direction=='left':self.line([(ax,ay+ah/2),(bx+bw,by+bh/2)],dashed=dashed)
        elif direction=='down':self.line([(ax+aw/2,ay+ah),(bx+bw/2,by)],dashed=dashed)
        elif direction=='up':self.line([(ax+aw/2,ay),(bx+bw/2,by+bh)],dashed=dashed)

    def op(self, x, y, symbol='+', color='orange', radius=18):
        fill, stroke=PALETTE[color]
        self.parts.append(f'<circle cx="{x:g}" cy="{y:g}" r="{radius:g}" fill="{fill}" stroke="{stroke}" stroke-width="1.4"/>')
        self.text(x,y+.5,symbol,22,weight=500)
        return (x-radius,y-radius,radius*2,radius*2)

    def group(self,x,y,w,h,label):
        self.parts.append(f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" rx="15" fill="none" stroke="#d3dce6" stroke-width="1.1" stroke-dasharray="5 5"/>')
        self.text(x+16,y+18,label,12,color=MUTED,anchor='start',weight=600)

    def pixels(self,x,y,size=90,kind='image',noise=0):
        self.parts.append(f'<g><rect x="{x}" y="{y}" width="{size}" height="{size}" rx="10" fill="#f1f4f8" stroke="#bdc8d5"/>')
        n=5;cell=(size-18)/n
        for r in range(n):
            for c in range(n):
                base=(r*13+c*29+7)%101/100
                if kind=='mask': color=['#b2dace','#e1c6df','#d1e2f9'][(r//2+c//2)%3]
                else:
                    level=int(110+base*105*noise+(r+c)*6*(1-noise));level=min(238,max(100,level))
                    color=f'#{level:02x}{min(245,level+12):02x}{min(250,level+25):02x}'
                self.parts.append(f'<rect x="{x+9+c*cell:.2f}" y="{y+9+r*cell:.2f}" width="{cell-1.7:.2f}" height="{cell-1.7:.2f}" rx="1.4" fill="{color}"/>')
        self.parts.append('</g>')
        return(x,y,size,size)

    def footer(self, note='Concept schematic · implementation details omitted · original artwork / MIT'):
        self.parts.append(f'<path d="M36 {self.h-43}H{self.w-36}" stroke="#e4e9ef" stroke-width="1"/>')
        self.text(37,self.h-22,note,11,color=MUTED,anchor='start')

    def svg(self, meta):
        self.footer(meta.get('footer','Concept schematic · implementation details omitted · original artwork / MIT'))
        metadata=html.escape(json.dumps({'license':'MIT','copyright':COPYRIGHT,'license_text':LICENSE_TEXT,'source_url':meta['source_url'],'source_title':meta['source_title'],'original_artwork':True,'not_a_reproduction':True},ensure_ascii=False))
        return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}" role="img" aria-labelledby="diagram-title diagram-desc">
<title id="diagram-title">{html.escape(self.title)}</title>
<desc id="diagram-desc">Original conceptual schematic. {html.escape(meta['facts'])} Not a reproduction of a paper figure. MIT.</desc>
<metadata>{metadata}</metadata>
<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M1 1L9 5L1 9Z" fill="{ARROW}"/></marker></defs>
<g font-family="Arial, Helvetica, sans-serif">{''.join(self.parts)}</g>
</svg>'''


def lenet():
    d=Diagram('LeNet-5','Convolution → learned subsampling → feature vector → RBF output',1120,340)
    steps=[(90,'Input','32 × 32','gray'),(115,'C1 · Conv','6 × 28 × 28','blue'),(115,'S2 · Subsample','6 × 14 × 14','teal'),(115,'C3 · Conv','16 × 10 × 10','blue'),(115,'S4 · Subsample','16 × 5 × 5','teal'),(100,'C5 · Conv','120 units','purple'),(90,'F6 · Dense','84 units','orange'),(90,'RBF','10 outputs','rose')]
    x=36;prev=None
    for w,t,s,c in steps:
        b=d.block(x,155,w,87,t,s,c,size=16)
        if prev:d.connect(prev,b)
        prev=b;x+=w+18
    d.text(560,266,'The original network uses trainable subsampling and Euclidean RBF outputs.',13,color=MUTED)
    return d

def alexnet():
    d=Diagram('AlexNet','Five convolutional layers followed by three fully connected layers',1120,375)
    steps=[(90,'RGB image','','gray'),(135,'Conv 1','11 × 11 · 96 ch','blue'),(135,'Conv 2','5 × 5 · 256 ch','blue'),(165,'Conv 3 → 5','3 × 3 · 384 / 384 / 256','purple'),(150,'FC 1 → 2','4096 → 4096','orange'),(145,'FC 3','1000 + Softmax','rose')]
    x=45;prev=None
    for w,t,s,c in steps:
        b=d.block(x,160,w,90,t,s,c,size=17)
        if prev:d.connect(prev,b)
        prev=b;x+=w+32
    for x in [251,418,615]:d.text(x,278,'MaxPool',12,color=MUTED)
    d.text(560,315,'ReLU activations · local response normalization in early layers · dropout in the classifier',13,color=MUTED)
    return d

def vgg():
    d=Diagram('VGG-16','Thirteen 3 × 3 convolutions + three fully connected layers',1120,350)
    x=36;prev=d.block(x,155,80,100,'Image','','gray',16);x+=110
    for repeats,ch in [(2,64),(2,128),(3,256),(3,512),(3,512)]:
        b=d.block(x,155,125,100,f'{repeats} × Conv 3 × 3',f'{ch} channels\nMaxPool 2 × 2','blue',16)
        d.connect(prev,b);prev=b;x+=151
    b=d.block(x,155,175,100,'FC classifier','4096 → 4096 → 1000\nSoftmax','orange',17);d.connect(prev,b)
    return d

def googlenet():
    d=Diagram('GoogLeNet / Inception-v1','Multi-scale convolution branches are concatenated, then repeated through the network',1240,540)
    image=d.block(35,244,90,70,'Image','','gray',17);stem=d.block(160,244,130,70,'Conv stem','Conv + pooling','blue',17);d.connect(image,stem)
    d.group(345,104,505,333,'INCEPTION · 9 modules across the full network')
    ys=[149,220,291,362];branches=[]
    for i,(first,second,col) in enumerate([('1 × 1 Conv','', 'teal'),('1 × 1 Conv','3 × 3 Conv','blue'),('1 × 1 Conv','5 × 5 Conv','purple'),('3 × 3 Pool','1 × 1 Conv','orange')]):
        a=d.block(385,ys[i],130,50,first,'',col,16);b=d.block(550,ys[i],145,50,second or 'Identity','',col,16)
        d.line([(290,279),(330,279),(330,ys[i]+25),(385,ys[i]+25)]);d.connect(a,b);branches.append(b)
    concat=d.block(735,231,85,97,'Concat','channels','rose',16)
    for b in branches:d.line([(695,b[1]+25),(715,b[1]+25),(715,279),(735,279)])
    gap=d.block(890,244,120,70,'AvgPool','global','teal',17);out=d.block(1045,244,160,70,'Classifier','Linear + Softmax','orange',17);d.connect(concat,gap);d.connect(gap,out)
    aux=d.block(905,390,275,65,'Auxiliary heads × 2','Training only · removed at inference','gray',17)
    d.line([(820,300),(867,300),(867,422),(905,422)],dashed=True)
    return d

def resnet():
    d=Diagram('ResNet-18','Residual stages: [2, 2, 2, 2] basic blocks',1180,520)
    steps=[(100,'Image','','gray'),(125,'Stem','7 × 7 + Pool','blue'),(130,'Stage 1','64 ch · 2 blocks','teal'),(130,'Stage 2','128 ch · 2 blocks','teal'),(130,'Stage 3','256 ch · 2 blocks','teal'),(130,'Stage 4','512 ch · 2 blocks','teal'),(150,'GAP + FC','class prediction','orange')]
    x=35;prev=None
    for w,t,s,c in steps:
        b=d.block(x,135,w,75,t,s,c,16)
        if prev:d.connect(prev,b)
        prev=b;x+=w+25
    d.group(205,280,765,165,'BASIC BLOCK · same-shape shortcut shown')
    b1=d.block(310,340,190,62,'Conv 3 × 3','BN + ReLU','blue',17);b2=d.block(540,340,170,62,'Conv 3 × 3','BN','purple',17);d.connect(b1,b2);plus=d.op(770,371);relu=d.block(825,340,105,62,'ReLU','','orange',17)
    d.line([(250,371),(310,371)]);d.line([(710,371),(752,371)]);d.line([(788,371),(825,371)]);d.line([(270,371),(270,316),(770,316),(770,353)])
    d.text(1020,352,'x + F(x)',17,weight=600);d.text(1020,380,'match dimensions',12,color=MUTED);d.text(1020,398,'when downsampling',12,color=MUTED)
    return d

def densenet():
    d=Diagram('DenseNet','Every layer receives a concatenation of all preceding feature maps',1180,550)
    x=35;prev=d.block(x,128,100,72,'Stem','','blue',17);x=170
    for i in range(4):
        b=d.block(x,128,160,72,f'Dense block {i+1}','feature reuse','teal',17);d.connect(prev,b);prev=b;x+=222
        if i<3:d.text(x-32,228,'Transition',12,color=MUTED);d.text(x-32,246,'1 × 1 + AvgPool',11,color=MUTED)
    head=d.block(1055,128,90,72,'Head','GAP + FC','orange',16);d.connect(prev,head)
    d.group(65,285,1050,182,'DENSE CONNECTIVITY · concatenation, not element-wise addition')
    inp=d.block(95,366,105,65,'x₀','','gray',18)
    h1=d.block(280,366,170,65,'H₁','input: x₀','blue',18);h2=d.block(515,366,170,65,'H₂','input: [x₀, x₁]','purple',18);h3=d.block(750,366,170,65,'H₃','input: [x₀, x₁, x₂]','teal',18);out=d.block(975,366,110,65,'Concat','all features','rose',16)
    for a,b in [(inp,h1),(h1,h2),(h2,h3),(h3,out)]:d.connect(a,b)
    d.line([(220,398),(220,330),(555,330),(555,366)])
    d.line([(220,398),(220,311),(790,311),(790,366)])
    d.line([(470,398),(470,345),(840,345),(840,366)])
    d.line([(220,398),(220,453),(1030,453),(1030,431)])
    d.line([(470,398),(470,453)],arrow=False)
    d.line([(705,398),(705,453)],arrow=False)
    return d

def mobilenet():
    d=Diagram('MobileNetV2','Inverted residuals connect thin bottlenecks; the final projection is linear',1170,505)
    steps=[(130,'Conv stem','','blue'),(230,'Inverted residual stack','Depthwise separable blocks','teal'),(150,'1 × 1 Conv','','blue'),(130,'Global AvgPool','','purple'),(150,'Classifier','','orange')]
    x=90;prev=None
    for w,t,s,c in steps:
        b=d.block(x,126,w,70,t,s,c,17)
        if prev:d.connect(prev,b)
        prev=b;x+=w+35
    d.group(90,264,990,174,'INVERTED RESIDUAL BLOCK · shortcut only for stride 1 and equal input/output channels')
    n1=d.block(120,336,105,66,'Thin input','','gray',16);expand=d.block(275,321,190,96,'1 × 1 Expand','BN + ReLU6','blue',18);dw=d.block(510,321,185,96,'3 × 3 Depthwise','BN + ReLU6','purple',18);proj=d.block(740,336,165,66,'1 × 1 Project','BN · no activation','teal',17);out=d.op(990,369)
    for a,b in [(n1,expand),(expand,dw),(dw,proj)]:d.connect(a,b)
    d.line([(905,369),(972,369)]);d.line([(245,369),(245,300),(990,300),(990,351)])
    return d

def unet():
    d=Diagram('U-Net','Contracting path + expanding path with cropped, concatenated skip features',1180,565)
    xs=[50,260,470,680];enc=[];dec=[]
    for i,x in enumerate(xs):
        enc.append(d.block(x,155,155,74,f'Encoder {i+1}','Conv 3 × 3 × 2','blue',17))
        dec.append(d.block(x,350,155,74,f'Decoder {i+1}','Up + Concat + Conv','teal',17))
        d.line([(x+77.5,229),(x+77.5,350)],dashed=True)
        d.text(x+90,278,'crop + concat',12,color=MUTED,anchor='start')
    for a,b in zip(enc,enc[1:]):d.connect(a,b)
    for a,b in zip(reversed(dec),list(reversed(dec))[1:]):d.connect(a,b,'left')
    bottleneck=d.block(945,251,190,80,'Bottleneck','Conv 3 × 3 × 2','purple',18)
    d.line([(835,192),(885,192),(885,291),(945,291)])
    d.text(916,235,'Pool ↓',11,color=MUTED)
    d.line([(1040,331),(1040,387),(835,387)])
    for x in [232,442,652]:d.text(x,135,'Pool ↓',11,color=MUTED);d.text(x,446,'↑ Up',11,color=MUTED)
    output=d.block(50,464,155,48,'1 × 1 → Mask','','rose',16);d.connect(dec[0],output,'down')
    d.text(580,485,'Skip paths carry spatial detail; channel concatenation occurs after upsampling.',13,color=MUTED)
    return d

def fcn():
    d=Diagram('FCN-8s','Fuse coarse semantic scores with stride-16 and stride-8 skip scores',1240,550)
    inp=d.block(30,255,100,75,'Image','','gray',17)
    d.group(175,112,250,345,'CONVOLUTIONAL BACKBONE')
    f8=d.block(210,155,180,65,'Pool 3 features','stride 8','blue',17);f16=d.block(210,270,180,65,'Pool 4 features','stride 16','purple',17);f32=d.block(210,385,180,65,'Deep features','stride 32 · conv7','teal',17)
    d.line([(130,292),(160,292),(160,187),(210,187)]);d.connect(f8,f16,'down');d.connect(f16,f32,'down')
    scores=[]
    for f,c in [(f8,'blue'),(f16,'purple'),(f32,'teal')]:
        b=d.block(490,f[1],130,65,'1 × 1 score','class logits',c,16);d.connect(f,b);scores.append(b)
    up1=d.block(675,385,115,65,'Upsample','× 2','teal',16);d.connect(scores[2],up1)
    plus1=d.op(835,302);d.line([(790,417),(835,417),(835,320)]);d.line([(620,302),(817,302)])
    up2=d.block(885,270,115,65,'Upsample','× 2','purple',16);d.line([(853,302),(885,302)])
    plus2=d.op(1040,187);d.line([(1000,302),(1040,302),(1040,205)]);d.line([(620,187),(1022,187)])
    up8=d.block(1090,155,110,65,'Upsample','× 8','blue',16);d.line([(1058,187),(1090,187)])
    output=d.block(1090,285,110,80,'Dense mask','pixel classes','rose',16);d.connect(up8,output,'down')
    return d

def autoencoder():
    d=Diagram('Autoencoder','Compress an input into a low-dimensional code, then reconstruct it',1120,460)
    inp=d.pixels(55,185,100);out=d.pixels(965,185,100)
    d.text(105,310,'Input x',16);d.text(1015,310,'Reconstruction x̂',16)
    d.parts.append('<path d="M225 145L460 215V285L225 355Z" fill="#e3edfc" stroke="#a9c2e8" stroke-width="1.4"/>');d.text(332,244,'Encoder',21,weight=600);d.text(332,274,'f(x)',16)
    code=d.block(515,215,90,70,'Code z','','purple',18)
    d.parts.append('<path d="M660 215L895 145V355L660 285Z" fill="#ddf1e9" stroke="#9bc9b7" stroke-width="1.4"/>');d.text(785,244,'Decoder',21,weight=600);d.text(785,274,'g(z)',16)
    d.line([(155,235),(225,235)]);d.line([(460,250),(515,250)]);d.line([(605,250),(660,250)]);d.line([(895,235),(965,235)])
    d.line([(105,285),(105,385),(1015,385),(1015,285)],arrow=False,dashed=True);d.text(560,404,'Reconstruction objective: match x̂ to x',14,color=MUTED)
    return d

def vae():
    d=Diagram('Variational Autoencoder','Infer a distribution, sample with reparameterization, and decode',1170,565)
    inp=d.block(35,260,90,75,'Input x','','gray',17);enc=d.block(165,260,150,75,'Encoder','q(z | x)','blue',19);d.connect(inp,enc)
    mu=d.block(375,170,140,60,'Mean μ','','purple',18);var=d.block(375,350,140,60,'log σ²','σ = exp(½ log σ²)','purple',17)
    d.line([(315,297),(345,297),(345,200),(375,200)]);d.line([(315,297),(345,297),(345,380),(375,380)])
    z=d.block(605,250,210,95,'Sample z','z = μ + σ ⊙ ε','teal',20)
    d.line([(515,200),(565,200),(565,276),(605,276)]);d.line([(515,380),(565,380),(565,319),(605,319)])
    eps=d.block(630,120,160,55,'ε ~ N(0, I)','','gray',17);d.connect(eps,z,'down')
    dec=d.block(865,260,145,75,'Decoder','p(x | z)','orange',19);out=d.block(1050,260,90,75,'Output x̂','','rose',16);d.connect(z,dec);d.connect(dec,out)
    kl=d.block(355,450,305,60,'KL regularization','q(z | x) toward N(0, I)','gray',17);d.line([(445,410),(445,450)],dashed=True)
    d.line([(515,200),(535,200),(535,430),(510,430),(510,450)],dashed=True)
    d.text(865,470,'Objective = reconstruction + KL',15,color=MUTED)
    return d

def gan():
    d=Diagram('Generative Adversarial Network','A generator and discriminator learn through an adversarial objective',1120,480)
    z=d.block(40,245,120,80,'Noise z','prior sample','gray',18);g=d.block(205,235,180,100,'Generator G','learned synthesis','blue',20);fake=d.block(435,245,140,80,'Fake sample','G(z)','purple',18);disc=d.block(650,235,190,100,'Discriminator D','shared real / fake judge','teal',20);score=d.block(900,245,170,80,'Real / fake','probability','orange',18)
    for a,b in [(z,g),(g,fake),(fake,disc),(disc,score)]:d.connect(a,b)
    real=d.block(660,115,170,65,'Real sample x','training data','rose',18);d.connect(real,disc,'down')
    d.line([(745,335),(745,405),(295,405),(295,335)],dashed=True)
    d.text(520,424,'Adversarial training feedback',14,color=MUTED)
    return d

def dcgan():
    d=Diagram('DCGAN','Convolutional synthesis and learned strided downsampling',1160,510)
    d.text(40,122,'GENERATOR',12,color=MUTED,anchor='start',weight=650)
    z=d.block(40,155,100,80,'Noise z','','gray',18);proj=d.block(185,155,180,80,'Project + reshape','4 × 4 feature map','purple',18);up=d.block(415,145,290,100,'Transposed convolutions','Spatial upsampling · BN + ReLU','blue',19);image=d.block(765,155,170,80,'RGB image','64 × 64 · Tanh','rose',18)
    for a,b in [(z,proj),(proj,up),(up,image)]:d.connect(a,b)
    d.text(40,298,'DISCRIMINATOR',12,color=MUTED,anchor='start',weight=650)
    image2=d.block(765,335,210,80,'Real or generated','image input','rose',18);down=d.block(405,325,300,100,'Strided convolutions','Downsampling · LeakyReLU + BN','teal',19);judge=d.block(160,335,190,80,'Sigmoid output','real / fake','orange',18)
    d.connect(image,image2,'down');d.connect(image2,down,'left');d.connect(down,judge,'left')
    d.text(560,460,'BN omitted at the generator output and discriminator input; no deterministic pooling.',13,color=MUTED)
    return d

def lstm():
    d=Diagram('LSTM · gated memory','Standard forget-gate variant: retain, write, then expose the memory state',1160,545)
    cprev=d.block(35,127,140,55,'cₜ₋₁','','gray',19);ct=d.block(1000,127,125,55,'cₜ','','teal',20)
    forget=d.op(325,155,'×');add=d.op(570,155,'+');d.line([(175,155),(307,155)]);d.line([(343,155),(552,155)]);d.line([(588,155),(1000,155)])
    f=d.block(270,315,110,64,'Forget fₜ','sigmoid','orange',18);i=d.block(440,315,110,64,'Input iₜ','sigmoid','orange',18);g=d.block(610,315,110,64,'Candidate ĝₜ','tanh','blue',16);o=d.block(820,315,110,64,'Output oₜ','sigmoid','orange',17)
    d.line([(325,315),(325,173)]);mulwrite=d.op(570,245,'×');d.line([(495,315),(495,245),(552,245)]);d.line([(665,315),(665,245),(588,245)]);d.line([(570,227),(570,173)])
    tanh=d.block(700,215,90,60,'tanh','','purple',18);mulout=d.op(875,245,'×');d.line([(745,155),(745,215)]);d.line([(790,245),(857,245)]);d.line([(875,315),(875,263)])
    ht=d.block(1000,217,125,55,'hₜ','','rose',20);d.line([(893,245),(1000,245)])
    inputs=d.block(35,425,170,60,'[xₜ, hₜ₋₁]','gate inputs','gray',18);d.line([(205,455),(875,455)],arrow=False)
    for x in [325,495,665,875]:d.line([(x,455),(x,379)])
    return d

def gru():
    d=Diagram('GRU · reset and update','Reset controls the candidate; update mixes previous and candidate states',1160,505)
    prev=d.block(40,115,145,60,'hₜ₋₁','','gray',20);inputs=d.block(40,270,170,70,'[xₜ, hₜ₋₁]','gate inputs','gray',18)
    reset=d.block(275,160,135,65,'Reset rₜ','sigmoid','orange',18);update=d.block(275,365,135,65,'Update zₜ','sigmoid','orange',18)
    d.line([(210,305),(242,305),(242,192),(275,192)]);d.line([(210,305),(242,305),(242,397),(275,397)])
    mul=d.op(475,192,'×');d.line([(410,192),(457,192)]);d.line([(185,145),(475,145),(475,174)])
    cand=d.block(540,155,180,100,'Candidate h̃ₜ','tanh(xₜ, rₜ ⊙ hₜ₋₁)','blue',20);d.line([(493,192),(540,192)]);d.line([(210,305),(505,305),(505,230),(540,230)]);d.text(450,290,'xₜ',14,color=MUTED)
    mix=d.block(800,265,215,100,'Update mixture','zₜ ⊙ hₜ₋₁ +\n(1 − zₜ) ⊙ h̃ₜ','teal',19);d.line([(720,205),(760,205),(760,296),(800,296)]);d.line([(185,145),(910,145),(910,265)]);d.line([(410,397),(900,397),(900,365)])
    out=d.block(1060,285,70,60,'hₜ','','rose',19);d.connect(mix,out)
    return d

def seq2seq():
    d=Diagram('Sequence-to-sequence · LSTM','Encode the source into a fixed-size state, then decode autoregressively',1220,490)
    enc=[];dec=[]
    for x,t in zip([65,235,405],['x_T','…','x_1']):
        b=d.block(x,235,120,75,'LSTM','encoder','blue',18);enc.append(b);tok=d.block(x,368,120,45,t,'','gray',17);d.connect(tok,b,'up')
    for a,b in zip(enc,enc[1:]):d.connect(a,b)
    state=d.block(570,235,130,75,'Context v','final state','purple',18);d.connect(enc[-1],state)
    for j,x in enumerate([745,915,1085]):
        b=d.block(x,235,100,75,'LSTM','decoder','teal',17);dec.append(b);tok=d.block(x,368,100,45,['BOS','y_1','y_2'][j],'','gray',16);d.connect(tok,b,'up');out=d.block(x,130,100,45,f'y_{j+1}','','rose',17);d.connect(b,out,'up')
    d.connect(state,dec[0])
    for a,b in zip(dec,dec[1:]):d.connect(a,b)
    d.text(290,440,'Reversed source order in the original setup',12,color=MUTED);d.text(965,440,'Previous target token → next prediction',12,color=MUTED)
    return d

def transformer():
    d=Diagram('Transformer · encoder–decoder','The original post-normalization architecture, with causal and cross attention',1420,640)
    d.text(250,119,'ENCODER × N',13,color=MUTED,anchor='start',weight=650)
    source=d.block(35,160,170,70,'Source tokens','Embed + position','gray',17);sa=d.block(250,160,155,70,'Self-attention','multi-head','blue',17);an1=d.block(440,160,105,70,'Add &\nNorm','','orange',17);ff=d.block(580,160,120,70,'FFN','','purple',18);an2=d.block(735,160,105,70,'Add &\nNorm','','orange',17);memory=d.block(890,160,135,70,'Memory','encoder states','teal',18)
    for a,b in [(source,sa),(sa,an1),(an1,ff),(ff,an2),(an2,memory)]:d.connect(a,b)
    d.line([(225,195),(225,260),(492,260),(492,230)]);d.line([(562,195),(562,280),(787,280),(787,230)])
    d.text(250,357,'DECODER × N',13,color=MUTED,anchor='start',weight=650)
    target=d.block(35,395,170,70,'Shifted targets','Embed + position','gray',17);msa=d.block(250,395,155,70,'Masked self-attn','causal','blue',16);dan1=d.block(440,395,105,70,'Add &\nNorm','','orange',17);cross=d.block(580,395,150,70,'Cross-attention','Q: decoder · K,V: memory','teal',17);dan2=d.block(765,395,105,70,'Add &\nNorm','','orange',17);dff=d.block(905,395,120,70,'FFN','','purple',18);dan3=d.block(1060,395,105,70,'Add &\nNorm','','orange',17);head=d.block(1200,395,180,70,'Linear + Softmax','next-token probabilities','rose',17)
    for a,b in [(target,msa),(msa,dan1),(dan1,cross),(cross,dan2),(dan2,dff),(dff,dan3),(dan3,head)]:d.connect(a,b)
    d.line([(957,230),(957,320),(655,320),(655,395)]);d.text(895,304,'K, V',13,color=MUTED)
    d.line([(225,430),(225,510),(492,510),(492,465)]);d.line([(562,430),(562,530),(817,530),(817,465)]);d.line([(887,430),(887,550),(1112,550),(1112,465)])
    d.text(705,588,'Residual paths surround every attention / FFN sublayer; Add & Norm follows each sublayer.',13,color=MUTED)
    return d

def bert():
    d=Diagram('BERT · bidirectional encoder','Token, segment and position embeddings feed encoder-only Transformer blocks',1160,470)
    tokens=d.block(35,230,195,90,'Input sequence','[CLS] A [SEP] B [SEP]','gray',18);emb=d.block(280,230,205,90,'Embedding sum','Token + segment + position','blue',19);enc=d.block(545,230,240,90,'Bidirectional encoder','Self-attention + FFN × L','teal',20)
    d.connect(tokens,emb);d.connect(emb,enc)
    cls=d.block(895,145,225,75,'[CLS] head','NSP / sequence classification','orange',18);mlm=d.block(895,335,225,75,'Token head','Masked language modeling','purple',18)
    d.line([(785,275),(840,275),(840,182),(895,182)]);d.line([(785,275),(840,275),(840,372),(895,372)])
    d.text(835,153,'CLS state',12,color=MUTED);d.text(835,408,'masked states',12,color=MUTED)
    d.text(405,380,'Left and right context are visible at every encoder layer.',14,color=MUTED)
    return d

def vit():
    d=Diagram('Vision Transformer · ViT','Patch embeddings + a learned class token + position embeddings',1240,450)
    image=d.pixels(35,210,125);d.text(97,362,'Image patches',15)
    proj=d.block(215,230,185,85,'Linear projection','one vector per patch','blue',18);d.line([(160,272),(215,272)])
    for i,label in enumerate(['CLS','p₁','p₂','p₃','…']):d.block(475+i*56,244,46,58,label,'','rose' if i==0 else 'blue',16)
    d.line([(400,272),(475,272)]);d.text(610,328,'Token sequence',14,color=MUTED)
    cls=d.block(453,120,105,55,'Class token','','rose',16);d.line([(498,175),(498,244)])
    pos=d.block(605,120,165,55,'Position embeddings','','purple',16);d.line([(687,175),(687,210),(770,210),(770,254)])
    enc=d.block(810,230,200,85,'Transformer encoder','Self-attention + MLP × L','teal',18);head=d.block(1060,230,150,85,'MLP head','CLS state','orange',18)
    d.op(770,272,'+');d.line([(745,272),(752,272)],arrow=False);d.line([(788,272),(810,272)]);d.connect(enc,head)
    d.text(620,385,'Only the encoded class-token state is sent to the image classifier.',14,color=MUTED)
    return d

def swin():
    d=Diagram('Swin Transformer','Hierarchical stages with alternating regular and shifted-window attention',1400,560)
    emb=d.block(35,175,180,105,'Patch embedding','4 × 4 partition + linear','gray',18);prev=emb
    positions=[260,570,880,1190]
    for i,x in enumerate(positions):
        b=d.block(x,175,175,105,f'Stage {i+1}',f'W-MSA / SW-MSA\nH/{4*2**i} · {2**i}C','teal' if i%2==0 else 'blue',20)
        if i==0:d.connect(prev,b)
        else:
            merge=d.block(x-120,195,80,65,'Merge','2 × 2','purple',16);d.connect(prev,merge);d.connect(merge,b)
        prev=b
    def windows(x,y,shift):
        for r in range(4):
            for c in range(4):
                region=((r+(1 if shift else 0))//2*3+(c+(1 if shift else 0))//2)%4
                fill=['#d6e6fb','#dfefd6','#f5dfdf','#e4dcf4'][region]
                d.parts.append(f'<rect x="{x+c*29}" y="{y+r*29}" width="26" height="26" rx="3" fill="{fill}" stroke="#ffffff"/>')
    windows(230,362,False);windows(520,362,True);d.text(286,496,'Regular windows',14);d.text(576,496,'Shifted windows',14);d.line([(365,417),(490,417)]);d.text(427,392,'shift',13,color=MUTED)
    d.text(970,392,'Alternation links neighboring windows.',16,weight=600);d.text(970,422,'Patch merging reduces token count by 4',14,color=MUTED);d.text(970,447,'and doubles the channel dimension.',14,color=MUTED)
    return d

def ddpm():
    d=Diagram('DDPM · diffusion and denoising','Fixed forward noising, followed by a learned time-conditioned reverse process',1180,595)
    xs=[75,365,655,945]
    for i,(x,label) in enumerate(zip(xs,['Clean x₀','Noised x₁','Noisy xₜ','Gaussian x_T'])):
        d.pixels(x,135,115,noise=i/3);d.text(x+57.5,276,label,16)
        if i<3:d.line([(x+115,192),(xs[i+1],192)]);d.text(x+202,168,'q: add noise',12,color=MUTED)
    xt=d.block(920,375,170,80,'xₜ','start from x_T ~ N(0,I)','gray',18);net=d.block(625,365,235,100,'Noise predictor','Time-conditioned U-Net','blue',19);step=d.block(345,375,220,80,'Reverse update','pθ(xₜ₋₁ | xₜ)','teal',19);out=d.block(75,375,210,80,'xₜ₋₁','one less-noisy sample','rose',19)
    d.line([(1002,250),(1002,375)]);d.connect(xt,net,'left');d.connect(net,step,'left');d.connect(step,out,'left')
    d.text(744,330,'time t',14,color=MUTED);d.line([(744,342),(744,365)]);d.text(595,349,'εθ',15,color=MUTED)
    d.line([(180,455),(180,510),(1005,510),(1005,455)],dashed=True);d.text(592,533,'Repeat reverse steps: t = T, …, 1 → generated x₀',14,color=MUTED)
    return d


SPECS = [
    ('ARCH001','lenet5','LeNet-5 经典卷积网络','LeNet-5',1998,'经典卷积网络',lenet,'https://bottou.org/papers/lecun-98h','Gradient Based Learning Applied to Document Recognition','LeNet-5 has C1/S2/C3/S4/C5/F6 and ten Euclidean RBF output units; subsampling is trainable.',['卷积','CNN','数字识别','subsampling','RBF']),
    ('ARCH002','alexnet','AlexNet 图像分类网络','AlexNet',2012,'经典卷积网络',alexnet,'https://papers.nips.cc/paper_files/paper/2012/hash/c399862d3b9d6b76c8436e924a68c45b-Abstract.html','ImageNet Classification with Deep Convolutional Neural Networks','Five convolutional layers and three fully connected layers; ReLU, selected max-pooling, dropout.',['卷积','CNN','图像分类','ImageNet','ReLU']),
    ('ARCH003','vgg16','VGG-16 深层卷积网络','VGG-16',2014,'经典卷积网络',vgg,'https://arxiv.org/abs/1409.1556','Very Deep Convolutional Networks for Large-Scale Image Recognition','Configuration D uses 2/2/3/3/3 convolution groups of 64/128/256/512/512 channels, five pools and three FC layers.',['卷积','CNN','图像分类','3x3','VGG']),
    ('ARCH004','googlenet','GoogLeNet 多尺度 Inception 网络','GoogLeNet / Inception-v1',2014,'经典卷积网络',googlenet,'https://arxiv.org/abs/1409.4842','Going Deeper with Convolutions','Inception-v1 concatenates 1x1, 3x3, 5x5 and pooling branches with dimensionality reduction; nine modules and two training-only auxiliary heads.',['卷积','多尺度','Inception','GoogLeNet','并行分支']),
    ('ARCH005','resnet18','ResNet-18 残差网络','ResNet-18',2015,'经典卷积网络',resnet,'https://arxiv.org/abs/1512.03385','Deep Residual Learning for Image Recognition','Four stages of 2 basic blocks each with 64/128/256/512 channels; shortcuts add x to F(x), adapting dimensions when needed.',['卷积','残差','skip connection','ResNet','图像分类']),
    ('ARCH006','densenet','DenseNet 稠密连接网络','DenseNet',2016,'经典卷积网络',densenet,'https://arxiv.org/abs/1608.06993','Densely Connected Convolutional Networks','Each dense layer receives concatenated features from all preceding layers; transition layers connect dense blocks.',['稠密连接','特征复用','拼接','DenseNet','CNN']),
    ('ARCH007','mobilenetv2','MobileNetV2 倒残差网络','MobileNetV2',2018,'轻量化网络',mobilenet,'https://arxiv.org/abs/1801.04381','MobileNetV2: Inverted Residuals and Linear Bottlenecks','1x1 nonlinear expansion, 3x3 depthwise nonlinear filtering and linear 1x1 projection; thin shortcut only at stride 1 with matching channels.',['轻量化','移动端','倒残差','深度可分离','线性瓶颈']),
    ('ARCH008','unet','U-Net 编码解码分割网络','U-Net',2015,'分割与编码解码',unet,'https://arxiv.org/abs/1505.04597','U-Net: Convolutional Networks for Biomedical Image Segmentation','Contracting and expanding paths; up-convolution followed by concatenation with corresponding cropped encoder features.',['分割','编码器','解码器','跳连','U-Net','crop concat']),
    ('ARCH009','fcn8s','FCN-8s 全卷积分割网络','FCN-8s',2014,'分割与编码解码',fcn,'https://arxiv.org/abs/1411.4038','Fully Convolutional Networks for Semantic Segmentation','FCN-8s fuses upsampled stride-32 scores with pool4 stride-16 scores, then pool3 stride-8 scores, then upsamples to pixels.',['语义分割','全卷积','FCN','上采样','跳跃融合']),
    ('ARCH010','autoencoder','Autoencoder 自编码器','Autoencoder',2006,'生成与潜变量',autoencoder,'https://www.cs.utoronto.ca/~hinton/absps/science.pdf','Reducing the Dimensionality of Data with Neural Networks','An encoder maps input to a compact code and a decoder reconstructs the input; a conceptual deep autoencoder, not the exact 2006 layer schedule.',['自编码器','降维','重建','编码解码','潜空间']),
    ('ARCH011','vae','VAE 变分自编码器','Variational Autoencoder',2013,'生成与潜变量',vae,'https://arxiv.org/abs/1312.6114','Auto-Encoding Variational Bayes','Encoder predicts distribution parameters; Gaussian reparameterization z=mu+sigma*epsilon; decoder and KL regularization to a prior.',['VAE','变分','自编码器','重参数化','潜空间','KL']),
    ('ARCH012','gan','GAN 生成对抗网络','Generative Adversarial Network',2014,'生成与潜变量',gan,'https://arxiv.org/abs/1406.2661','Generative Adversarial Nets','Generator maps prior noise to samples; discriminator judges real and generated samples in an adversarial game.',['GAN','生成','对抗','生成器','判别器']),
    ('ARCH013','dcgan','DCGAN 卷积生成对抗网络','DCGAN',2015,'生成与潜变量',dcgan,'https://arxiv.org/abs/1511.06434','Unsupervised Representation Learning with Deep Convolutional Generative Adversarial Networks','Generator learns upsampling with transposed convolutions, BN/ReLU and Tanh output; discriminator uses strided convolutions and LeakyReLU.',['DCGAN','GAN','转置卷积','生成器','判别器','图像生成']),
    ('ARCH014','lstm','LSTM 门控记忆单元','Long Short-Term Memory',1997,'循环与序列网络',lstm,'https://www.bioinf.jku.at/publications/older/2604.pdf','Long Short-Term Memory','Diagram explicitly uses the standard forget-gate extension introduced by Gers et al. in 2000, not the exact 1997 input/output-gate-only cell.',['LSTM','循环网络','RNN','遗忘门','输入门','输出门','时序预测']),
    ('ARCH015','gru','GRU 重置与更新门控单元','Gated Recurrent Unit',2014,'循环与序列网络',gru,'https://arxiv.org/abs/1406.1078','Learning Phrase Representations using RNN Encoder-Decoder for Statistical Machine Translation','Reset gate modulates previous state in the candidate; update gate mixes previous and candidate states using the original Cho convention.',['GRU','循环网络','RNN','重置门','更新门','时序预测']),
    ('ARCH016','seq2seq','Seq2Seq LSTM 编码解码网络','Sequence-to-sequence LSTM',2014,'循环与序列网络',seq2seq,'https://arxiv.org/abs/1409.3215','Sequence to Sequence Learning with Neural Networks','LSTM encoder reads a reversed source sequence into a fixed-size final state; LSTM decoder is conditioned on it and previous target tokens; no attention.',['Seq2Seq','LSTM','编码器','解码器','机器翻译','序列到序列']),
    ('ARCH017','transformer','Transformer 编码器解码器','Transformer encoder-decoder',2017,'Transformer 架构',transformer,'https://arxiv.org/abs/1706.03762','Attention Is All You Need','Encoder has self-attention/FFN; decoder adds masked self-attention and encoder cross-attention; original post-norm residual structure.',['Transformer','自注意力','交叉注意力','因果掩码','编码器','解码器']),
    ('ARCH018','bert','BERT 双向 Transformer 编码器','BERT',2018,'Transformer 架构',bert,'https://arxiv.org/abs/1810.04805','BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding','Encoder-only bidirectional Transformer; token/segment/position embeddings; CLS sequence head and masked-language-model token head.',['BERT','双向','Transformer','预训练','MLM','NSP','自然语言']),
    ('ARCH019','vit','ViT 视觉 Transformer','Vision Transformer',2020,'Transformer 架构',vit,'https://arxiv.org/abs/2010.11929','An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale','Image patches are linearly projected; a learned class token is prepended, position embeddings added, and encoded class state feeds the classifier.',['ViT','视觉Transformer','图像分块','class token','patch embedding','图像分类']),
    ('ARCH020','swin','Swin 层次化窗口 Transformer','Swin Transformer',2021,'Transformer 架构',swin,'https://arxiv.org/abs/2103.14030','Swin Transformer: Hierarchical Vision Transformer using Shifted Windows','Alternating regular/shifted-window self-attention; patch merging groups 2x2 tokens, reduces token count fourfold and doubles channels.',['Swin','窗口注意力','移位窗口','层次化','patch merging','视觉Transformer']),
    ('ARCH021','ddpm','DDPM 扩散与反向去噪','Denoising Diffusion Probabilistic Model',2020,'扩散与生成',ddpm,'https://arxiv.org/abs/2006.11239','Denoising Diffusion Probabilistic Models','A fixed Gaussian forward process adds noise; a time-conditioned learned noise predictor supports iterative reverse sampling from Gaussian noise.',['DDPM','扩散','Diffusion','去噪','噪声预测','U-Net','生成模型']),
]


def generate():
    OUT.mkdir(parents=True,exist_ok=True);BACKUP.mkdir(parents=True,exist_ok=True)
    assets=[]
    for ident,slug,name,english,year,category,draw,url,title,facts,tags in SPECS:
        meta={'source_url':url,'source_title':title,'facts':facts}
        if ident=='ARCH014':meta['footer']='Concept schematic · standard forget-gate variant (Gers et al., 2000) · original artwork / MIT'
        d=draw();svg=d.svg(meta);raw=svg.encode('utf-8');filename=f'{ident}_{slug}.svg';(OUT/filename).write_bytes(raw)
        xml=ET.fromstring(raw)
        assert not any(e.tag.endswith('image') for e in xml.iter()),ident
        assert any(e.tag.endswith('text') for e in xml.iter()),ident
        path='assets/architectures/'+filename
        note=SCHEMATIC_NOTE
        if ident=='ARCH014':note+=' LSTM 图示采用 2000 年引入遗忘门后的常用变体，不等同于 1997 年原始单元。'
        item={'id':ident,'name':name,'english':english,'tags':['经典架构','原创示意','深度学习','模型结构图',english,*tags],'category':category,'type':'architecture','architecture':True,'style':'原创 · 架构示意','pack':'original-architectures','featured':True,'preview':path,'svg':path,'png':'','pdf':'','source_url':url,'source_title':title,'year':year,'figure':'概念重绘（原创布局）','license':'MIT','license_note':LICENSE_NOTE,'license_notes':LICENSE_NOTE,'license_url':'licenses/original-architectures-LICENSE.txt','svg_kind':'vector','svg_note':note,'description':LICENSE_NOTE+' '+note,'usage':'用于论文结构图、模型对比、教学及技术说明；可编辑节点、颜色、标签和连接箭头。','width':d.w,'height':d.h,'has_alpha':True,'available':True,'source_only':False,'facts_checked':facts,'verified_at':'2026-10-09','operations':'用标准库 SVG 元素独立绘制；没有复制、裁剪或嵌入原论文图像。','hashes':{'svg':hashlib.sha256(raw).hexdigest()},'bytes':{'svg':len(raw)}}
        if ident=='ARCH014':item['additional_sources']=[{'title':'Learning to Forget: Continual Prediction with LSTM','year':2000,'url':'https://doi.org/10.1162/089976600300015015'}]
        assets.append(item)
    manifest={'version':1,'generated_at':'2026-10-09','count':len(assets),'original_artwork':True,'license':'MIT','note':LICENSE_NOTE,'assets':assets}
    (BACKUP/'original-architectures-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Generated {len(assets)} editable, transparent SVG diagrams. Manifest: {BACKUP.name}/original-architectures-manifest.json')
    return assets


def render_qa(assets):
    # This local cache is optional and intentionally excluded from a public clone.
    optional_cache=ROOT/'.local-backup/build-cache/icon_library/pydeps'
    if optional_cache.exists():sys.path.insert(0,str(optional_cache))
    try:
        import resvg_py
        from PIL import Image, ImageDraw, ImageFont
        import io
    except ImportError as exc:
        raise SystemExit('Optional QA requires: pip install resvg-py Pillow') from exc
    qa=BACKUP/'architecture-qa';qa.mkdir(parents=True,exist_ok=True)
    renders=[]
    for a in assets:
        svg=(ROOT/'dist'/a['svg']).read_text(encoding='utf-8')
        raw=resvg_py.svg_to_bytes(svg_string=svg,width=1600,height=round(1600*a['height']/a['width']))
        p=qa/(a['id']+'.png');p.write_bytes(raw)
        img=Image.open(io.BytesIO(raw)).convert('RGBA')
        assert img.getchannel('A').getpixel((0,0))==0,'Canvas must be transparent'
        renders.append((a,img))
    columns=3;cellw=800;cellh=435
    sheet=Image.new('RGB',(columns*cellw,70+math.ceil(len(assets)/columns)*cellh),'#f4f6f9');draw=ImageDraw.Draw(sheet)
    try:font=ImageFont.truetype('Arial.ttf',24);small=ImageFont.truetype('Arial.ttf',18)
    except OSError:font=ImageFont.load_default();small=font
    draw.text((25,20),'Original deep-learning architecture schematics | editable SVG | MIT',font=font,fill='#34465d')
    for i,(a,img) in enumerate(renders):
        x=(i%columns)*cellw;y=70+(i//columns)*cellh
        tile=Image.new('RGBA',(cellw-22,cellh-50),'white');img.thumbnail((cellw-50,cellh-75),Image.Resampling.LANCZOS);tile.alpha_composite(img,((tile.width-img.width)//2,(tile.height-img.height)//2));sheet.paste(tile.convert('RGB'),(x+11,y+10))
        draw.text((x+24,y+cellh-29),a['id']+' / '+a['english'],font=small,fill='#6e7e92')
    (ROOT/'docs').mkdir(exist_ok=True);sheet.save(ROOT/'docs/architectures-preview.png')
    (qa/'qa-report.json').write_text(json.dumps({'count':len(assets),'renderer':'resvg_py','all_xml_valid':True,'all_canvas_corners_transparent':True,'all_images_embedded':False,'contact_sheet':'docs/architectures-preview.png'},indent=2),encoding='utf-8')
    print('Rendered individual QA previews and docs/architectures-preview.png')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--qa',action='store_true',help='Render optional PNG contact sheet (resvg-py and Pillow).');args=parser.parse_args()
    result=generate()
    if args.qa:render_qa(result)
