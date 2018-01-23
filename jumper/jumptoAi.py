# -*- coding: utf-8 -*-
import numpy as np
import time
import os, glob, shutil
import cv2
import argparse
import random


def multi_scale_search(pivot, screen, range=0.3, num=10):
    H, W = screen.shape[:2]
    h, w = pivot.shape[:2]

    found = None
    for scale in np.linspace(1-range, 1+range, num)[::-1]:
        resized = cv2.resize(screen, (int(W * scale), int(H * scale)))
        r = W / float(resized.shape[1])
        if resized.shape[0] < h or resized.shape[1] < w:
            break
        res = cv2.matchTemplate(resized, pivot, cv2.TM_CCOEFF_NORMED)
        
        loc = np.where(res >= res.max())#只去最大概率的值
        
        pos_h, pos_w = list(zip(*loc))[0]
        
        if found is None or res.max() > found[-1]:
            found = (pos_h, pos_w, r, res.max())# 去处最大匹配分数的框
        
    if found is None: return (0,0,0,0,0)
    pos_h, pos_w, r, score = found
    start_h, start_w = int(pos_h * r), int(pos_w * r)
    end_h, end_w = int((pos_h + h) * r), int((pos_w + w) * r)
    #print ([start_h, start_w, end_h, end_w, score])
    return [start_h, start_w, end_h, end_w, score]

def showFocus(image,px,py,x1,y1,x2,y2,name="player"):
    cv2.rectangle(image, (x1,y1), (x2,y2), (255,0,0),3)
    cv2.circle(image, (py, px), 30, (71,23,226))
    if (y1 > 10):
        cv2.putText(image, name, (int(x1),int(y1-6)), cv2.FONT_HERSHEY_COMPLEX_SMALL,0.8, (0, 255, 0) )
    else:
        cv2.putText(image, name, (int(x1),int(y1+15)), cv2.FONT_HERSHEY_COMPLEX_SMALL,0.8, (0, 255, 0) )
    
    cv2.imwrite("cat.jpg", image)

class WechatAutoJump(object):
    def __init__(self, phone="IOS", sensitivity=2.045, serverURL=None, debug=False, resource_dir='../Wechat_AutoJump/resource'):
       
        self.phone = phone
        
        self.sensitivity = sensitivity
        self.debug = debug
        
        self.resource_dir = resource_dir
        
        self.bb_size = [300, 300]
        self.step = 0
        
    
        self.load_resource()
        """
        self.serverURL = serverURL
        if self.phone == 'IOS':
            import wda
            self.client = wda.Client(self.serverURL)
            self.s = self.client.session()
        if self.debug:
            if not os.path.exists(self.debug):
                os.mkdir(self.debug)
        """
    
    def load_resource(self):
        
        self.player = cv2.imread(os.path.join(self.resource_dir, 'player.png'), 0)
        circle_file = glob.glob(os.path.join(self.resource_dir, 'circle/*.png'))
        table_file  = glob.glob(os.path.join(self.resource_dir, 'table/*.png'))
        self.jump_file = [cv2.imread(name, 0) for name in circle_file + table_file]
    
    def get_current_state(self):
        """
        if self.phone == 'Android':
            os.system('adb shell screencap -p /sdcard/1.png')
            os.system('adb pull /sdcard/1.png state.png')
        elif self.phone == 'IOS':
            self.client.screenshot('state.png')

        if self.debug:
            shutil.copyfile('state.png', os.path.join(self.debug, 'state_{:03d}.png'.format(self.step)))
        """
        state = cv2.imread('1.jpg')
        
        
        self.resolution = state.shape[:2]#分辨率
        
        scale = state.shape[1] / 720.
        state = cv2.resize(state, (720, int(state.shape[0] / scale)), interpolation=cv2.INTER_NEAREST)#缩放手机分辨率
       
        
        if state.shape[0] > 1280:#如果大于1280 ,去掉两边的padding
            s = (state.shape[0] - 1280) // 2
            state = state[s:(s+1280),:,:]
        elif state.shape[0] < 1280:#如果小于1280补全两边的padding
            s1 = (1280 - state.shape[0]) // 2
            s2 = (1280 - state.shape[0]) - s1
            pad1 = 255 * np.ones((s1, 720, 3), dtype=np.uint8)
            pad2 = 255 * np.ones((s2, 720, 3), dtype=np.uint8)
            state = np.concatenate((pad1, state, pad2), 0)
        return state#最后shape为(1280, 720, 3)

    def get_player_position(self, state):
        state = cv2.cvtColor(state, cv2.COLOR_BGR2GRAY)#转换成灰度
        
        pos = multi_scale_search(self.player, state, 0.3, 10)
        h, w = int((pos[0] + 13 * pos[2])/14.), (pos[1] + pos[3])//2
       
        return np.array([h, w]),np.array([pos[1], pos[0],pos[3], pos[2]])
    
    def get_target_position(self, state, player_pos):
        state = cv2.cvtColor(state, cv2.COLOR_BGR2GRAY)
        
        sym_center = [1280, 720] - player_pos
        
        sym_tl = np.maximum([0,0], sym_center + np.array([-self.bb_size[0]//2, -self.bb_size[1]//2]))
        sym_br = np.array([min(sym_center[0] + self.bb_size[0]//2, player_pos[0]), min(sym_center[1] + self.bb_size[1]//2, 720)])
        state_cut = state[sym_tl[0]:sym_br[0], sym_tl[1]:sym_br[1]]
        target_pos = None
        for target in self.jump_file:
            pos = multi_scale_search(target, state_cut, 0.4, 15)
            if target_pos is None or pos[-1] > target_pos[-1]:
                target_pos = pos
        return np.array([(target_pos[0]+target_pos[2])//2, (target_pos[1]+target_pos[3])//2]) + sym_tl
    
    
    def get_target_position_fast(self, state, player_pos):
        state_cut = state[:player_pos[0],:,:]
        m1 = (state_cut[:, :, 0] == 245)
        m2 = (state_cut[:, :, 1] == 245)
        m3 = (state_cut[:, :, 2] == 245)
        m = np.uint8(np.float32(m1 * m2 * m3) * 255)
        b1, b2 = cv2.connectedComponents(m)
        for i in range(1, np.max(b2) + 1):
            x, y = np.where(b2 == i)
            # print('fast', len(x))
            if len(x) > 280 and len(x) < 310:
                r_x, r_y = x, y
        h, w = int(r_x.mean()), int(r_y.mean())
        return np.array([h, w])
    
    
    def jump(self, player_pos, target_pos):
        distance = np.linalg.norm(player_pos - target_pos)
        press_time = distance * self.sensitivity
        press_time = int(np.rint(press_time))
        press_h, press_w = int(0.82*self.resolution[0]), self.resolution[1]//2
        print(press_h, press_w)
        """
        if self.phone == 'Android':
            cmd = 'adb shell input swipe {} {} {} {} {}'.format(press_w, press_h, press_w, press_h, press_time)
            print(cmd)
            os.system(cmd)
        elif self.phone == 'IOS':
            self.s.tap_hold(press_w, press_h, press_time / 1000.)
        """
    
    """
    def debugging(self):
        current_state = self.state.copy()
        cv2.circle(current_state, (self.player_pos[1], self.player_pos[0]), 5, (0,255,0), -1)
        cv2.circle(current_state, (self.target_pos[1], self.target_pos[0]), 5, (0,0,255), -1)
        cv2.imwrite(os.path.join(self.debug, 'state_{:03d}_res_h_{}_w_{}.png'.format(self.step, self.target_pos[0], self.target_pos[1])), current_state)
    """
    def play(self):
        self.state = self.get_current_state()
        image=self.state 
        self.player_pos ,rect= self.get_player_position(self.state)#传入图像数组
        x1=rect[0]
        y1=rect[1]
        x2=rect[2]
        y2=rect[3]

        showFocus(image,self.player_pos[0],self.player_pos[1],x1,y1,x2,y2)

        
        if self.phone == 'IOS':
            self.target_pos = self.get_target_position(self.state, self.player_pos)
            
            #cv2.circle(image, (self.target_pos[1], self.target_pos[0]), 30, (71,23,226))
            #cv2.rectangle(image, (self.target_pos[1]-self.bb_size[1]//2,self.target_pos[0]-self.bb_size[0]//2), (self.target_pos[1]+self.bb_size[1]//2,self.target_pos[0]+self.bb_size[0]//2), (255,0,0),3)
            #cv2.imwrite("cat.jpg", image)
            showFocus(image,self.target_pos[0],self.target_pos[1],self.target_pos[1]-self.bb_size[1]//2,
                            self.target_pos[0]-self.bb_size[0]//2,self.target_pos[1]+self.bb_size[1]//2,
                            self.target_pos[0]+self.bb_size[0]//2,name="targert")
            print('multiscale-search, step: %04d' % self.step)
        else:
            try:
                self.target_pos = self.get_target_position_fast(self.state, self.player_pos)
                print('fast-search, step: %04d' % self.step)
            except UnboundLocalError:
                self.target_pos = self.get_target_position(self.state, self.player_pos)
                print('multiscale-search, step: %04d' % self.step)
        if self.debug:
            self.debugging()
        
        self.jump(self.player_pos, self.target_pos)
        """
        self.step += 1
        time.sleep(1.5)
        """

    def run(self):
        self.play()
        """
        try:
            while True:
                self.play()
        except KeyboardInterrupt:
                pass
        """
if __name__ == "__main__":
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--phone', default='Android', choices=['Android', 'IOS'], type=str, help='mobile phone OS')
    parser.add_argument('--sensitivity', default=2.045, type=float, help='constant for press time')
    parser.add_argument('--serverURL', default='http://localhost:8100', type=str, help='ServerURL for wda Client')
    parser.add_argument('--resource', default='resource', type=str, help='resource dir')
    parser.add_argument('--debug', default=None, type=str, help='debug mode, specify a directory for storing log files.')
    args = parser.parse_args()
    # print(args)
    """
    #AI = WechatAutoJump(args.phone, args.sensitivity, args.serverURL, args.debug, args.resource)
    AI = WechatAutoJump()
    AI.run()



