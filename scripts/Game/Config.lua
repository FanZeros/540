-- 固定设计坐标；所有玩法由 Lua 自行实现，不调用引擎物理或动画。
local C = { WIDTH = 676, HEIGHT = 288, FLOOR = 246, STEP = 1 / 120,
    WORLD_SLOW = 0.22, PLAYER_SLOW = 0.72, DOORS = { 114, 257, 429, 562 } }
C.playerFrames = { Idle = 5, Run = 10, Prerun = 4, Stoprun = 3, Jump = 10,
    Land = 2, Roll = 7, Slash = 5, Squat = 3, Wallslide = 1, Hit = 6 }
C.playerFPS = { Idle = 8, Run = 16, Prerun = 24, Stoprun = 20, Jump = 15,
    Land = 16, Roll = 20, Slash = 22, Squat = 30, Wallslide = 8, Hit = 10 }
C.meleeTags = { Idle = {0, 5}, Switch = {6, 12}, Hurt = {13, 17}, Hit = {18, 21},
    Death = {22, 27}, Walk = {28, 37}, Run = {38, 43} }
C.rangedTags = { Idle = {0, 9}, ShieldHit = {10, 10}, Switch = {11, 14},
    ShieldAttact = {15, 19}, Shoot = {20, 27}, ShootEnd = {28, 29}, Hit = {30, 38},
    Run = {39, 45}, Walk = {46, 53} }
C.fx = {
    jump = {"VFX_Jump.png",54,54,5}, land = {"VFX_Land.png",54,54,2},
    roll = {"VFX_Roll.png",24,24,6}, slash = {"VFX_Slash.png",98,36,5},
    hit = {"受击特效.png",80,54,5}, melee = {"大壮攻击特效.png",54,44,3},
    shoot = {"射击特效.png",54,54,5},
}
C.sounds = { "sound_player_jump.wav", "sound_player_land.wav", "sound_player_landwire.wav",
    "sound_player_prerun.wav", "sound_player_roll.wav", "sound_player_wallslide.wav", "sound_playerdie.wav",
    "sound_player_running_1.wav", "sound_player_running_2.wav", "sound_player_running_3.wav", "sound_player_running_4.wav",
    "sound_player_slash_1.wav", "sound_player_slash_2.wav", "sound_player_slash_3.wav", "Ambient.wav", "Music.wav" }
C.images = { {"Background.png",676,288,1}, {"大壮动作.png",72,54,44}, {"盾牌男.png",51,44,54},
    {"Bullet.png",16,8,1}, {"Crate.png",28,28,1}, {"Barrel.png",22,32,1},
    {"Portal.png",24,54,1}, {"Platform.png",96,8,1} }
for name, count in pairs(C.playerFrames) do
    C.images[#C.images + 1] = {"武士零主角/" .. name .. ".png",72,54,count}
end
for _, fx in pairs(C.fx) do C.images[#C.images + 1] = fx end
C.chapters = {
    {name="雨夜来信", story="凌晨 03:17。有人把你的名字，从明天的死亡名单里划掉了。", count=3, gap=2.5, gun=0, tint={16,54,75}},
    {name="第二声枪响", story="电话里的声音说：不要相信枪声。相信刀锋碰到它的那一瞬间。", count=4, gap=2.1, gun=2, tint={30,30,70}},
    {name="易燃的秘密", story="那些红色容器里，装的不是燃料。是他们删不掉的证据。", count=5, gap=1.9, gun=2, tint={65,20,45}},
    {name="门的另一面", story="你走进同一扇门两次。第二次，整个走廊站到了你的身后。", count=6, gap=1.8, gun=3, tint={14,64,64}},
    {name="悬空记忆", story="监控拍不到高处。跃过枪线，让他们记住一片空白。", count=7, gap=1.65, gun=3, tint={45,28,78}},
    {name="折返弹道", story="两道裂隙之间，最短的路不再是一条直线。", count=8, gap=1.6, gun=4, tint={14,58,68}},
    {name="连锁反应", story="一刀，一次爆炸，一场连锁。他们终于开始害怕安静。", count=9, gap=1.5, gun=4, tint={75,24,36}},
    {name="不存在的楼层", story="电梯上没有第八层。可你已经听见了里面的脚步。", count=10, gap=1.4, gun=5, tint={40,25,75}},
    {name="最后的安保", story="十分钟之前，这些人还以为你只有一次机会。", count=11, gap=1.3, gun=5, tint={60,18,45}},
    {name="零刻", story="天亮之前，把这段记忆带出去。这一次，别再回头。", count=12, gap=1.2, gun=6, tint={14,58,78}},
}
return C
