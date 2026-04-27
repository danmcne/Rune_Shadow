"""
Rune & Shadow - UI v3
HUD, Inventory, Menus. Fixed drop (U=unequip, D=drop, Enter/E=equip, Space=use).
"""
import pygame
from constants import *
from items import ITEMS

_fonts={}
def font(size):
    if size not in _fonts:
        _fonts[size]=pygame.font.SysFont("monospace",size,bold=False)
    return _fonts[size]

def draw_text(surf,text,x,y,size=16,color=WHITE,shadow=True):
    f=font(size)
    if shadow: surf.blit(f.render(text,True,BLACK),(x+1,y+1))
    surf.blit(f.render(text,True,color),(x,y))

def draw_bar(surf,x,y,w,h,value,max_val,fg,bg=DARK_GRAY,label=""):
    pygame.draw.rect(surf,bg,(x,y,w,h))
    filled=int(w*max(0,value)/max(1,max_val))
    pygame.draw.rect(surf,fg,(x,y,filled,h))
    pygame.draw.rect(surf,WHITE,(x,y,w,h),1)
    if label: draw_text(surf,label,x+4,y+1,size=13,shadow=False)


# ═══════════════════════════════════════════════════════════════════════════════
#  HUD
# ═══════════════════════════════════════════════════════════════════════════════
class HUD:
    SLOT_SIZE=44; SLOT_PAD=4
    def __init__(self): self._surf=pygame.Surface((SCREEN_WIDTH,HUD_H))

    def draw(self,screen,player,map_name,messages,asset_mgr=None,
             difficulty=DIFFICULTY_NORMAL,cheat_display=""):
        s=self._surf; s.fill((20,20,28))
        pygame.draw.line(s,  (80,80,100),(0,0),(SCREEN_WIDTH,0),2)

        draw_bar(s,8,8,160,18,player.hp,player.max_hp,RED,
                 label=f"HP {player.hp}/{player.max_hp}")
        draw_bar(s,8,32,160,18,player.mana,player.max_mana,BLUE,
                 label=f"MP {player.mana}/{player.max_mana}")
        draw_text(s,f"Gold: {player.inventory.gold}",8,56,14,GOLD)

        # Status indicators
        status_x=178
        if player.is_swimming:
            draw_text(s,"~SWIM~",status_x,56,12,CYAN)
        elif player.is_slowed:
            draw_text(s,"~SLOW~",status_x,56,12,(100,200,100))

        # Aim mode
        aim_col=YELLOW if player.aim_mode=='mouse' else CYAN
        draw_text(s,f"AIM:{player.aim_mode.upper()[0]}",status_x,8,11,aim_col)
        draw_text(s,"[TAB]",status_x,20,10,GRAY)

        diff_col=[GREEN,WHITE,RED][difficulty]
        draw_text(s,DIFFICULTY_LABELS[difficulty],SCREEN_WIDTH-80,6,12,diff_col)
        draw_text(s,map_name,SCREEN_WIDTH//2,6,15,LIGHT_GRAY)
        if cheat_display:
            draw_text(s,f"CHEAT:{cheat_display}",SCREEN_WIDTH//2-60,HUD_H-18,13,(200,150,255))

        # Hotbar
        hb_x=245; hb_y=8
        for i in range(HOTBAR_SLOTS):
            iid=player.hotbar[i]
            sx=hb_x+i*(self.SLOT_SIZE+self.SLOT_PAD)
            sel=(i==player.equipped)
            col_b=YELLOW if sel else (60,60,80)
            pygame.draw.rect(s,(30,30,45),(sx,hb_y,self.SLOT_SIZE,self.SLOT_SIZE))
            pygame.draw.rect(s,col_b,(sx,hb_y,self.SLOT_SIZE,self.SLOT_SIZE),2)
            if iid and iid in ITEMS:
                it=ITEMS[iid]; isz=self.SLOT_SIZE-12
                pygame.draw.rect(s,it.color,(sx+6,hb_y+6,isz,isz))
                cnt=player.inventory.count(iid)
                if it.stackable and cnt>0:
                    draw_text(s,str(cnt),sx+self.SLOT_SIZE-16,hb_y+self.SLOT_SIZE-16,12,WHITE,False)
            draw_text(s,str(i+1),sx+2,hb_y+2,11,GRAY,False)

        # Messages
        msg_x=SCREEN_WIDTH-320
        for mi,(msg,col) in enumerate(messages[-4:]):
            draw_text(s,msg,msg_x,6+mi*18,13,col)

        ctrl="SPACE/Click=Attack  E=Interact  I=Inv  Q/F=Cycle  X=Unequip  ESC=Pause"
        draw_text(s,ctrl,SCREEN_WIDTH//2-280,HUD_H-18,12,(120,120,140),False)
        screen.blit(s,(0,VIEWPORT_H))


# ═══════════════════════════════════════════════════════════════════════════════
#  Inventory Screen
# ═══════════════════════════════════════════════════════════════════════════════
class InventoryScreen:
    COLS=6; ROWS=8; SZ=52; PAD=6
    PANEL_W=COLS*(52+6)+6+220; PANEL_H=ROWS*(52+6)+6+90

    def __init__(self): self.cursor=0

    def handle_key(self,event,player,messages):
        inv=player.inventory; slots=list(inv.items()); n=len(slots)
        k=event.key

        if k in (pygame.K_ESCAPE,pygame.K_i): return True
        if k==pygame.K_UP:    self.cursor=(self.cursor-self.COLS)%max(1,n)
        elif k==pygame.K_DOWN: self.cursor=(self.cursor+self.COLS)%max(1,n)
        elif k==pygame.K_LEFT: self.cursor=(self.cursor-1)%max(1,n)
        elif k==pygame.K_RIGHT:self.cursor=(self.cursor+1)%max(1,n)

        elif k==pygame.K_RETURN or k==pygame.K_e:
            # EQUIP (non-consumables) or USE (consumables)
            if 0<=self.cursor<n:
                item,cnt=slots[self.cursor]
                if item.itype==IT_CONSUMABLE:
                    player.use_item(item.iid,messages)
                elif item.itype not in (IT_CURRENCY,IT_INGREDIENT,IT_AMMO):
                    # Find free slot or use current
                    target=next((i for i in range(HOTBAR_SLOTS)
                                 if player.hotbar[i] is None),player.equipped)
                    player.hotbar[target]=item.iid
                    messages.append((f"Equipped {item.name} → slot {target+1}.",YELLOW))
                else:
                    messages.append(("Can't equip that.",GRAY))

        elif k==pygame.K_SPACE:
            # USE only
            if 0<=self.cursor<n:
                item,_=slots[self.cursor]
                if item.itype==IT_CONSUMABLE:
                    player.use_item(item.iid,messages)
                else:
                    messages.append(("Press E/Enter to equip.",GRAY))

        elif k==pygame.K_u:
            # UNEQUIP from hotbar (remove current slot reference)
            cleared=False
            if 0<=self.cursor<n:
                item,_=slots[self.cursor]
                for si in range(HOTBAR_SLOTS):
                    if player.hotbar[si]==item.iid:
                        player.hotbar[si]=None; cleared=True; break
            if cleared: messages.append(("Unequipped.",GRAY))
            else: messages.append(("Not equipped.",GRAY))

        elif k==pygame.K_d:
            # DROP — remove from inventory FIRST then signal GroundItem creation
            if 0<=self.cursor<n:
                item,cnt=slots[self.cursor]
                if item.itype==IT_CURRENCY:
                    messages.append(("Gold drops automatically.",GRAY))
                else:
                    # Remove from inventory first (prevents duplication)
                    if inv.remove(item.iid,1):
                        # Clear hotbar ref if count drops to 0
                        if inv.count(item.iid)==0:
                            for si in range(HOTBAR_SLOTS):
                                if player.hotbar[si]==item.iid:
                                    player.hotbar[si]=None
                        # Signal game.py to spawn GroundItem
                        messages.append((f"__DROP__:{item.iid}",WHITE))
                        messages.append((f"Dropped {item.name}.",ORANGE))
                        self.cursor=min(self.cursor,max(0,len(list(inv.items()))-1))

        elif pygame.K_1<=k<=pygame.K_8:
            slot=k-pygame.K_1
            if 0<=self.cursor<n:
                item,_=slots[self.cursor]
                player.hotbar[slot]=item.iid
                messages.append((f"{item.name} → slot {slot+1}",YELLOW))

        return False

    def draw(self,screen,player,asset_mgr=None):
        inv=player.inventory; slots=list(inv.items())
        ov=pygame.Surface((SCREEN_WIDTH,SCREEN_HEIGHT),pygame.SRCALPHA)
        ov.fill((0,0,0,160)); screen.blit(ov,(0,0))
        px=(SCREEN_WIDTH-self.PANEL_W)//2; py=(SCREEN_HEIGHT-self.PANEL_H)//2
        pygame.draw.rect(screen,(20,20,35),(px,py,self.PANEL_W,self.PANEL_H))
        pygame.draw.rect(screen,(80,80,120),(px,py,self.PANEL_W,self.PANEL_H),2)
        draw_text(screen,"─── INVENTORY ───",px+8,py+8,20,YELLOW)
        draw_text(screen,f"Gold: {inv.gold}",px+8,py+32,16,GOLD)

        for i,(item,count) in enumerate(slots):
            col_=i%self.COLS; row_=i//self.COLS
            sx=px+self.PAD+col_*(self.SZ+self.PAD)
            sy=py+56+row_*(self.SZ+self.PAD)
            bg=(80,80,150) if i==self.cursor else (40,40,60)
            pygame.draw.rect(screen,bg,(sx,sy,self.SZ,self.SZ))
            pygame.draw.rect(screen,YELLOW if i==self.cursor else (60,60,90),
                             (sx,sy,self.SZ,self.SZ),2)
            isz=self.SZ-16
            pygame.draw.rect(screen,item.color,(sx+8,sy+8,isz,isz))
            if item.stackable and count>1:
                draw_text(screen,str(count),sx+self.SZ-20,sy+self.SZ-18,13,WHITE,False)
            if item.iid in player.hotbar:
                pygame.draw.rect(screen,GOLD,(sx,sy,self.SZ,self.SZ),2)
                draw_text(screen,"E",sx+2,sy+2,10,GOLD,False)

        # Info panel
        if 0<=self.cursor<len(slots):
            item,count=slots[self.cursor]
            ix=px+self.COLS*(self.SZ+self.PAD)+10; iy=py+56
            draw_text(screen,item.name,ix,iy,18,WHITE)
            draw_text(screen,f"Type: {item.itype}",ix,iy+24,14,LIGHT_GRAY)
            lines=[]
            if item.damage:      lines.append(f"Dmg: {item.damage}")
            if item.defense:     lines.append(f"Def: +{item.defense}")
            if item.hp_restore:  lines.append(f"Heal: +{item.hp_restore}")
            if item.mp_restore:  lines.append(f"Mana: +{item.mp_restore}")
            if item.mana_cost:   lines.append(f"Cost: {item.mana_cost}MP")
            if item.light_radius:lines.append(f"Light: {item.light_radius}t")
            for li,ln in enumerate(lines):
                draw_text(screen,ln,ix,iy+44+li*20,14,LIGHT_GRAY)
            y_off=iy+44+len(lines)*20+10
            desc=item.description
            for li in range(0,min(len(desc),110),22):
                draw_text(screen,desc[li:li+22],ix,y_off+li//22*18,13,GRAY)
            y_off+=70
            if item.itype==IT_CONSUMABLE:
                draw_text(screen,"[Enter/Space]=Use",ix,y_off,13,GREEN)
            else:
                draw_text(screen,"[Enter/E]=Equip",ix,y_off,13,CYAN)
                draw_text(screen,"[U]=Unequip from hotbar",ix,y_off+18,13,YELLOW)
            draw_text(screen,"[D]=Drop item",ix,y_off+36,13,ORANGE)

        draw_text(screen,
            "[Arrows]=Move  [E]=Equip  [Space]=Use  [U]=Unequip  [D]=Drop  [1-8]=Slot  [I]=Close",
            px+4,py+self.PANEL_H-26,12,(100,100,130),False)


# ═══════════════════════════════════════════════════════════════════════════════
#  Menus
# ═══════════════════════════════════════════════════════════════════════════════
def draw_main_menu(screen,seed_str,cursor,difficulty=DIFFICULTY_NORMAL,has_save=False):
    screen.fill((10,10,20))
    draw_text(screen,"RUNE  &  SHADOW",SCREEN_WIDTH//2-180,100,52,GOLD)
    draw_text(screen,"A  Roguelike  Adventure",SCREEN_WIDTH//2-140,162,20,LIGHT_GRAY)
    opts=["New Game"]+( ["Load Save"] if has_save else [])+["Quit"]
    for i,opt in enumerate(opts):
        col=YELLOW if i==cursor else LIGHT_GRAY
        draw_text(screen,opt,SCREEN_WIDTH//2-60,250+i*52,28,col)
        if i==cursor: draw_text(screen,"►",SCREEN_WIDTH//2-92,250+i*52,28,YELLOW)
    y_off=250+len(opts)*52+10
    draw_text(screen,"Difficulty:",SCREEN_WIDTH//2-100,y_off,18,LIGHT_GRAY)
    for di,dlabel in enumerate(DIFFICULTY_LABELS):
        col=[GREEN,WHITE,RED][di]
        bx=SCREEN_WIDTH//2-90+di*80
        if di==difficulty:
            pygame.draw.rect(screen,col,(bx,y_off+26,72,26))
            draw_text(screen,dlabel,bx+6,y_off+28,15,BLACK,False)
        else:
            pygame.draw.rect(screen,(40,40,50),(bx,y_off+26,72,26))
            draw_text(screen,dlabel,bx+6,y_off+28,15,col,False)
    draw_text(screen,"[←/→] difficulty",SCREEN_WIDTH//2-100,y_off+58,13,GRAY)
    draw_text(screen,f"World Seed: {seed_str}_",SCREEN_WIDTH//2-100,y_off+90,18,CYAN)
    draw_text(screen,"(Type numbers to change seed)",SCREEN_WIDTH//2-160,y_off+114,13,GRAY)
    draw_text(screen,"Start in TOWN. Gates N/S/E/W lead to different biomes.",
              SCREEN_WIDTH//2-260,670,14,(100,120,160))
    draw_text(screen,"WASD=Move  Mouse=Aim  TAB=Toggle aim  X=Unequip  E=Interact",
              SCREEN_WIDTH//2-255,690,14,(100,100,140))
    draw_text(screen,"Cheats: GODMODE  MAXHP  MAXMANA  GIVEALL  NOCLIP  RESPAWN  LEVELUP  FULLCLEAR",
              SCREEN_WIDTH//2-320,710,12,(80,80,100))

def draw_game_over(screen,score):
    screen.fill((10,5,5))
    draw_text(screen,"YOU  DIED",SCREEN_WIDTH//2-130,200,60,DARK_RED)
    draw_text(screen,f"Score: {score}",SCREEN_WIDTH//2-60,300,28,WHITE)
    draw_text(screen,"Press ENTER to return to menu",SCREEN_WIDTH//2-190,380,22,GRAY)

def draw_paused(screen,cursor=0,has_save=True):
    ov=pygame.Surface((SCREEN_WIDTH,SCREEN_HEIGHT),pygame.SRCALPHA)
    ov.fill((0,0,0,150)); screen.blit(ov,(0,0))
    pw,ph=340,280
    px=SCREEN_WIDTH//2-pw//2; py=SCREEN_HEIGHT//2-ph//2
    pygame.draw.rect(screen,(18,18,30),(px,py,pw,ph))
    pygame.draw.rect(screen,(100,80,160),(px,py,pw,ph),2)
    draw_text(screen,"── PAUSED ──",px+pw//2-80,py+14,26,YELLOW)
    opts=["Resume","New Game","Save & Quit","Quit (no save)"]
    for i,opt in enumerate(opts):
        col=YELLOW if i==cursor else LIGHT_GRAY
        draw_text(screen,opt,px+pw//2-70,py+70+i*50,22,col)
        if i==cursor: draw_text(screen,"►",px+pw//2-96,py+70+i*50,22,YELLOW)
    draw_text(screen,"[↑/↓] navigate  [Enter] select  [ESC] resume",
              px+12,py+ph-24,12,(100,100,130),False)

def draw_win(screen,score):
    screen.fill((5,10,5))
    draw_text(screen,"VICTORY!",SCREEN_WIDTH//2-110,180,60,GOLD)
    draw_text(screen,"You conquered the darkness.",SCREEN_WIDTH//2-190,270,22,WHITE)
    draw_text(screen,f"Score: {score}",SCREEN_WIDTH//2-60,320,28,YELLOW)
    draw_text(screen,"Press ENTER to return to menu",SCREEN_WIDTH//2-190,400,22,GRAY)
