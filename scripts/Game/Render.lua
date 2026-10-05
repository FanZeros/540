-- 图集裁剪与脚底锚点，纯像素绘制接口。
local C = require "Game.Config"
local V = {}
V.__index=V
function V.New(vg)
    local v=setmetatable({},V); v:init(vg); return v
end
function V:init(vg)
    self.vg=vg; self.images={}; self.scale=1; self.ox=0; self.oy=0; self.dpr=1
    for _,a in ipairs(C.images) do
        local id=nvgCreateImage(vg,a[1],NVG_IMAGE_NEAREST)
        assert(id>0,"图片加载失败："..a[1])
        self.images[a[1]]={id=id,w=a[2],h=a[3],count=a[4]}
        print("[素材] 图片加载",a[1],a[4],"帧")
    end
end
function V:Rect(x,y,w,h,r,g,b,a)
    nvgBeginPath(self.vg); nvgRect(self.vg,x,y,w,h)
    nvgFillColor(self.vg,nvgRGBA(r,g,b,a or 255)); nvgFill(self.vg)
end
function V:Sprite(path,frame,x,y,dir,alpha,tint)
    local a=self.images[path]
    if not a then return end
    local f=math.max(0,math.min(a.count-1,math.floor(frame)))
    local ctx=self.vg
    nvgSave(ctx); nvgTranslate(ctx,math.floor(x),math.floor(y))
    if dir and dir<0 then nvgScale(ctx,-1,1) end
    nvgIntersectScissor(ctx,-a.w/2,-a.h,a.w,a.h)
    nvgBeginPath(ctx); nvgRect(ctx,-a.w/2,-a.h,a.w,a.h)
    if tint then
        nvgFillPaint(ctx,nvgImagePatternTinted(ctx,-a.w/2-f*a.w,-a.h,a.w*a.count,a.h,0,a.id,nvgRGBA(tint[1],tint[2],tint[3],math.floor((alpha or 1)*255))))
    else
        nvgFillPaint(ctx,nvgImagePattern(ctx,-a.w/2-f*a.w,-a.h,a.w*a.count,a.h,0,a.id,alpha or 1))
    end
    nvgFill(ctx); nvgRestore(ctx)
end
function V:Player(p,alpha,tint)
    local count=C.playerFrames[p.anim] or 5
    local f=math.floor(p.animTime*(C.playerFPS[p.anim] or 12))
    if p.anim=="Hit" or p.anim=="Slash" or p.anim=="Land" or p.anim=="Jump" then f=math.min(count-1,f) else f=f%count end
    self:Sprite("武士零主角/"..p.anim..".png",f,p.x,p.y,p.dir,alpha,tint)
end
function V:Enemy(e)
    local tags=e.kind=="melee" and C.meleeTags or C.rangedTags
    local tag=tags[e.anim] or tags.Idle
    local count=tag[2]-tag[1]+1
    local frame=math.floor(e.animTime/(e.anim=="Walk" and e.kind=="ranged" and 0.13 or 0.1))
    if e.dead then frame=math.min(count-1,frame) else frame=frame%count end
    self:Sprite(e.kind=="melee" and "大壮动作.png" or "盾牌男.png",tag[1]+frame,e.x,e.y,e.dir,e.state=="spawn" and math.min(1,e.timer*3) or 1)
    if not e.dead and (e.state=="switch" or e.state=="shield") then
        local t=0.5+math.sin(e.timer*25)*0.5
        self:Rect(e.x-2,e.y-52,4,5,255,65,97,math.floor(t*255))
        self:Rect(e.x-2,e.y-44,4,2,255,180,100,255)
    end
end
function V:Draw(w)
    local ctx=self.vg
    local physW,physH=graphics:GetWidth(),graphics:GetHeight()
    self.dpr=math.max(1,graphics:GetDPR())
    local logicalW,logicalH=physW/self.dpr,physH/self.dpr
    self.scale=math.min(logicalW/C.WIDTH,logicalH/C.HEIGHT)
    self.ox=(logicalW-C.WIDTH*self.scale)/2; self.oy=(logicalH-C.HEIGHT*self.scale)/2
    nvgBeginFrame(ctx,logicalW,logicalH,self.dpr)
    self:Rect(0,0,logicalW,logicalH,5,7,16)
    nvgSave(ctx); nvgTranslate(ctx,self.ox,self.oy); nvgScale(ctx,self.scale,self.scale)
    nvgScissor(ctx,0,0,C.WIDTH,C.HEIGHT); nvgShapeAntiAlias(ctx,0)
    local s=w.view or w
    local t=w.mode=="title" and w.modeTime or (s.worldTime or w.time)
    if s.shake>0 then nvgTranslate(ctx,math.sin(t*170)*s.shake,math.cos(t*139)*s.shake*0.45) end
    self:Sprite("Background.png",0,338,288,1,1)
    local tint=C.chapters[w.level].tint
    self:Rect(0,0,676,246,tint[1],tint[2],tint[3],20)
    -- 窗口电流、雨丝与地面倒影，仍是手写原始像素。
    for i=1,34 do
        local x=(i*97+t*13)%676; local y=(i*47+t*105)%242
        self:Rect(math.floor(x),math.floor(y),1,4,72,157,183,55)
    end
    local flicker=0.7+math.sin(t*2.4)*0.15
    self:Rect(1,245,674,1,66,218,229,math.floor(65*flicker))
    for _,platform in ipairs(w.platforms) do self:Sprite("Platform.png",0,platform.x+48,platform.y+8,1,1) end
    for _,portal in ipairs(w.portals) do
        self:Sprite("Portal.png",0,portal.x,246,1,0.7+0.25*math.sin(t*7))
        for j=1,6 do self:Rect(portal.x-12,196+j*7,24,1,58,235,249,math.floor(90+70*math.sin(t*6+j))) end
    end
    for _,o in ipairs(s.objects) do
        if not o.broken then self:Sprite(o.kind=="barrel" and "Barrel.png" or "Crate.png",0,o.x,o.y,1,1) end
    end
    for _,stain in ipairs(s.stains) do
        if stain.wall then
            self:Rect(stain.x-stain.r,stain.y-stain.r,stain.r*2,stain.r,119,16,56,205)
            self:Rect(stain.x,stain.y,1,stain.drip,176,23,69,195)
        else self:Rect(stain.x-stain.r,245,stain.r*2,2,193,24,67,220); self:Rect(stain.x-stain.r*0.6,248,stain.r*1.2,1,87,16,44,180) end
    end
    for i=w.spawnIndex,math.min(#w.schedule,w.spawnIndex+2) do
        local spawn=w.schedule[i]; local remain=spawn.time-w.time
        if remain>0 and remain<0.85 and w.mode=="playing" then
            local x=C.DOORS[spawn.door]
            self:Rect(x-15,195,30,50,220,32,100,math.floor((1-remain/0.85)*65))
            self:Rect(x-15,193,30,2,255,47,104,220)
        end
    end
    for _,e in ipairs(s.enemies) do if e.dead then self:Enemy(e) end end
    for _,e in ipairs(s.enemies) do if not e.dead then self:Enemy(e) end end
    for _,trail in ipairs(s.trails) do
        local ghost={x=trail.x,y=trail.y,dir=trail.dir,anim=trail.anim,animTime=trail.time}
        self:Player(ghost,trail.life/0.22*0.24,{40,225,240})
    end
    self:Player(s.player,1)
    for _,b in ipairs(s.bullets) do
        local dir=b.vx>=0 and 1 or -1
        self:Rect(b.x-dir*13,b.y-1,13,1,b.friendly and 52 or 255,b.friendly and 231 or 150,b.friendly and 242 or 68,150)
        self:Sprite("Bullet.png",0,b.x,b.y+4,dir,1,b.friendly and {110,255,255} or nil)
    end
    local colors={blood={221,26,76},cyan={62,243,255},fire={255,183,74},wood={163,112,65}}
    for _,p in ipairs(s.particles) do
        local col=colors[p.color] or colors.cyan
        self:Rect(math.floor(p.x),math.floor(p.y),math.ceil(p.size),math.ceil(p.size),col[1],col[2],col[3],math.floor(math.min(1,p.life*3)*255))
    end
    for _,f in ipairs(s.fx) do
        local spec=C.fx[f.kind]
        self:Sprite(spec[1],math.min(spec[4]-1,math.floor(f.time/0.05)),f.x,f.y+spec[3]/2,f.dir,1)
    end
    if s.slow and w.mode=="playing" then
        self:Rect(0,0,676,288,20,116,139,27)
        self:Rect(0,0,676,2,64,244,255,150); self:Rect(0,286,676,2,64,244,255,150)
    end
    if s.flash>0 then self:Rect(0,0,676,288,220,248,255,math.floor(math.min(0.5,s.flash*3)*255)) end
    if w.mode=="rewind" then
        for y=0,288,4 do self:Rect(0,y,676,1,42,221,230,65) end
        self:Rect(0,0,676,288,37,93,155,40)
    end
    if w.mode=="title" then self:Rect(0,0,676,288,7,9,26,125) end
    nvgRestore(ctx); nvgEndFrame(ctx)
end
function V:Dispose()
    for _,a in pairs(self.images) do nvgDeleteImage(self.vg,a.id) end
end
return V
