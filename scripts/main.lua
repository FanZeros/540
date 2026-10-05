-- 基于 scaffold-2d.lua 生命周期；游戏自写物理、碰撞、动画和状态管理。
local World = require "Game.World"
local Render = require "Game.Render"
local Audio = require "Game.Audio"
local Interface = require "Game.Interface"
local Config = require "Game.Config"
local Assets = require "Game.Assets"
---@type NVGContextWrapper?
local vg = nil
---@type table
local app = {}
local accum=0
local pending={jump=false,slash=false,roll=false,restart=false}
function Start()
    graphics.windowTitle="零刻 / ZERO HOUR"
    input.mouseMode=MM_ABSOLUTE
    vg=nvgCreate(0)
    assert(vg,"无法创建绘图上下文")
    Assets.Load()
    app.audio=Audio.New()
    app.world=World.New(app.audio)
    app.renderer=Render.New(vg)
    app.interface=Interface.New(app.world)
    SubscribeToEvent("Update","HandleUpdate")
    SubscribeToEvent(vg,"NanoVGRender","HandleGameRender")
    print("[零刻] 初始化完成：676×288，十关，自写120Hz物理，固定键位")
end
local function readInput()
    -- 测试入口可注入同一套动作布尔值，正式启动从不设置此回调。
    if app.testInput then return app.testInput(app.world) end
    if not input.focus then return {} end
    return {
        left=input:GetKeyDown(KEY_A) or input:GetKeyDown(KEY_LEFT),
        right=input:GetKeyDown(KEY_D) or input:GetKeyDown(KEY_RIGHT),
        jump=input:GetKeyPress(KEY_SPACE) or input:GetKeyPress(KEY_W),
        slash=input:GetKeyPress(KEY_J) or input:GetMouseButtonPress(MOUSEB_LEFT),
        roll=input:GetKeyPress(KEY_K) or input:GetKeyPress(KEY_SHIFT),
        slow=input:GetKeyDown(KEY_L) or input:GetMouseButtonDown(MOUSEB_RIGHT),
        restart=input:GetKeyPress(KEY_R),
    }
end
---@param eventType string
---@param eventData UpdateEventData
function HandleUpdate(eventType,eventData)
    if not app.world then return end
    local dt=math.max(0,math.min(0.1,eventData:GetFloat("TimeStep")))
    local keys=readInput()
    for name in pairs(pending) do
        if not app.testInput and not input.focus then pending[name]=false
        else pending[name]=(pending[name] or keys[name])==true end
    end
    accum=accum+dt
    local iterations=0
    while accum>=Config.STEP and iterations<12 do
        keys.jump=pending.jump; keys.slash=pending.slash; keys.roll=pending.roll; keys.restart=pending.restart
        app.world:Update(Config.STEP,keys)
        for name in pairs(pending) do pending[name]=false end
        accum=accum-Config.STEP; iterations=iterations+1
    end
    app.audio:Update(app.world.slow)
    app.interface:Update()
end
function HandleGameRender()
    if app.renderer then app.renderer:Draw(app.world) end
end
function Stop()
    if app.interface then app.interface:Dispose() end
    if app.audio then app.audio:Dispose() end
    if app.renderer then app.renderer:Dispose() end
    if vg then nvgDelete(vg); vg=nil end
    app={}
end
return app
