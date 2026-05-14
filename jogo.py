import pygame, sys, random
from collections import deque

pygame.init()

SCREEN_W, SCREEN_H = 900, 700
HUD_H  = 65
VIEW_H = SCREEN_H - HUD_H
TILE   = 40   # tamanho fixo — camera rola para labirintos grandes

# ── cores base ────────────────────────────────────────────────────────────────
BG       = (15,  15,  25)
WALL_C   = (60,  63,  85)
WALL_E   = (80,  83, 108)
FLOOR_C  = (32,  34,  48)
EXIT_C   = (40, 200,  70)
EXIT_E   = (60, 230,  90)
CRACK0   = (90,  75,  40)   # rachado intacto
CRACK1   = (130, 50,  30)   # rachado danificado (já pisado)
GOLD     = (255, 200,  40)
WHITE    = (238, 238, 238)
GRAY     = (100, 103, 123)
GREEN    = (55,  205,  80)
BLACK    = (0,   0,    0)
RED      = (215,  45,  45)

# paleta de cores dos pares (botão/alavanca/chave ↔ porta)
PAIR_COLORS = [
    (255, 210,  30),   # dourado
    (40,  190, 255),   # ciano
    (170,  80, 255),   # roxo
    (255,  90,  50),   # laranja-vermelho
    (50,  230, 130),   # verde-menta
    (255, 100, 180),   # rosa
    (100, 200, 255),   # azul-claro
    (255, 180,  60),   # âmbar
    (140, 255, 100),   # verde-lima
]

# ── configurações de cada fase ─────────────────────────────────────────────
# (cols, rows, seed, n_botoes, n_alavancas, n_chaves, n_rachaduras, n_teleportes)
LEVEL_CONFIGS = [
    (11,  9,  42, 1, 0, 0,  0, 0),   # 1
    (13, 11,  17, 2, 0, 0,  0, 0),   # 2
    (15, 13,   7, 1, 1, 0,  0, 0),   # 3
    (17, 13,  99, 2, 1, 0,  0, 0),   # 4
    (17, 15,  33, 1, 1, 1,  0, 0),   # 5
    (19, 15,  55, 2, 1, 1,  5, 0),   # 6  + rachaduras
    (21, 15,  81, 2, 1, 1,  6, 1),   # 7  + teleporte
    (21, 17,  23, 2, 2, 2,  7, 1),   # 8
    (25, 19,  64, 3, 2, 2,  9, 1),   # 9
    (27, 21, 100, 3, 3, 3, 12, 2),   # 10
]

# ── geração do labirinto (DFS) ────────────────────────────────────────────────
def gen_maze(cols, rows, seed):
    rng = random.Random(seed)
    g = [['#']*cols for _ in range(rows)]
    g[1][1] = ' '
    stk, vis = [(1,1)], {(1,1)}
    ds = [(0,-2),(0,2),(-2,0),(2,0)]
    while stk:
        cx,cy = stk[-1]
        nb = [(cx+dx,cy+dy,dx,dy) for dx,dy in ds
              if 1<=cx+dx<cols-1 and 1<=cy+dy<rows-1 and (cx+dx,cy+dy) not in vis]
        if nb:
            nx,ny,dx,dy = rng.choice(nb)
            g[cy+dy//2][cx+dx//2]=' '; g[ny][nx]=' '
            vis.add((nx,ny)); stk.append((nx,ny))
        else: stk.pop()
    g[1][1]='S'; g[rows-2][cols-2]='E'
    return [''.join(r) for r in g]

def parse_maze(lines):
    walls,S,E = set(),(1,1),(1,1)
    for r,row in enumerate(lines):
        for c,ch in enumerate(row):
            if ch=='#': walls.add((c,r))
            elif ch=='S': S=(c,r)
            elif ch=='E': E=(c,r)
    return walls,S,E

def bfs(start,goal,blocked):
    if start==goal: return [start]
    q=deque([(start,[start])]); vis={start}
    while q:
        (x,y),p=q.popleft()
        for dx,dy in [(0,1),(0,-1),(1,0),(-1,0)]:
            n=(x+dx,y+dy)
            if n not in blocked and n not in vis:
                vis.add(n); np2=p+[n]
                if n==goal: return np2
                q.append((n,np2))
    return []

def flood(start,blocked):
    vis={start}; q=deque([start])
    while q:
        x,y=q.popleft()
        for dx,dy in [(0,1),(0,-1),(1,0),(-1,0)]:
            n=(x+dx,y+dy)
            if n not in blocked and n not in vis: vis.add(n); q.append(n)
    return vis

def deg(pos, walls):
    x,y=pos
    return sum(1 for dx,dy in [(0,1),(0,-1),(1,0),(-1,0)] if (x+dx,y+dy) not in walls)

# ── posicionamento de elementos ───────────────────────────────────────────────
def place_elements(walls,S,E,seed,nb,nl,nk,ncr,nt):
    rng   = random.Random(seed^0xF00D)
    btns  = []   # (c,r,door_id,color_idx)
    levs  = []   # (c,r,door_id,color_idx)
    keys  = []   # (c,r,door_id,color_idx)
    doors = {}   # door_id -> (c,r, type)   type: 'btn'|'lev'|'key'
    cracks= set()
    teles = []   # [(entrance,exit), ...]

    cw  = set(walls)
    path= bfs(S,E,cw)
    if not path or len(path)<6:
        return btns,levs,keys,doors,cracks,teles

    pset = set(path); used={S,E}
    mid  = path[2:-2]; rng.shuffle(mid)
    did=0; pi=0; color_idx=0

    for i in range(nb+nl+nk):
        dp=None
        while pi<len(mid):
            c=mid[pi]; pi+=1
            if c not in used: dp=c; break
        if not dp: break
        used.add(dp)

        reach = flood(S, cw|{dp})
        off   = [c for c in reach if c not in pset and c not in used]
        dead  = [c for c in off if deg(c,cw)==1]
        pool  = dead or off or [c for c in reach if c not in used]
        if not pool: continue
        bp = rng.choice(pool); used.add(bp)
        cw.add(dp); doors[did]=(dp[0],dp[1], 'btn' if i<nb else 'lev' if i<nb+nl else 'key')
        ci = color_idx % len(PAIR_COLORS)
        if i<nb:         btns.append((bp[0],bp[1],did,ci))
        elif i<nb+nl:    levs.append((bp[0],bp[1],did,ci))
        else:            keys.append((bp[0],bp[1],did,ci))
        did+=1; color_idx+=1

    # rachaduras (tiles de chão, não críticos, não especiais)
    all_floor = [c for c in flood(S,walls) if c not in pset and c not in used]
    rng.shuffle(all_floor)
    for c in all_floor[:ncr]: cracks.add(c); used.add(c)

    # teleportes (pares em regiões diferentes)
    floor_list = [c for c in flood(S,cw) if c not in used]
    rng.shuffle(floor_list)
    for _ in range(nt):
        if len(floor_list)<4: break
        e1 = floor_list.pop(); e2 = floor_list.pop()
        teles.append((e1,e2)); used.add(e1); used.add(e2)

    return btns,levs,keys,doors,cracks,teles

# ── carregamento de fase ──────────────────────────────────────────────────────
def load_level(idx):
    cols,rows,seed,nb,nl,nk,ncr,nt = LEVEL_CONFIGS[idx]
    maze = gen_maze(cols,rows,seed)
    walls,S,E = parse_maze(maze)
    btns,levs,keys,doors,cracks,teles = place_elements(walls,S,E,seed,nb,nl,nk,ncr,nt)
    return dict(walls=walls,S=S,E=E,cols=cols,rows=rows,
                btns=btns,levs=levs,keys=keys,doors=doors,
                cracks=cracks,teles=teles)

# ── câmera ────────────────────────────────────────────────────────────────────
def get_cam(px,py,cols,rows):
    vc = SCREEN_W//TILE; vr = VIEW_H//TILE
    cx = max(0,min(px-vc//2, cols-vc))
    cy = max(0,min(py-vr//2, rows-vr))
    return cx,cy

def sx(c,cx): return (c-cx)*TILE   # screen x
def sy(r,cy): return (r-cy)*TILE   # screen y

# ── desenho ───────────────────────────────────────────────────────────────────
def draw_tile(surf,color,c,r,cx,cy,edge=None,pad=0,rad=0):
    x,y=sx(c,cx),sy(r,cy)
    pygame.draw.rect(surf,color,(x+pad,y+pad,TILE-2*pad,TILE-2*pad),border_radius=rad)
    if edge: pygame.draw.rect(surf,edge,(x+pad,y+pad,TILE-2*pad,TILE-2*pad),1,border_radius=rad)

def draw_icon(surf,font,text,color,c,r,cx,cy):
    s=font.render(text,True,color)
    x,y=sx(c,cx)+TILE//2-s.get_width()//2, sy(r,cy)+TILE//2-s.get_height()//2
    surf.blit(s,(x,y))

def draw_scene(surf,fnt,lv,px,py,door_open,key_held,crack_dmg,broken):
    _,_,fS=fnt
    cx,cy=get_cam(px,py,lv['cols'],lv['rows'])
    vc=SCREEN_W//TILE+2; vr=VIEW_H//TILE+2

    surf.fill(BG)

    # piso e paredes
    for r in range(cy,min(cy+vr,lv['rows'])):
        for c in range(cx,min(cx+vc,lv['cols'])):
            p=(c,r)
            if p in lv['walls']:
                draw_tile(surf,WALL_C,c,r,cx,cy,WALL_E)
            else:
                draw_tile(surf,FLOOR_C,c,r,cx,cy)

    # rachaduras
    for (c,r) in lv['cracks']:
        if (c,r) in broken: continue
        color = CRACK1 if (c,r) in crack_dmg else CRACK0
        draw_tile(surf,color,c,r,cx,cy,pad=2,rad=2)
        x,y=sx(c,cx),sy(r,cy)
        col2=tuple(min(255,v+40) for v in color)
        pygame.draw.line(surf,col2,(x+5,y+5),(x+TILE-5,y+TILE-5),1)
        pygame.draw.line(surf,col2,(x+TILE//2,y+5),(x+5,y+TILE-5),1)

    # saída
    ec,er=lv['E']
    if cx<=ec<cx+vc and cy<=er<cy+vr:
        draw_tile(surf,EXIT_C,ec,er,cx,cy,EXIT_E,pad=3,rad=6)
        draw_icon(surf,fS,"E",BLACK,ec,er,cx,cy)

    # portas
    for did,(dc,dr,dtype) in lv['doors'].items():
        if not (cx<=dc<cx+vc and cy<=dr<cy+vr): continue
        opened=door_open.get(did,False)
        if opened:
            # porta aberta: mostrar apenas contorno
            x,y=sx(dc,cx),sy(dr,cy)
            pygame.draw.rect(surf,FLOOR_C,(x,y,TILE,TILE))
            # símbolo de passagem
            col=PAIR_COLORS[did%len(PAIR_COLORS)]
            pygame.draw.rect(surf,tuple(v//4 for v in col),(x+3,y+3,TILE-6,TILE-6),1,border_radius=3)
        else:
            col=PAIR_COLORS[did%len(PAIR_COLORS)]
            draw_tile(surf,tuple(v//2 for v in col),dc,dr,cx,cy,col,pad=2,rad=3)
            # ícone do tipo
            icon = "●" if dtype=='btn' else "↕" if dtype=='lev' else "🗝"
            draw_icon(surf,fS,icon,col,dc,dr,cx,cy)

    # botões
    for (bc,br,did,ci) in lv['btns']:
        if not (cx<=bc<cx+vc and cy<=br<cy+vr): continue
        active=door_open.get(did,False)
        col=PAIR_COLORS[ci%len(PAIR_COLORS)]
        base=tuple(v//3 for v in col) if not active else tuple(min(255,v+30) for v in col)
        draw_tile(surf,base,bc,br,cx,cy,col,pad=TILE//5,rad=3)
        draw_icon(surf,fS,"●",col if not active else WHITE,bc,br,cx,cy)

    # alavancas
    for (lc,lr,did,ci) in lv['levs']:
        if not (cx<=lc<cx+vc and cy<=lr<cy+vr): continue
        active=door_open.get(did,False)
        col=PAIR_COLORS[ci%len(PAIR_COLORS)]
        draw_tile(surf,tuple(v//3 for v in col),lc,lr,cx,cy,col,pad=TILE//5,rad=3)
        # alavanca gráfica
        lx,ly=sx(lc,cx)+TILE//2, sy(lr,cy)+TILE//2
        tip=(lx+TILE//3,ly-TILE//4) if active else (lx-TILE//4,ly+TILE//3)
        pygame.draw.line(surf,col,(lx,ly),tip,max(2,TILE//8))
        pygame.draw.circle(surf,col,tip,max(2,TILE//8))
        # hint ESPAÇO perto
        if (lc,lr)==(px,py):
            h=fS.render("ESPAÇO",True,col)
            surf.blit(h,(sx(lc,cx)+TILE//2-h.get_width()//2, sy(lr,cy)-18))

    # chaves
    for (kc,kr,did,ci) in lv['keys']:
        if (kc,kr) in key_held: continue
        if not (cx<=kc<cx+vc and cy<=kr<cy+vr): continue
        col=PAIR_COLORS[ci%len(PAIR_COLORS)]
        draw_tile(surf,tuple(v//4 for v in col),kc,kr,cx,cy,col,pad=TILE//5,rad=3)
        draw_icon(surf,fS,"K",col,kc,kr,cx,cy)

    # teleportes
    for pair in lv['teles']:
        for i,(tc,tr) in enumerate(pair):
            if not (cx<=tc<cx+vc and cy<=tr<cy+vr): continue
            col=(150,60,255) if i==0 else (255,80,200)
            draw_tile(surf,tuple(v//3 for v in col),tc,tr,cx,cy,col,pad=3,rad=TILE//4)
            draw_icon(surf,fS,"T",col,tc,tr,cx,cy)

    # jogador
    px_s=sx(px,cx)+TILE//2; py_s=sy(py,cy)+TILE//2
    rad=TILE//2-4
    pygame.draw.circle(surf,(55,120,225),(px_s,py_s),rad)
    pygame.draw.circle(surf,(200,220,255),(px_s,py_s),rad,2)
    if rad>=8:
        eo=rad//3; er2=max(2,rad//5)
        for ex_off in(-eo,+eo):
            pygame.draw.circle(surf,WHITE,(px_s+ex_off,py_s-eo//2),er2)
            pygame.draw.circle(surf,BLACK,(px_s+ex_off+1,py_s-eo//2),max(1,er2//2))

def draw_hud(surf,fnt,lv_idx,total,moves,door_open,lv,key_held):
    _,fM,fS=fnt
    hy=VIEW_H
    pygame.draw.rect(surf,(10,10,20),(0,hy,SCREEN_W,HUD_H))
    pygame.draw.line(surf,GOLD,(0,hy),(SCREEN_W,hy),2)

    # barra progresso
    bw=max(1,int(SCREEN_W*(lv_idx+1)/total))
    pygame.draw.rect(surf,(35,35,55),(0,hy+HUD_H-5,SCREEN_W,5))
    pygame.draw.rect(surf,GOLD,(0,hy+HUD_H-5,bw,5))

    ls=fM.render(f"Fase {lv_idx+1}/{total}",True,GOLD)
    ms=fM.render(f"Movimentos: {moves}",True,WHITE)
    surf.blit(ls,(10,hy+8)); surf.blit(ms,(SCREEN_W//2-ms.get_width()//2,hy+8))

    # inventário de chaves
    inv_x=SCREEN_W-10
    for (kc,kr,_,ci) in reversed(lv['keys']):
        if (kc,kr) in key_held:
            col=PAIR_COLORS[ci%len(PAIR_COLORS)]
            ks=fS.render("K",True,col)
            inv_x-=ks.get_width()+4
            surf.blit(ks,(inv_x,hy+8))

    # portas fechadas
    nd=sum(1 for o in door_open.values() if not o)
    if nd:
        ds=fS.render(f"Portas fechadas: {nd}",True,GRAY)
        surf.blit(ds,(10,hy+32))

    # controles
    ctrl=fS.render("Setas: mover  ESPAÇO: alavanca  R: reiniciar  ESC: sair",True,GRAY)
    surf.blit(ctrl,(SCREEN_W//2-ctrl.get_width()//2,hy+32))

def draw_win(surf,fnt,lv_idx,total,moves):
    fB,fM,fS=fnt
    ov=pygame.Surface((SCREEN_W,SCREEN_H),pygame.SRCALPHA)
    ov.fill((0,0,0,165)); surf.blit(ov,(0,0))
    if lv_idx+1>=total:
        lines=[(fB,"PARABENS!",GOLD),(fM,"Voce completou todas as fases!",WHITE),
               (fM,f"Movimentos: {moves}",WHITE),(fS," ",GRAY),
               (fM,"ENTER: recomecar do inicio",GREEN)]
    else:
        lines=[(fB,"FASE CONCLUIDA!",GOLD),(fM,f"Movimentos: {moves}",WHITE),
               (fS," ",GRAY),(fM,"ENTER: proxima fase",GREEN),
               (fS,"R: reiniciar esta fase",GRAY)]
    y=SCREEN_H//2-len(lines)*44//2
    for fn,txt,col in lines:
        s=fn.render(txt,True,col); surf.blit(s,(SCREEN_W//2-s.get_width()//2,y)); y+=44

def draw_fell(surf,fnt):
    fB,_,_=fnt
    s=fB.render("CAIU!  Pressione R",True,RED)
    surf.blit(s,(SCREEN_W//2-s.get_width()//2,VIEW_H//2-20))

# ── lógica de jogo ────────────────────────────────────────────────────────────
def eff_walls(lv, door_open):
    return lv['walls'] | {(lv['doors'][d][0],lv['doors'][d][1])
                          for d,o in door_open.items() if not o}

def init_state(idx):
    lv = load_level(idx)
    door_open = {did: False for did in lv['doors']}
    # alavancas começam com a porta fechada, botões também
    return lv, door_open, set(), set(), set(), set()
    # lv, door_open, key_held(positions), crack_dmg, broken_set, tele_used

# ── main ──────────────────────────────────────────────────────────────────────
def main():
    screen=pygame.display.set_mode((SCREEN_W,SCREEN_H))
    pygame.display.set_caption("Labirinto — 10 Fases")
    clock=pygame.time.Clock()

    fB=pygame.font.SysFont("consolas",28,bold=True)
    fM=pygame.font.SysFont("consolas",19,bold=True)
    fS=pygame.font.SysFont("consolas",14)
    fnt=(fB,fM,fS)

    total=len(LEVEL_CONFIGS)
    lv_idx=0

    def reset(idx):
        nonlocal lv_idx,lv,px,py,moves,won,fell,door_open,key_held,crack_dmg,broken,held,last_m
        lv_idx=idx
        lv,door_open,key_held,crack_dmg,broken,_=init_state(idx)
        px,py=lv['S']; moves=0; won=False; fell=False; held=None; last_m=0

    lv=None; px=py=0; moves=0; won=fell=False
    door_open={}; key_held=set(); crack_dmg=set(); broken=set()
    held=None; last_m=0
    reset(0)

    DELAY=150
    DIRS={pygame.K_UP:(0,-1),pygame.K_DOWN:(0,1),
          pygame.K_LEFT:(-1,0),pygame.K_RIGHT:(1,0)}

    while True:
        clock.tick(60)
        now=pygame.time.get_ticks()

        for ev in pygame.event.get():
            if ev.type==pygame.QUIT: pygame.quit(); sys.exit()
            if ev.type==pygame.KEYDOWN:
                k=ev.key
                if k==pygame.K_ESCAPE: pygame.quit(); sys.exit()
                if k==pygame.K_r: reset(lv_idx); continue
                if won and k in(pygame.K_RETURN,pygame.K_SPACE):
                    reset((lv_idx+1)%total); continue
                if not won and not fell:
                    if k==pygame.K_SPACE:
                        # alavancas: toggle ao pressionar ESPAÇO em cima delas
                        for (lc,lr,did,_) in lv['levs']:
                            if (px,py)==(lc,lr):
                                door_open[did]=not door_open[did]
                    elif k in DIRS:
                        held=k; last_m=now-DELAY
            if ev.type==pygame.KEYUP:
                if ev.key==held: held=None

        if not won and not fell and held and now-last_m>=DELAY:
            dx,dy=DIRS[held]; nx,ny=px+dx,py+dy
            ew=eff_walls(lv,door_open)
            if (nx,ny) not in ew:
                # tile rachado?
                if (nx,ny) in lv['cracks'] and (nx,ny) not in broken:
                    if (nx,ny) in crack_dmg:
                        # segunda pisada: cai!
                        broken.add((nx,ny)); px,py=nx,ny; fell=True
                    else:
                        crack_dmg.add((nx,ny)); px,py=nx,ny; moves+=1
                else:
                    px,py=nx,ny; moves+=1

                if not fell:
                    last_m=now
                    # verificar vitória
                    if (px,py)==lv['E']: won=True

                    # botões: pisar abre porta permanentemente
                    for (bc,br,did,_) in lv['btns']:
                        if (px,py)==(bc,br): door_open[did]=True

                    # chaves: coletar
                    for (kc,kr,did,ci) in lv['keys']:
                        if (px,py)==(kc,kr) and (kc,kr) not in key_held:
                            key_held.add((kc,kr)); door_open[did]=True

                    # teleportes: ao pisar na entrada, vai para a saída
                    for pair in lv['teles']:
                        e1,e2=pair
                        dest=None
                        if (px,py)==e1: dest=e2
                        elif (px,py)==e2: dest=e1
                        if dest:
                            dw=eff_walls(lv,door_open)
                            if dest not in dw:
                                px,py=dest

        # desenho
        draw_scene(screen,fnt,lv,px,py,door_open,key_held,crack_dmg,broken)
        draw_hud(screen,fnt,lv_idx,total,moves,door_open,lv,key_held)
        if won: draw_win(screen,fnt,lv_idx,total,moves)
        elif fell: draw_fell(screen,fnt)
        pygame.display.flip()

if __name__=="__main__":
    main()
