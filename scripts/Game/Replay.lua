-- 记录可见快照，不回放 AI/碰撞，避免二次伤害和随机分歧。
local R = {}
local function copy(t)
    local result={}
    for k,v in pairs(t) do result[k]=type(v)=="table" and copy(v) or v end
    return result
end
function R.New() return {frames={},accum=0,worldCursor=0,realCursor=0,index=1} end
function R.Capture(w,force)
    local r=w.replay
    r.accum=r.accum+(w.lastRealDT or w.lastWorldDT)
    if not force and r.accum<1/30 then return end
    r.accum=0
    local f={worldTime=w.time,realTime=w.realTime,player=copy(w.player),enemies=copy(w.enemies),
        bullets=copy(w.bullets),fx=copy(w.fx),particles=copy(w.particles),stains=copy(w.stains),
        objects=copy(w.objects),trails=copy(w.trails),shake=w.shake,flash=w.flash,slow=w.slow}
    r.frames[#r.frames+1]=f
    -- 最多90秒的实际时间录像。绝不在每帧保存引擎对象。
    if #r.frames>2700 then table.remove(r.frames,1) end
end
function R.Begin(w,reverse)
    local r=w.replay
    if #r.frames==0 then R.Capture(w,true) end
    r.reverse=reverse
    r.index=reverse and #r.frames or 1
    r.worldCursor=r.frames[1].worldTime
    r.realCursor=r.frames[reverse and #r.frames or 1].realTime
    w.view=r.frames[r.index]
end
function R.Update(w,dt)
    local r=w.replay
    if #r.frames==0 then return true end
    if r.reverse then
        r.realCursor=r.realCursor-dt
        while r.index>1 and r.frames[r.index].realTime>r.realCursor do r.index=r.index-1 end
        w.view=r.frames[r.index]
        return r.index==1 or r.realCursor<r.frames[#r.frames].realTime-4
    end
    -- 1×指录像实际时间：不把玩家0.72时钟挤到世界0.22时钟导致3.27倍快进。
    -- 录下的子弹时间表现也保留，玩家可以欣赏自己实际完成的操作。
    r.realCursor=r.realCursor+dt
    while r.index<#r.frames and r.frames[r.index+1].realTime<=r.realCursor do r.index=r.index+1 end
    w.view=r.frames[r.index]
    return r.realCursor>=r.frames[#r.frames].realTime+0.25
end
return R
