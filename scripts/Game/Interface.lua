-- PixelForge 硬边、高对比主题；仅剧情、教学、结算使用 UI 组件。
local UI = require "urhox-libs/UI"
local C = require "Game.Config"
local I = {}
I.__index=I
function I.New(w)
    local i=setmetatable({},I); i:init(w); return i
end
function I:init(w)
    self.world=w; self.lastMode=""; self.lastLevel=0
    local theme=UI.Theme.ExtendTheme(UI.Theme.defaultTheme,{
        fonts={{family="sans",weights={normal="Fonts/MiSans-Regular.ttf"}}},
        colors={primary={33,189,174,255},primaryHover={61,208,193,255},primaryPressed={25,168,153,255},
            background={15,15,35,255},surface={27,27,58,255},text={240,240,240,255},textSecondary={160,160,192,255}},
        componentDefaults={borderRadius=0},
        components={Button={borderRadius=0,borderWidth=2,boxShadow={{x=3,y=3,blur=0,color={10,10,26,204}},{x=-1,y=-1,blur=0,color={255,255,255,48}}}}}})
    UI.Init({theme=theme,scale=UI.Scale.DEFAULT})
    self:Refresh()
end
local function label(text,size,color)
    return UI.Label{text=text,fontSize=size,fontColor=color or {231,242,249,255},flexShrink=1,whiteSpace="normal"}
end
function I:Refresh()
    local w=self.world
    self.lastMode=w.mode; self.lastLevel=w.level
    if w.mode=="playing" and w.time<5 then self.captionExpired=0 end
    local children={}
    if w.mode=="title" then
        children={UI.Panel{width="100%",height="100%",justifyContent="center",alignItems="center",children={
            UI.Panel{width="85%",maxWidth=640,padding=28,gap=12,backgroundColor={10,14,34,235},children={
                label("ZERO HOUR  /  03:17 AM",12,{65,229,235,255}),
                label("零 刻",48),
                label("有人删掉了你的未来。",18,{255,74,132,255}),
                label("雨夜，十层安保，一把刀。让飞来的子弹回到枪口，让死亡回到尚未发生的那一秒。",13),
                UI.Button{text="进入雨夜",width=192,height=44,marginTop=8,onClick=function() w:Start(); w.audio:Begin() end},
                label("一击即死  ·  十段记忆  ·  时间在你手里",10,{154,165,192,255}),
            }}
        }}}
    elseif w.mode=="playing" then
        children={UI.Panel{position="absolute",top=14,left=18,right=18,pointerEvents="none",children={
            label(string.format("%02d / 10   %s",w.level,C.chapters[w.level].name),12,{88,229,237,245}),
        }}}
        if w.time<5 then children[#children+1]=UI.Panel{position="absolute",top=42,left=18,right=18,pointerEvents="none",
            children={label(C.chapters[w.level].story,10,{193,186,210,240})}} end
        if w.level==1 then
            children[#children+1]=UI.Panel{position="absolute",bottom=12,left=18,right=18,pointerEvents="none",
                backgroundColor={8,13,30,200},padding=8,children={
                    label("移动 A / D 或 ← / →   ·   跳跃 空格 / W   ·   挥刀 J / 左键",10),
                    label("翻滚 K / Shift   ·   按住 L / 右键放慢时间   ·   挥刀可以弹反子弹",10,{89,223,233,255}),
                }}
        end
    elseif w.mode=="replay" or w.mode=="rewind" then
        children={UI.Panel{position="absolute",top=16,left=18,right=18,pointerEvents="none",children={
            label(w.mode=="replay" and "精彩回放   ▶   1×" or "时光倒流   ◀   1×",14,{73,237,243,255})}}}
    elseif w.mode=="failed" or w.mode=="complete" then
        local failed=w.mode=="failed"
        children={UI.Panel{width="100%",height="100%",justifyContent="center",alignItems="center",children={
            UI.Panel{width="85%",maxWidth=490,padding=26,gap=12,backgroundColor={10,14,32,240},children={
                label(failed and "这不是结局。" or "记忆已清空。",27,failed and {255,77,127,255} or {69,232,226,255}),
                label(failed and ("死因："..(w.cause or "未知").."  /  当前关卡 "..w.level) or
                    string.format("斩杀 %d   弹反 %d   翻滚 %d",w.stats.kills,w.stats.parries,w.stats.rolls),13),
                label(failed and "按 R，让时间回到这一层。" or "按 R 重演这一层；点击下方继续。",12),
                UI.Button{text=failed and "倒转当前关卡" or (w.level==10 and "走向黎明" or "继续下一段记忆"),
                    width=220,height=44,onClick=function() if failed then w:Restart() else w:Next() end end},
            }}
        }}}
    elseif w.mode=="ending" then
        children={UI.Panel{width="100%",height="100%",justifyContent="center",alignItems="center",children={
            UI.Panel{width="85%",maxWidth=560,padding=30,gap=16,backgroundColor={9,14,32,230},children={
                label("天亮了。",34,{74,237,227,255}),
                label("03:18 AM  /  十段记忆全部完成",14),
                label("电话不再响起。你第一次不知道下一秒会发生什么。那就是自由。",16),
                label("ZERO HOUR   —   终",12,{165,158,199,255}),
            }}
        }}}
    end
    UI.SetRoot(UI.Panel{width="100%",height="100%",pointerEvents="box-none",children=children},true)
end
function I:Update()
    local w=self.world
    if self.lastMode~=w.mode or self.lastLevel~=w.level then self:Refresh() end
    -- 章节字幕在5秒后撤掉，只重建一次而非每帧重建。
    if w.mode=="playing" and w.time>5 and self.lastMode=="playing" and self.captionExpired~=w.level then
        self.captionExpired=w.level; self:Refresh()
    end
end
function I:Dispose() UI.Shutdown() end
return I
